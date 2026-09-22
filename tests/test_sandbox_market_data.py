import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent.agent_prompts import (
    ACNOLOGIA_SYSTEM_PROMPT,
    ATLAS_SYSTEM_PROMPT,
    GRANDINE_SYSTEM_PROMPT,
    MARKET_DATA_FILE_CONTRACT,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_market_data_file_caller_documents_the_request_limits():
    assert "timeframes` must be a list, never a comma-separated string." in MARKET_DATA_FILE_CONTRACT
    assert "positive integer followed by `D`, `W`, `M`, or `Y`" in MARKET_DATA_FILE_CONTRACT
    assert "Maximum date range by timeframe:" in MARKET_DATA_FILE_CONTRACT
    assert "use the shortest applicable maximum" in MARKET_DATA_FILE_CONTRACT
    assert "## TIMEFRAME PLAN" in MARKET_DATA_FILE_CONTRACT
    assert "web-researched approach's documented rules" in MARKET_DATA_FILE_CONTRACT
    assert "Request every timeframe in that plan" in MARKET_DATA_FILE_CONTRACT
    assert "Do not use a fixed timeframe ladder" in MARKET_DATA_FILE_CONTRACT
    assert "minimum sufficient lookback" in MARKET_DATA_FILE_CONTRACT
    assert "split it into compatible requests" in MARKET_DATA_FILE_CONTRACT
    assert "open_{tf}, high_{tf}, low_{tf}, close_{tf}" in MARKET_DATA_FILE_CONTRACT

    for prompt in (
        ATLAS_SYSTEM_PROMPT,
        ACNOLOGIA_SYSTEM_PROMPT,
        GRANDINE_SYSTEM_PROMPT,
    ):
        assert "get_price_data_file" in prompt
        assert MARKET_DATA_FILE_CONTRACT in prompt


def test_market_data_file_callers_describe_csv_loading_only():
    for prompt in (
        ATLAS_SYSTEM_PROMPT,
        ACNOLOGIA_SYSTEM_PROMPT,
        GRANDINE_SYSTEM_PROMPT,
    ):
        assert "CSV" in prompt
        assert "Parquet" not in prompt
        assert "read_parquet" not in prompt

    assert 'pd.read_csv("<returned-path>")' in ATLAS_SYSTEM_PROMPT
    assert 'pd.read_csv("<returned-path>")' in ACNOLOGIA_SYSTEM_PROMPT
    assert 'pd.read_csv("<returned-path>")' in GRANDINE_SYSTEM_PROMPT


def test_market_data_file_callers_follow_and_persist_the_timeframe_plan():
    assert "TIMEFRAME PLAN:" in ATLAS_SYSTEM_PROMPT
    assert "persisted in Atlas's RESEARCH CONTEXT exactly" in MARKET_DATA_FILE_CONTRACT
    assert "Use the exact TIMEFRAME PLAN from Atlas's active research context" in ACNOLOGIA_SYSTEM_PROMPT
    assert "Use the exact TIMEFRAME PLAN from the active research context" in GRANDINE_SYSTEM_PROMPT
    assert "return NO_TRADE with unavailable market evidence" in ACNOLOGIA_SYSTEM_PROMPT
    assert "recommend HOLD" in GRANDINE_SYSTEM_PROMPT


def test_atlas_reviews_each_search_url_before_using_web_evidence():
    assert "Treat web-search snippets only as discovery metadata, not\nas evidence" in ATLAS_SYSTEM_PROMPT
    assert "For every distinct URL returned by each successful `web_search`" in ATLAS_SYSTEM_PROMPT
    assert "either call `fetch_url`, or record why it was skipped" in ATLAS_SYSTEM_PROMPT
    assert "attempted/unavailable" in ATLAS_SYSTEM_PROMPT
    assert "only when supported by a successfully fetched source" in ATLAS_SYSTEM_PROMPT
    assert "SOURCE REVIEW:" in ATLAS_SYSTEM_PROMPT
    assert "SKIPPED: each un-fetched search\nresult URL with its reason" in ATLAS_SYSTEM_PROMPT


def test_acnologia_prompt_requires_stop_method_and_risk_reward_calculation():
    assert "must be LONG or NO_TRADE" in ACNOLOGIA_SYSTEM_PROMPT
    assert "Never return WAIT for\na qualifying direction" in ACNOLOGIA_SYSTEM_PROMPT
    assert "## STOP LOSS AND TAKE PROFIT" in ACNOLOGIA_SYSTEM_PROMPT
    assert "`ATR`" in ACNOLOGIA_SYSTEM_PROMPT
    assert "`SWING`" in ACNOLOGIA_SYSTEM_PROMPT
    assert "`FIXED_POINTS`" in ACNOLOGIA_SYSTEM_PROMPT
    assert "get_symbol_specification" in ACNOLOGIA_SYSTEM_PROMPT
    assert "RISK REWARD RATIO:" in ACNOLOGIA_SYSTEM_PROMPT


def test_sandbox_analysis_contract_defines_the_suffixed_ohlc_extraction_rules():
    assert "one merged price DataFrame" in MARKET_DATA_FILE_CONTRACT
    assert "columns in the same DataFrame" in MARKET_DATA_FILE_CONTRACT
    assert "build one per-timeframe frame" in ATLAS_SYSTEM_PROMPT
    assert "low <= open/close <= high" in ATLAS_SYSTEM_PROMPT
    assert "planned timeframe is missing" in ATLAS_SYSTEM_PROMPT
    assert "do not substitute another timeframe" in ATLAS_SYSTEM_PROMPT
    assert "forming candle" in ATLAS_SYSTEM_PROMPT


def test_price_data_file_tool_documents_the_timeframe_suffixed_ohlc_schema(monkeypatch):
    tools, _ = load_tools(monkeypatch)

    assert "open_{tf}" in tools.get_price_data_file.__doc__
    assert "high_{tf}" in tools.get_price_data_file.__doc__
    assert "low_{tf}" in tools.get_price_data_file.__doc__
    assert "close_{tf}" in tools.get_price_data_file.__doc__
    assert "independently" in tools.get_price_data_file.__doc__


def test_sandbox_analysis_prompts_use_python3_and_multiline_heredocs():
    assert "python3 - <<'PY'" in ATLAS_SYSTEM_PROMPT
    assert "the `python` command is not available" in ATLAS_SYSTEM_PROMPT
    assert "Do not flatten the script\ninto one shell line." in ATLAS_SYSTEM_PROMPT
    assert "the `python` command is not available" in GRANDINE_SYSTEM_PROMPT
    assert "closing delimiter each occupy separate lines" in GRANDINE_SYSTEM_PROMPT


def load_tools(monkeypatch):
    """Load the file tool with local-only fakes for its external dependencies."""
    monkeypatch.setenv("DERIV_LOGIN", "1")
    monkeypatch.setenv("DERIV_PASSWORD", "test-password")
    monkeypatch.setenv("DERIV_SERVER", "test-server")

    backend = ModuleType("agent.agent_backend")
    backend.sandbox_backend = MagicMock()
    collection = ModuleType("collection")
    collection.PriceDataCollection = object
    connection = ModuleType("connection")
    connection.connect = MagicMock()
    order = ModuleType("order")
    order.close_all_order = MagicMock()
    order.close_order = MagicMock()
    order.modify_order = MagicMock()
    order.open_orders = MagicMock()
    order.place_order = MagicMock()
    mt5 = ModuleType("MetaTrader5")
    mt5.TIMEFRAME_D1 = 1
    mt5.TIMEFRAME_H4 = 2
    mt5.TIMEFRAME_H1 = 3
    mt5.TIMEFRAME_M15 = 4
    mt5.TIMEFRAME_M5 = 5
    mt5.TIMEFRAME_M1 = 6

    monkeypatch.setitem(sys.modules, "agent.agent_backend", backend)
    monkeypatch.setitem(sys.modules, "collection", collection)
    monkeypatch.setitem(sys.modules, "connection", connection)
    monkeypatch.setitem(sys.modules, "order", order)
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)

    spec = importlib.util.spec_from_file_location(
        "agent.test_sandbox_market_data_module",
        PROJECT_ROOT / "agent" / "agent_tools.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, backend.sandbox_backend


class Frame:
    columns = ["time", "open", "close"]

    def __init__(self, *, empty=False, serialization_error=None):
        self.empty = empty
        self.serialization_error = serialization_error

    def __len__(self):
        return 2

    def to_csv(self, buffer, *, index):
        if self.serialization_error:
            raise self.serialization_error
        assert index is False
        buffer.write(b"time,open,close\n2026-01-01,1.0,1.5\n")


def test_symbol_specification_returns_broker_point_and_minimum_stop_distance(monkeypatch):
    tools, _ = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "is_connected", lambda: True)
    monkeypatch.setattr(
        tools.mt5,
        "symbol_info",
        lambda symbol: SimpleNamespace(digits=5, point=0.00001, trade_stops_level=25),
        raising=False,
    )

    result = tools.get_symbol_specification(" EURUSD ")

    assert result == {
        "success": True,
        "data": {
            "symbol": "EURUSD",
            "digits": 5,
            "point": 0.00001,
            "trade_stops_level": 25.0,
            "minimum_stop_distance": 0.00025,
        },
        "error": None,
    }


