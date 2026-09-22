"""MT5-facing tools exposed to the autonomous trading agent."""

import io
import math
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from dotenv import load_dotenv

from collection import PriceDataCollection
from connection import connect
import MetaTrader5 as mt5
from order import (
    close_all_order as _close_all_order,
    close_order as _close_order,
    modify_order as _modify_order,
    open_orders as _open_orders,
    place_order as _place_order,
)

_SUPPORTED_TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1", "W1")
_DATE_RANGE_PATTERN = re.compile(r"^[1-9]\d*[DWMY]$", re.IGNORECASE)

from pathlib import Path
import os

from agent.paths import AGENT_TOOL_EVENTS_LOG_PATH, ENV_FILE
from agent.agent_backend import sandbox_backend

load_dotenv(ENV_FILE)

_connection_auth: dict[str, Any] | None = {
    "login": int(os.environ["DERIV_LOGIN"]),
    "password": os.environ["DERIV_PASSWORD"],
    "server": os.environ["DERIV_SERVER"],
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
}

_compact_price_cache: dict[tuple, tuple[int, Any]] = {}
_COMPACT_CACHE_SECONDS = 15 * 60


def configure_connection(auth: dict[str, Any]) -> None:
    """Configure the MT5 credentials used by the tools' automatic connection handling."""
    global _connection_auth
    _connection_auth = dict(auth)


def is_connected() -> bool:
    """Return whether the current process has an authenticated MT5 account."""
    try:
        return mt5.account_info() is not None
    except Exception:
        return False


def connect_mt5_terminal():
    """Connect to the configured MetaTrader 5 terminal."""
    if _connection_auth is None:
        return _tool_failure("MetaTrader 5 connection credentials have not been configured.")
    return connect(_connection_auth)


