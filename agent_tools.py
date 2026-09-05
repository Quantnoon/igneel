"""MT5-facing tools exposed to the autonomous trading agent."""

import math
import re
import time
from typing import Any

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
from trade_manager import TradeExecutionGuard

_SUPPORTED_TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1", "W1")
_DATE_RANGE_PATTERN = re.compile(r"^[1-9]\d*[DWMY]$", re.IGNORECASE)
_connection_auth: dict[str, Any] | None = {
    "login": 41180154,
    "password": "Money_135795",
    "server": "Deriv-Demo",
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
}

trade_execution_guard = TradeExecutionGuard()
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


def get_compact_price_data(symbols: list[str], timeframes: list[str], date_range: str, symbol: str, indicators: list[dict], recent_rows: int = 192):
    """Return recent merged price data as compact JSON-safe columns and rows for agent analysis."""
    normalized, failure = _normalized_price_request(symbols, timeframes, date_range, symbol, indicators)
    if failure:
        return failure
    if not isinstance(recent_rows, int) or isinstance(recent_rows, bool) or not 1 <= recent_rows <= 500:
        return _request_error(_request_metadata(symbols, timeframes, date_range, symbol), "recent_rows must be an integer from 1 to 500.", stage="request_validation")
    normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol = normalized
    metadata = _request_metadata(normalized_symbols, normalized_timeframes, normalized_date_range, normalized_symbol)
    cache_key = (tuple(normalized_symbols), tuple(normalized_timeframes), normalized_date_range, normalized_symbol, repr(indicators))
    bucket = int(time.time() // _COMPACT_CACHE_SECONDS)
    cached = _compact_price_cache.get(cache_key)
    if cached and cached[0] == bucket:
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


def place_trade(symbol: str, order_type: str, volume: float, stop_loss: float, take_profit: float):
    """Place an agent-selected, broker-valid market order with evidence-based exits."""
    error = trade_execution_guard.placement_error(symbol)
    if error:
        return _tool_failure(error)
    if order_type not in ("buy", "sell"):
        return _tool_failure("order_type must be buy or sell for the continuous strategy.")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 for value in (volume, stop_loss, take_profit)):
        return _tool_failure("volume, stop_loss, and take_profit must be positive numbers.")
    try:
        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        if tick is None or symbol_info is None:
            return _tool_failure("Current tick or symbol information is unavailable.")
        entry_price = float(tick.ask if order_type == "buy" else tick.bid)
        if order_type == "buy" and not (stop_loss < entry_price < take_profit):
            return _tool_failure("Buy trades require stop_loss below and take_profit above the current ask.")
        if order_type == "sell" and not (take_profit < entry_price < stop_loss):
            return _tool_failure("Sell trades require take_profit below and stop_loss above the current bid.")
        volume_min = float(symbol_info.volume_min)
        volume_max = float(symbol_info.volume_max)
        volume_step = float(symbol_info.volume_step)
        if volume_min <= 0 or volume_max < volume_min or volume_step <= 0:
            return _tool_failure("Broker volume constraints are invalid.")
        steps = (volume - volume_min) / volume_step
        if not volume_min <= volume <= volume_max or not math.isclose(steps, round(steps), abs_tol=1e-8):
            return _tool_failure("The requested volume is not supported by this broker for this symbol.")
    except ValueError as error:
        return _tool_failure(str(error))
    except Exception:
        return _tool_failure("Unable to validate the requested trade volume.")
    config = trade_execution_guard.config
    return _place_order(symbol=symbol, order_type=order_type, volume=volume, price=entry_price, sl=stop_loss, tp=take_profit, magic=config.magic, comment=config.comment)


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