@pytest.mark.parametrize(
    "symbol_info",
    (
        None,
        SimpleNamespace(digits=5, point=0, trade_stops_level=25),
        SimpleNamespace(digits=5, point=0.00001, trade_stops_level=-1),
    ),
)
def test_symbol_specification_rejects_missing_or_invalid_broker_values(monkeypatch, symbol_info):
    tools, _ = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "is_connected", lambda: True)
    monkeypatch.setattr(tools.mt5, "symbol_info", lambda _symbol: symbol_info, raising=False)

    result = tools.get_symbol_specification("EURUSD")

    assert result["success"] is False


def test_price_data_file_rejects_comma_delimited_timeframes_before_collection(monkeypatch):
    tools, _ = load_tools(monkeypatch)
    constructed = False

    class Collection:
        def __init__(self, **_kwargs):
            nonlocal constructed
            constructed = True

    monkeypatch.setattr(tools, "PriceDataCollection", Collection)

    result = tools.get_price_data_file("XAUUSD", "D1, H4", "1W")

    assert constructed is False
    assert result["success"] is False
    assert result["error"]["message"] == "timeframes must be a non-empty list of supported MT5 timeframes."


def test_price_data_file_normalizes_and_uploads_valid_timeframe_list(monkeypatch):
    tools, sandbox_backend = load_tools(monkeypatch)
    captured = {}
    frame = Frame()

    class Collection:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def get_price_data(self, symbol):
            captured["requested_symbol"] = symbol
            return frame

    monkeypatch.setattr(tools, "PriceDataCollection", Collection)
    monkeypatch.setattr(tools, "is_connected", lambda: True)
    monkeypatch.setattr(tools.uuid, "uuid4", lambda: type("Id", (), {"hex": "a" * 32})())
    sandbox_backend.upload_files.return_value = [SimpleNamespace(error=None)]

    result = tools.get_price_data_file(" XAUUSD ", ["d1", "h4"], "1w")

    assert captured == {
        "symbols": ["XAUUSD"],
        "timeframes": ["D1", "H4"],
        "date_range": "1W",
        "indicators": [],
        "requested_symbol": "XAUUSD",
    }
    assert result == {
        "success": True,
        "path": "/workspace/market/XAUUSD_1W_aaaaaaaa.csv",
        "symbol": "XAUUSD",
        "symbols": ["XAUUSD"],
        "timeframes": ["D1", "H4"],
        "date_range": "1W",
        "rows": 2,
        "columns": ["time", "open", "close"],
    }
    sandbox_backend.upload_files.assert_called_once_with([
        ("/workspace/market/XAUUSD_1W_aaaaaaaa.csv", b"time,open,close\n2026-01-01,1.0,1.5\n")
    ])