def _markdown_cell(value):
    if value is None:
        return ""
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if converted is not value:
            return _markdown_cell(converted)
    try:
        if value != value:
            return ""
    except Exception:
        pass
    isoformat = getattr(value, "isoformat", None)
    text = isoformat() if callable(isoformat) else str(value)
    return text.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _dataframe_to_markdown(candles):
    if "time" in candles.columns:
        frame = candles.reset_index(drop=True)
    else:
        frame = candles.reset_index()
        index_column = candles.index.name or "index"
        if index_column != "time":
            frame = frame.rename(columns={index_column: "time"})
    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(_markdown_cell(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def _json_cell(value):
    if value is None:
        return None
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if converted is not value:
            return _json_cell(converted)
    try:
        if value != value:
            return None
    except Exception:
        pass
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else value


def _request_metadata(symbols, timeframes, date_range, symbol):
    return {"symbol": symbol, "symbols": symbols, "timeframes": timeframes, "date_range": date_range}


def _request_error(metadata, message, *, stage: str | None = None):
    error = {"code": None, "message": message}
    if stage is not None:
        error["stage"] = stage
    return {"success": False, **metadata, "error": error}


def _validate_price_request(symbols, timeframes, date_range, symbol):
    if not isinstance(symbols, list) or not symbols or any(not isinstance(value, str) or not value.strip() for value in symbols):
        return "symbols must be a non-empty list of symbol strings."
    if not isinstance(symbol, str) or not symbol.strip():
        return "symbol must be a non-empty string."
    if symbol not in symbols:
        return "symbol must be included in symbols."
    if not isinstance(timeframes, list) or not timeframes or any(not isinstance(value, str) or value.upper() not in _SUPPORTED_TIMEFRAMES for value in timeframes):
        return "timeframes must be a non-empty list of supported MT5 timeframes."
    if not isinstance(date_range, str) or not _DATE_RANGE_PATTERN.fullmatch(date_range):
        return "date_range must be a relative lookback such as 10D, 2W, 5M, or 1Y."
    return None


def _validate_indicators(indicators):
    if not isinstance(indicators, list):
        return "indicators must be a list of indicator configurations."
    for index, indicator in enumerate(indicators):
        prefix = f"indicators[{index}]"
        if not isinstance(indicator, dict):
            return f"{prefix} must be an object with indicator, timeframe, optional params, and optional outputs."
        if "name" in indicator:
            return f"{prefix}.name is not supported; use {prefix}.indicator."
        if "timeperiod" in indicator:
            return f"{prefix}.timeperiod is not supported; use {prefix}.params.timeperiod."
        if not isinstance(indicator.get("indicator"), str) or not indicator["indicator"].strip():
            return f"{prefix}.indicator must be a non-empty string."
        if not isinstance(indicator.get("timeframe"), str) or not indicator["timeframe"].strip():
            return f"{prefix}.timeframe must be a non-empty string."
        if "params" in indicator and not isinstance(indicator["params"], dict):
            return f"{prefix}.params must be an object."
        if "outputs" in indicator and (
            not isinstance(indicator["outputs"], list)
            or any(not isinstance(output, str) or not output.strip() for output in indicator["outputs"])
        ):
            return f"{prefix}.outputs must be a list of non-empty strings."
    return None


def _safe_collection_error(error: Exception) -> str:
    message = " ".join(str(error).split())[:500]
    detail = f": {message}" if message else ""
    return f"Price-data collection failed with {type(error).__name__}{detail}"


def _normalized_price_request(symbols, timeframes, date_range, symbol, indicators):
    metadata = _request_metadata(symbols, timeframes, date_range, symbol)
    validation_error = _validate_price_request(symbols, timeframes, date_range, symbol)
    if validation_error:
        return None, _request_error(metadata, validation_error)
    indicator_error = _validate_indicators(indicators)
    if indicator_error:
        return None, _request_error(metadata, indicator_error, stage="indicator_validation")
    normalized = (
        [item.strip() for item in symbols],
        [timeframe.upper() for timeframe in timeframes],
        date_range.upper(),
        symbol.strip(),
    )
    return normalized, None


def _load_price_frame(symbols, timeframes, date_range, symbol, indicators, metadata):
    if not is_connected():
        connection_result = connect_mt5_terminal()
        if not connection_result.get("success", False):
            return None, {"success": False, **metadata, "error": connection_result.get("error") or {"code": None, "message": "MetaTrader 5 connection failed."}}
    try:
        price_data = PriceDataCollection(symbols=symbols, timeframes=timeframes, date_range=date_range, indicators=indicators)
        candles = price_data.get_price_data(symbol)
        if candles is None or candles.empty:
            return None, _request_error(metadata, "No candle data is available for the requested symbol and timeframes.")
        return candles, None
    except Exception as error:
        return None, _request_error(metadata, _safe_collection_error(error), stage="collection")


def get_price_data(symbols: list[str], timeframes: list[str], date_range: str, symbol: str, indicators: list[dict]):
    """Return all merged candles for ``symbol`` as a Markdown table."""
    normalized, failure = _normalized_price_request(symbols, timeframes, date_range, symbol, indicators)
    if failure:
        return failure
    normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol = normalized
    metadata = _request_metadata(normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol)
    candles, failure = _load_price_frame(normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol, indicators, metadata)
    return failure if failure else _dataframe_to_markdown(candles)


def get_compact_price_data(symbols: list[str], timeframes: list[str], date_range: str, symbol: str, indicators: list[dict], recent_rows: int = 192, use_cache: bool = True):
    """Return recent merged price data as compact JSON-safe columns and rows for agent analysis."""
    normalized, failure = _normalized_price_request(symbols, timeframes, date_range, symbol, indicators)
    if failure:
        return failure
    if not isinstance(recent_rows, int) or isinstance(recent_rows, bool) or not 1 <= recent_rows <= 500:
        return _request_error(_request_metadata(symbols, timeframes, date_range, symbol), "recent_rows must be an integer from 1 to 500.", stage="request_validation")
    if not isinstance(use_cache, bool):
        return _request_error(_request_metadata(symbols, timeframes, date_range, symbol), "use_cache must be a boolean.", stage="request_validation")
    normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol = normalized
    metadata = _request_metadata(normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol)
    cache_key = (tuple(normalized_symbols), tuple(normalized_timeframes), normalized_date_range, normalized_symbol, repr(indicators))
    bucket = int(time.time() // _COMPACT_CACHE_SECONDS)
    cached = _compact_price_cache.get(cache_key)
    if use_cache and cached and cached[0] == bucket:
        candles = cached[1]
    else:
        candles, failure = _load_price_frame(normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol, indicators, metadata)
        if failure:
            return failure
        _compact_price_cache[cache_key] = (bucket, candles)
    frame = candles.tail(recent_rows)
    columns = ["time", *[str(column) for column in frame.columns]]
    times = frame.index.tolist() if "time" not in frame.columns else frame["time"].tolist()
    values = frame.drop(columns=["time"], errors="ignore").itertuples(index=False, name=None)
    rows = [[_json_cell(time_value), *[_json_cell(value) for value in row]] for time_value, row in zip(times, values)]
    latest = {column: _json_cell(frame[column].dropna().iloc[-1]) if not frame[column].dropna().empty else None for column in frame.columns if column != "time"}
    return {
        "success": True,
        **metadata,
        "row_count": len(candles),
        "returned_rows": len(rows),
        "truncated": len(candles) > len(rows),
        "columns": columns,
        "latest": latest,
        "rows": rows,
    }


def _tool_failure(message):
    return {"success": False, "data": None, "error": {"code": None, "message": message}}


def _normalize_market_order_type(order_type: str) -> str | None:
    if not isinstance(order_type, str):
        return None

    aliases = {
        "long": "buy",
        "buy": "buy",
        "short": "sell",
        "sell": "sell",
    }
    return aliases.get(order_type.strip().lower())


def place_trade(symbol: str, order_type: str, volume: float, stop_loss: float, take_profit: float):
    """Place an agent-selected, broker-valid market order with evidence-based exits."""
    side = _normalize_market_order_type(order_type)
    if side is None:
        return _tool_failure("order_type must be one of LONG, SHORT, buy, or sell.")

    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
        for value in (volume, stop_loss, take_profit)
    ):
        return _tool_failure(
            "volume, stop_loss, and take_profit must be positive finite numbers."
        )

    try:
        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        if tick is None or symbol_info is None:
            return _tool_failure("Current tick or symbol information is unavailable.")
        entry_price = float(tick.ask if side == "buy" else tick.bid)

        if side == "buy" and not (stop_loss < entry_price < take_profit):
            return _tool_failure(
                "Buy trades require stop_loss below and take_profit above the current ask."
            )
        if side == "sell" and not (take_profit < entry_price < stop_loss):
            return _tool_failure(
                "Sell trades require take_profit below and stop_loss above the current bid."
            )

        volume_min = float(symbol_info.volume_min)
        volume_max = float(symbol_info.volume_max)
        volume_step = float(symbol_info.volume_step)
        if volume_min <= 0 or volume_max < volume_min or volume_step <= 0:
            return _tool_failure("Broker volume constraints are invalid.")

        steps = (volume - volume_min) / volume_step
        if not volume_min <= volume <= volume_max or not math.isclose(
            steps, round(steps), abs_tol=1e-8
        ):
            return _tool_failure(
                "The requested volume is not supported by this broker for this symbol."
            )
    except ValueError as error:
        return _tool_failure(str(error))
    except Exception:
        return _tool_failure("Unable to validate the requested trade volume.")
    return _place_order(symbol=symbol, order_type=side, volume=volume, price=entry_price, sl=stop_loss, tp=take_profit, magic=1122, comment="")


def close_trade(ticket: int, target: str = "position", volume: float | None = None, deviation: int = 20, magic: int = 0, comment: str = "", type_filling: str = "return"):
    """Close a position or cancel a pending order by ticket."""
    return _close_order(ticket, target, volume, deviation, magic, comment, type_filling)


def close_all_trades(symbol: str | None = None, magic: int | None = None, include_positions: bool = True, include_pending: bool = True, deviation: int = 20, comment: str = "", type_filling: str = "return"):
    """Close all matching positions and/or cancel matching pending orders."""
    return _close_all_order(symbol, magic, include_positions, include_pending, deviation, comment, type_filling)


def modify_trade(ticket: int, target: str = "position", symbol: str | None = None, price: float | None = None, sl: float | None = None, tp: float | None = None, expiration: int | None = None, type_time: str | None = None, comment: str | None = None):
    """Modify stop loss/take profit on a position or fields on a pending order."""
    return _modify_order(ticket, target, symbol, price, sl, tp, expiration, type_time, comment)


def get_open_trades(symbol: str | None = None):
    """Return all open positions and pending orders, optionally for one symbol."""
    return _open_orders(symbol=symbol)


def get_account_snapshot():
    """Return the read-only MT5 facts used in each trading-decision report."""
    try:
        account_info = mt5.account_info()
        if account_info is None:
            raise RuntimeError("MT5 account information is unavailable.")
        return {"success": True, "data": {"balance": float(account_info.balance), "equity": float(account_info.equity), "profit": float(account_info.profit), "currency": str(account_info.currency)}, "error": None}
    except Exception as error:
        return {"success": False, "data": None, "error": {"code": None, "message": str(error) or "Unable to read MT5 account information."}}


def get_symbol_specification(symbol: str):
    """Return broker point, digits, and minimum stop distance for ``symbol``."""
    if not isinstance(symbol, str) or not symbol.strip():
        return _tool_failure("symbol must be a non-empty string.")

    symbol = symbol.strip()
    if not is_connected():
        connection_result = connect_mt5_terminal()
        if not connection_result.get("success", False):
            return _tool_failure("MetaTrader 5 connection failed while reading symbol specification.")

    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return _tool_failure("Broker symbol specification is unavailable.")

        digits = getattr(symbol_info, "digits", None)
        point = getattr(symbol_info, "point", None)
        stops_level = getattr(symbol_info, "trade_stops_level", None)
        if (
            isinstance(digits, bool)
            or not isinstance(digits, int)
            or digits < 0
            or isinstance(point, bool)
            or not isinstance(point, (int, float))
            or not math.isfinite(point)
            or point <= 0
            or isinstance(stops_level, bool)
            or not isinstance(stops_level, (int, float))
            or not math.isfinite(stops_level)
            or stops_level < 0
        ):
            return _tool_failure("Broker symbol specification contains invalid point, digits, or minimum stop data.")

        point = float(point)
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "digits": digits,
                "point": point,
                "trade_stops_level": float(stops_level),
                "minimum_stop_distance": float(stops_level) * point,
            },
            "error": None,
        }
    except Exception as error:
        return _tool_failure(str(error) or "Unable to read broker symbol specification.")


import json
from datetime import datetime, timezone
from pathlib import Path


LOG_FILE = AGENT_TOOL_EVENTS_LOG_PATH

SUBAGENT_NAMES = {
    "Atlas",
    "Acnologia",
    "Grandine",
    "Ignia",
}

# task run_id -> delegated subagent
TASK_RUNS = {}


def json_safe(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        pass

    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass

    return str(value)


def write_jsonl(record):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


def extract_task_agent(tool_input):
    """
    Extract delegated subagent name from DeepAgents `task` input.
    """

    if not isinstance(tool_input, dict):
        return None

    # Different DeepAgents versions may use one of these.
    for key in (
        "subagent_type",
        "agent",
        "agent_name",
        "subagent",
    ):
        value = tool_input.get(key)

        if value in SUBAGENT_NAMES:
            return value

    # Fallback: inspect the entire task payload.
    text = json.dumps(
        tool_input,
        default=str,
    )

    for agent_name in SUBAGENT_NAMES:
        if agent_name in text:
            return agent_name

    return None


def get_agent_name(event):
    metadata = event.get("metadata", {}) or {}

    for key in (
        "lc_agent_name",
        "agent_name",
        "subagent_name",
    ):
        value = metadata.get(key)

        if value in SUBAGENT_NAMES:
            return value

    checkpoint_ns = str(
        metadata.get("langgraph_checkpoint_ns", "")
    )

    for agent_name in SUBAGENT_NAMES:
        if agent_name in checkpoint_ns:
            return agent_name

    return "main-agent"

def print_agent_event(event):

    event_type = event.get("event")
    name = event.get("name", "")
    run_id = str(event.get("run_id", ""))

    agent_name = get_agent_name(event)

    # =====================================================
    # MODEL STREAM
    # =====================================================

    if event_type == "on_chat_model_stream":

        chunk = event.get("data", {}).get("chunk")
        content = getattr(chunk, "content", None)

        if content:
            print(
                content,
                end="",
                flush=True,
            )

    # =====================================================
    # TOOL START
    # =====================================================

    elif event_type == "on_tool_start":

        tool_input = event.get(
            "data",
            {},
        ).get("input")

        # DeepAgents uses `task` to delegate to subagents.
        if name == "task":

            delegated_agent = extract_task_agent(
                tool_input
            )

            if delegated_agent:
                TASK_RUNS[run_id] = delegated_agent

                print(
                    f"\n\n[MAIN → {delegated_agent}]"
                    " [SUBAGENT START]"
                )

            else:
                print(
                    "\n\n[main-agent]"
                    " [SUBAGENT START] unknown"
                )

        else:

            print(
                f"\n\n[{agent_name}]"
                f" [TOOL START] {name}"
            )

        # print(
        #     json.dumps(
        #         json_safe(tool_input),
        #         indent=2,
        #         ensure_ascii=False,
        #         default=str,
        #     )
        # )

        write_jsonl({
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event": "tool_start",
            "agent": (
                TASK_RUNS.get(run_id)
                if name == "task"
                else agent_name
            ),
            "tool": name,
            "run_id": run_id,
            "input": json_safe(tool_input),
        })

    # =====================================================
    # TOOL END
    # =====================================================

    elif event_type == "on_tool_end":

        output = event.get(
            "data",
            {},
        ).get("output")

        if name == "task":

            delegated_agent = TASK_RUNS.get(
                run_id,
                "unknown-subagent",
            )

            print(
                f"\n[{delegated_agent}]"
                " [SUBAGENT END]"
            )

        else:

            delegated_agent = agent_name

            print(
                f"\n[{agent_name}]"
                f" [TOOL END] {name}"
            )

        # print(
        #     json.dumps(
        #         json_safe(output),
        #         indent=2,
        #         ensure_ascii=False,
        #         default=str,
        #     )
        # )

        write_jsonl({
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event": "tool_end",
            "agent": delegated_agent,
            "tool": name,
            "run_id": run_id,
            "output": json_safe(output),
        })

        if name == "task":
            TASK_RUNS.pop(run_id, None)

import asyncio
from langchain_core.tools import tool


VALID_TIMEFRAMES = {
    "D1",
    "H4",
    "H1",
    "M15",
    "M5",
    "M1",
}

_TIMEFRAME_DURATIONS = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
    "W1": timedelta(weeks=1),
}