@pytest.mark.parametrize("timeframes", ([], ["D2"], None, 4))
def test_price_data_file_rejects_invalid_timeframe_values_before_collection(monkeypatch, timeframes):
    tools, _ = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "PriceDataCollection", MagicMock())

    result = tools.get_price_data_file("XAUUSD", timeframes, "1W")

    tools.PriceDataCollection.assert_not_called()
    assert result["success"] is False
    assert result["error"]["message"] == "timeframes must be a non-empty list of supported MT5 timeframes."


def test_price_data_file_returns_structured_collection_and_empty_data_failures(monkeypatch):
    tools, _ = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "is_connected", lambda: True)

    class BrokenCollection:
        def __init__(self, **_kwargs):
            raise ValueError("bad request")

    monkeypatch.setattr(tools, "PriceDataCollection", BrokenCollection)
    collection_failure = tools.get_price_data_file("XAUUSD", ["H4"], "1W")

    assert collection_failure["error"]["stage"] == "collection"
    assert "Traceback" not in collection_failure["error"]["message"]

    class EmptyCollection:
        def __init__(self, **_kwargs):
            pass

        def get_price_data(self, _symbol):
            return Frame(empty=True)

    monkeypatch.setattr(tools, "PriceDataCollection", EmptyCollection)
    empty_failure = tools.get_price_data_file("XAUUSD", ["H4"], "1W")

    assert empty_failure["error"]["message"] == "No candle data is available for the requested symbol and timeframes."