def _get_latest_compact_candle_time(symbol: str, timeframe: str) -> str:
    """Fetch one uncached candle through the shared market-data interface."""
    result = get_compact_price_data(
        symbols=[symbol],
        timeframes=[timeframe],
        date_range="1D",
        symbol=symbol,
        indicators=[],
        recent_rows=1,
        use_cache=False,
    )
    if not isinstance(result, dict) or not result.get("success"):
        raise RuntimeError("Unable to retrieve current candle data.")

    rows = result.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Current candle data contains no rows.")

    latest_row = rows[-1]
    if not isinstance(latest_row, list) or not latest_row or latest_row[0] is None:
        raise RuntimeError("Current candle data has no usable timestamp.")

    return str(latest_row[0])


def _seconds_until_next_candle(
    candle_time: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> float:
    """Return the delay until the next candle boundary in UTC."""
    try:
        candle_start = datetime.fromisoformat(candle_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("Current candle has an invalid timestamp.") from exc

    if candle_start.tzinfo is None:
        candle_start = candle_start.replace(tzinfo=timezone.utc)

    duration = _TIMEFRAME_DURATIONS.get(timeframe)
    if duration is None:
        raise RuntimeError(f"Unsupported timeframe: {timeframe}")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    next_candle_time = candle_start.astimezone(timezone.utc) + duration
    return max(0.0, (next_candle_time - current_time.astimezone(timezone.utc)).total_seconds())


@tool
async def wait_for_market_update(
    symbol: str,
    timeframe: str = "M15",
    poll_seconds: int = 5,
) -> dict:
    """
    Wait for a new candle before continuing market analysis.

    Use this after a WAIT or NO_TRADE decision so the system does not
    repeatedly analyze identical market data.

    Supported timeframes:
    D1, H4, H1, M15, M5, M1.
    """

    if timeframe not in VALID_TIMEFRAMES:
        return {
            "success": False,
            "error": f"Unsupported timeframe: {timeframe}",
        }

    try:
        previous_time = _get_latest_compact_candle_time(
            symbol=symbol,
            timeframe=timeframe,
        )

        print(
            f"[WAIT] {symbol} {timeframe} | "
            f"current candle: {previous_time}"
        )

        seconds_until_boundary = _seconds_until_next_candle(
            previous_time,
            timeframe,
        )
        await asyncio.sleep(seconds_until_boundary)

        while True:
            current_time = _get_latest_compact_candle_time(
                symbol=symbol,
                timeframe=timeframe,
            )

            if current_time != previous_time:

                print(
                    f"[MARKET UPDATE] {symbol} {timeframe} | "
                    f"{previous_time} -> {current_time}"
                )

                return {
                    "success": True,
                    "event": "new_candle",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "previous_candle_time": str(previous_time),
                    "new_candle_time": str(current_time),
                }

            await asyncio.sleep(max(poll_seconds, 1))

    except Exception as exc:
        return {
            "success": False,
            "event": "market_data_error",
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(exc),
        }


def _safe_sandbox_filename_component(value: str) -> str:
    """Return a filename-safe representation without changing request metadata."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def get_price_data_file(
    symbol: str,
    timeframes: list[str],
    date_range: str,
):
    """
    Retrieve raw market price data and upload it to the sandbox.

    Returns the sandbox file path and dataset metadata. The CSV is a merged
    frame with ``time`` and, for every requested timeframe ``tf``, the columns
    ``open_{tf}``, ``high_{tf}``, ``low_{tf}``, and ``close_{tf}``, where
    ``tf`` is one of M1, M5, M15, H1, H4, D1, or W1. Consumers must select
    the four suffixed OHLC columns for each timeframe independently; rows can
    be absent for an individual timeframe in the merged frame.
    """
    normalized, failure = _normalized_price_request(
        [symbol], timeframes, date_range, symbol, []
    )
    if failure:
        return failure

    normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol = normalized
    metadata = _request_metadata(
        normalized_symbols,
        normalized_timeframes,
        normalized_date_range,
        normalized_symbol,
    )
    df, failure = _load_price_frame(
        normalized_symbols,
        normalized_timeframes,
        normalized_date_range,
        normalized_symbol,
        [],
        metadata,
    )
    if failure:
        return failure

    filename = (
        f"{_safe_sandbox_filename_component(normalized_symbol)}_"
        f"{_safe_sandbox_filename_component(normalized_date_range)}_"
        f"{uuid.uuid4().hex[:8]}.csv"
    )

    path = f"/workspace/market/{filename}"

    buffer = io.BytesIO()

    try:
        df.to_csv(
            buffer,
            index=False,
        )
    except Exception:
        return _request_error(
            metadata,
            "Unable to serialize price data for the sandbox.",
            stage="serialization",
        )

    try:
        upload_responses = sandbox_backend.upload_files([
            (
                path,
                buffer.getvalue(),
            )
        ])
    except Exception:
        return _request_error(
            metadata,
            "Unable to upload price data to the sandbox.",
            stage="sandbox_upload",
        )

    if (
        not isinstance(upload_responses, list)
        or len(upload_responses) != 1
        or getattr(upload_responses[0], "error", None) is not None
    ):
        return _request_error(
            metadata,
            "Unable to upload price data to the sandbox.",
            stage="sandbox_upload",
        )

    return {
        "success": True,
        "path": path,
        **metadata,
        "rows": len(df),
        "columns": list(df.columns),
    }