def test_price_data_file_returns_structured_serialization_and_upload_failures(monkeypatch):
    tools, sandbox_backend = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "is_connected", lambda: True)

    class Collection:
        def __init__(self, **_kwargs):
            pass

        def get_price_data(self, _symbol):
            return Frame(serialization_error=RuntimeError("internal detail"))

    monkeypatch.setattr(tools, "PriceDataCollection", Collection)
    serialization_failure = tools.get_price_data_file("XAUUSD", ["H4"], "1W")

    assert serialization_failure["error"] == {
        "code": None,
        "stage": "serialization",
        "message": "Unable to serialize price data for the sandbox.",
    }

    class UploadableCollection(Collection):
        def get_price_data(self, _symbol):
            return Frame()

    monkeypatch.setattr(tools, "PriceDataCollection", UploadableCollection)
    sandbox_backend.upload_files.side_effect = RuntimeError("internal detail")
    upload_failure = tools.get_price_data_file("XAUUSD", ["H4"], "1W")

    assert upload_failure["error"] == {
        "code": None,
        "stage": "sandbox_upload",
        "message": "Unable to upload price data to the sandbox.",
    }

    sandbox_backend.upload_files.side_effect = None
    sandbox_backend.upload_files.return_value = [SimpleNamespace(error="permission_denied")]
    response_failure = tools.get_price_data_file("XAUUSD", ["H4"], "1W")

    assert response_failure["error"] == {
        "code": None,
        "stage": "sandbox_upload",
        "message": "Unable to upload price data to the sandbox.",
    }


def test_wait_uses_uncached_compact_price_data_and_detects_a_new_candle(monkeypatch):
    tools, _ = load_tools(monkeypatch)
    calls = []
    responses = iter((
        {"success": True, "rows": [["2026-01-01T00:00:00+00:00", 1.0]]},
        {"success": True, "rows": [["2026-01-01T00:15:00+00:00", 1.1]]},
    ))

    def get_compact_price_data(**kwargs):
        calls.append(kwargs)
        return next(responses)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(tools, "get_compact_price_data", get_compact_price_data)
    monkeypatch.setattr(tools.asyncio, "sleep", no_sleep)

    result = asyncio.run(tools.wait_for_market_update.ainvoke({
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "poll_seconds": 0,
    }))

    assert calls == [
        {
            "symbols": ["XAUUSD"],
            "timeframes": ["M15"],
            "date_range": "1D",
            "symbol": "XAUUSD",
            "indicators": [],
            "recent_rows": 1,
            "use_cache": False,
        },
        {
            "symbols": ["XAUUSD"],
            "timeframes": ["M15"],
            "date_range": "1D",
            "symbol": "XAUUSD",
            "indicators": [],
            "recent_rows": 1,
            "use_cache": False,
        },
    ]
    assert result == {
        "success": True,
        "event": "new_candle",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "previous_candle_time": "2026-01-01T00:00:00+00:00",
        "new_candle_time": "2026-01-01T00:15:00+00:00",
    }


def test_wait_calculates_the_delay_to_the_next_candle_boundary(monkeypatch):
    tools, _ = load_tools(monkeypatch)

    delay = tools._seconds_until_next_candle(
        "2026-01-01T12:00:00+00:00",
        "H4",
        now=tools.datetime.fromisoformat("2026-01-01T12:30:00+00:00"),
    )

    assert delay == 3.5 * 60 * 60


def test_wait_only_polls_after_the_next_candle_boundary(monkeypatch):
    tools, _ = load_tools(monkeypatch)
    responses = iter((
        {"success": True, "rows": [["2026-01-01T12:00:00+00:00", 1.0]]},
        {"success": True, "rows": [["2026-01-01T16:00:00+00:00", 1.1]]},
    ))
    sleeps = []

    monkeypatch.setattr(tools, "get_compact_price_data", lambda **_kwargs: next(responses))

    async def record_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(tools.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(tools, "_seconds_until_next_candle", lambda *_args: 14_100)

    result = asyncio.run(tools.wait_for_market_update.ainvoke({
        "symbol": "XAUUSD",
        "timeframe": "H4",
    }))

    assert sleeps == [14_100]
    assert result["event"] == "new_candle"


@pytest.mark.parametrize("response", (
    {"success": False},
    {"success": True, "rows": []},
    {"success": True, "rows": [[None, 1.0]]},
))
def test_wait_returns_market_data_error_for_invalid_compact_data(monkeypatch, response):
    tools, _ = load_tools(monkeypatch)
    monkeypatch.setattr(tools, "get_compact_price_data", lambda **_kwargs: response)

    result = asyncio.run(tools.wait_for_market_update.ainvoke({
        "symbol": "XAUUSD",
        "timeframe": "M15",
    }))

    assert result["success"] is False
    assert result["event"] == "market_data_error"
    assert result["symbol"] == "XAUUSD"
    assert result["timeframe"] == "M15"
