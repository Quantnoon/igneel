import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from trade_manager import TradingRunConfig


def load_agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    sys.modules.pop("agent", None)
    return importlib.import_module("agent")


def load_tools():
    sys.modules.pop("agent_tools", None)
    return importlib.import_module("agent_tools")


def test_get_price_data_passes_indicator_config_and_returns_all_candles_as_markdown(monkeypatch):
    agent = load_tools()
    captured = {}
    frame = pd.DataFrame(
        {"open": [1.0, 2.0], "close": [1.5, float("nan")]},
        index=pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"]),
    )
    frame.index.name = "time"

    class Collection:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def get_price_data(self, symbol):
            captured["requested_symbol"] = symbol
            return frame

    monkeypatch.setattr(agent, "PriceDataCollection", Collection)
    monkeypatch.setattr(agent, "is_connected", lambda: True)

    indicators = [
        {
            "indicator": "COMBINED_TREND",
            "timeframe": "H1",
            "params": {"hours": 4, "fast_span": 9, "slow_span": 50},
        }
    ]

    result = agent.get_price_data(
        ["XAUUSD", "EURUSD"], ["H1", "M15"], "2W", "XAUUSD", indicators
    )

    assert captured == {
        "symbols": ["XAUUSD", "EURUSD"],
        "timeframes": ["H1", "M15"],
        "date_range": "2W",
        "indicators": indicators,
        "requested_symbol": "XAUUSD",
    }
    assert result == "\n".join(
        [
            "| time | open | close |",
            "| --- | --- | --- |",
            "| 2026-01-01T00:00:00+00:00 | 1.0 | 1.5 |",
            "| 2026-01-01T01:00:00+00:00 | 2.0 |  |",
        ]
    )


def test_get_compact_price_data_returns_recent_json_safe_rows(monkeypatch):
    agent = load_tools()
    frame = pd.DataFrame(
        {"close": [1.0, 2.0, 3.0], "atr_M15": [float("nan"), 0.2, 0.3]},
        index=pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"]),
    )
    frame.index.name = "time"

    class Collection:
        def __init__(self, **kwargs):
            pass

        def get_price_data(self, symbol):
            return frame

    monkeypatch.setattr(agent, "PriceDataCollection", Collection)
    monkeypatch.setattr(agent, "is_connected", lambda: True)
    agent._compact_price_cache.clear()

    result = agent.get_compact_price_data(["XAUUSD"], ["M15"], "3D", "XAUUSD", [], recent_rows=2)

    assert result["success"] is True
    assert result["row_count"] == 3
    assert result["returned_rows"] == 2
    assert result["truncated"] is True
    assert result["columns"] == ["time", "close", "atr_M15"]
    assert result["latest"] == {"close": 3.0, "atr_M15": 0.3}
    assert result["rows"] == [["2026-01-01T01:00:00+00:00", 2.0, 0.2], ["2026-01-01T02:00:00+00:00", 3.0, 0.3]]


def test_get_price_data_returns_request_context_for_empty_data(monkeypatch):
    agent = load_tools()

    class Collection:
        def __init__(self, **kwargs):
            pass

        def get_price_data(self, symbol):
            return pd.DataFrame()

    monkeypatch.setattr(agent, "PriceDataCollection", Collection)
    monkeypatch.setattr(agent, "is_connected", lambda: True)

    result = agent.get_price_data(["EURUSD"], ["H1"], "10D", "EURUSD", [])

    assert result == {
        "success": False,
        "symbol": "EURUSD",
        "symbols": ["EURUSD"],
        "timeframes": ["H1"],
        "date_range": "10D",
        "error": {
            "code": None,
            "message": "No candle data is available for the requested symbol and timeframes.",
        },
    }


def test_get_price_data_rejects_malformed_indicator_schema_before_collection(monkeypatch):
    agent = load_tools()
    constructed = False

    class Collection:
        def __init__(self, **kwargs):
            nonlocal constructed
            constructed = True

    monkeypatch.setattr(agent, "PriceDataCollection", Collection)

    result = agent.get_price_data(
        ["XAUUSD"],
        ["H1"],
        "10D",
        "XAUUSD",
        [{"name": "SMA", "timeframe": "H1", "timeperiod": 50}],
    )

    assert constructed is False
    assert result["error"] == {
        "code": None,
        "stage": "indicator_validation",
        "message": "indicators[0].name is not supported; use indicators[0].indicator.",
    }


def test_get_price_data_surfaces_collection_failure_with_context(monkeypatch):
    agent = load_tools()

    class Collection:
        def __init__(self, **kwargs):
            raise KeyError("indicator")

    monkeypatch.setattr(agent, "PriceDataCollection", Collection)
    monkeypatch.setattr(agent, "is_connected", lambda: True)

    result = agent.get_price_data(
        ["XAUUSD"], ["H1"], "10D", "XAUUSD", [{"indicator": "SMA", "timeframe": "H1"}]
    )

    assert result == {
        "success": False,
        "symbol": "XAUUSD",
        "symbols": ["XAUUSD"],
        "timeframes": ["H1"],
        "date_range": "10D",
        "error": {
            "code": None,
            "stage": "collection",
            "message": "Price-data collection failed with KeyError: 'indicator'",
        },
    }


def test_dataframe_to_markdown_does_not_duplicate_existing_time_column(monkeypatch):
    agent = load_tools()
    frame = pd.DataFrame(
        {"time": ["2026-01-01T00:00:00+00:00"], "close_M15": [1.5]}
    )

    assert agent._dataframe_to_markdown(frame) == "\n".join(
        [
            "| time | close_M15 |",
            "| --- | --- |",
            "| 2026-01-01T00:00:00+00:00 | 1.5 |",
        ]
    )


def test_get_price_data_returns_request_context_when_connection_fails(monkeypatch):
    agent = load_tools()
    monkeypatch.setattr(agent, "is_connected", lambda: False)
    monkeypatch.setattr(
        agent,
        "connect_mt5_terminal",
        lambda: {"success": False, "error": {"code": 7, "message": "offline"}},
    )

    result = agent.get_price_data(["GBPUSD"], ["M5"], "1W", "GBPUSD", [])

    assert result == {
        "success": False,
        "symbol": "GBPUSD",
        "symbols": ["GBPUSD"],
        "timeframes": ["M5"],
        "date_range": "1W",
        "error": {"code": 7, "message": "offline"},
    }


def test_agent_instructions_describe_dynamic_evidence_based_forex_trading(monkeypatch):
    module = load_agent(monkeypatch)

    assert "autonomous forex trader" in module.research_instructions
    assert "/skills/market-data-analysis/SKILL.md" in module.research_instructions
    assert "current price data before" in module.research_instructions
    assert "cycle context supplies `strategy`" in module.research_instructions
    assert "Do not evaluate, select" in module.research_instructions
    assert "MARKET ANALYSIS" in module.research_instructions
    assert "SL / TP / Exit" in module.research_instructions
    assert "TRADE MANAGEMENT" in module.research_instructions
    assert "exact failed entry condition" in module.research_instructions
    assert "condition being awaited" in module.research_instructions
    assert "reply exactly \"No signal\"" not in module.research_instructions
    assert "risk structure" in module.research_instructions
    assert "INITIAL_PROMPT" not in dir(module)
    assert "ENTRY_SIGNAL" not in dir(module)
    assert "SMA(20)" not in module.research_instructions
    assert "1:3" not in module.research_instructions


def test_agent_registers_extracted_tool_functions_and_shared_execution_guard(monkeypatch):
    module = load_agent(monkeypatch)
    tools_module = importlib.import_module("agent_tools")

    assert module.get_price_data is tools_module.get_price_data
    assert module.place_trade is tools_module.place_trade
    assert module.close_trade is tools_module.close_trade
    assert module.close_all_trades is tools_module.close_all_trades
    assert module.modify_trade is tools_module.modify_trade
    assert module.get_open_trades is tools_module.get_open_trades
    assert module.trade_execution_guard is tools_module.trade_execution_guard


def test_market_data_analysis_skill_name_matches_its_directory():
    skill_path = Path("agent/skills/market-data-analysis/SKILL.md")
    name = next(
        line.removeprefix("name:").strip()
        for line in skill_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("name:")
    )

    assert name == skill_path.parent.name


def test_market_data_analysis_skill_routes_cycles_to_strategy_router():
    content = Path("agent/skills/market-data-analysis/SKILL.md").read_text(encoding="utf-8")

    assert "/skills/strategies/SKILL.md" in content
    assert "## Tool contract" in content
    assert "## Continuous trade-management cycles" in content
    assert "## Cycle decision report" in content
    assert "## Timeframe selection" not in content
    assert "## Trend workflow" not in content
    assert "stop loss" not in content
    assert "take profit" not in content
    assert "risk/reward" not in content
    assert "place_trade" not in content
    assert "modify_trade" not in content


def test_pinbar_trading_strategy_is_discoverable_and_documents_its_rules():
    skill_path = Path("agent/skills/strategies/pinbar-trading-strategy/SKILL.md")
    content = skill_path.read_text(encoding="utf-8")
    name = next(
        line.removeprefix("name:").strip()
        for line in content.splitlines()
        if line.startswith("name:")
    )

    assert name == skill_path.parent.name
    assert "higher-timeframe trend" in content
    assert "support/resistance" in content
    assert "multi-candle" in content
    assert "below the low" in content
    assert "above the high" in content
    assert "minimum 1:2 risk/reward ratio" in content
    assert "EMA_TREND" in content
    assert "SUPPORT_ZONE" in content
    assert "RESISTANCE_ZONE" in content
    assert "CDLENGULFING" in content
    assert "CDLHAMMER" in content
    assert "CDLINVERTEDHAMMER" in content
    assert "CDLSHOOTINGSTAR" in content
    assert "Do not add ATR, M5" in content
    assert "Indicators: N/A — candle retrieval failed" in content


def test_moving_average_strategy_is_discoverable_and_documents_its_rules():
    skill_path = Path("agent/skills/strategies/moving-average-trading-strategy/SKILL.md")
    content = skill_path.read_text(encoding="utf-8")
    router = Path("agent/skills/strategies/SKILL.md").read_text(encoding="utf-8")
    name = next(
        line.removeprefix("name:").strip()
        for line in content.splitlines()
        if line.startswith("name:")
    )

    assert name == skill_path.parent.name
    assert "/skills/strategies/moving-average-trading-strategy/SKILL.md" in router
    assert "cycle context supplies `strategy`" in router
    assert "read only the mapped strategy" in router
    assert "Do not combine rules" in router
    assert 'date_range: "10D"' in content
    assert "SMA(50)" in content and "SMA(200)" in content
    assert "ATR(14)" in content
    assert "at least two separate tests" in content
    assert "major H1 swing point" in content
    assert "does not use a trailing stop" in content
    assert '"indicator": "SMA"' in content
    assert '"params": {"timeperiod": 50}' in content
    assert "Use `indicator`, not `name`" in content


def test_trendline_strategy_is_discoverable_and_documents_its_rules():
    skill_path = Path("agent/skills/strategies/trendline-trading-strategy/SKILL.md")
    content = skill_path.read_text(encoding="utf-8")
    router = Path("agent/skills/strategies/SKILL.md").read_text(encoding="utf-8")
    name = next(
        line.removeprefix("name:").strip()
        for line in content.splitlines()
        if line.startswith("name:")
    )

    assert name == skill_path.parent.name
    assert "/skills/strategies/trendline-trading-strategy/SKILL.md" in router
    assert "at least two completed touches" in content
    assert "OHLC data" in content
    assert "SUPPORT_ZONE" in content and "RESISTANCE_ZONE" in content
    assert "ATR(14)" in content
    assert "M15 break-of-structure" in content
    assert "next relevant H1 swing point" in content
    assert "does not use a trailing stop" in content
    assert "one primary failed condition" in content
    assert "no configured rejection pattern" not in content
    assert "does not establish a later interaction" not in content
    assert "Fewer than two completed H1 trendline touches" in content
    assert "current price is not interacting" in content
    assert "structure has not broken" in content


def test_trade_tools_forward_existing_order_api_calls(monkeypatch):
    module = load_tools()
    calls = {}
    config = TradingRunConfig(
        symbol="XAUUSD",
        date_range="3D",
        magic=7,
        comment="test",
    )
    module.trade_execution_guard.configure(config)
    monkeypatch.setattr(module, "_place_order", lambda **kwargs: calls.setdefault("place", kwargs))
    monkeypatch.setattr(module, "_close_order", lambda *args: calls.setdefault("close", args))
    monkeypatch.setattr(module, "_close_all_order", lambda *args: calls.setdefault("close_all", args))
    monkeypatch.setattr(module, "_modify_order", lambda *args: calls.setdefault("modify", args))
    monkeypatch.setattr(module, "_open_orders", lambda **kwargs: calls.setdefault("open", kwargs))
    monkeypatch.setattr(
        module.mt5,
        "symbol_info",
        lambda symbol: SimpleNamespace(
            trade_tick_size=0.01,
            trade_tick_value=1.0,
            volume_min=0.01,
            volume_max=10.0,
            volume_step=0.01,
        ),
    )
    monkeypatch.setattr(module.mt5, "symbol_info_tick", lambda symbol: SimpleNamespace(ask=100.0, bid=99.9))

    module.place_trade("XAUUSD", "buy", 0.25, 99.0, 110.0)
    module.close_trade(1)
    module.close_all_trades(symbol="XAUUSD")
    module.modify_trade(1, sl=1990.0)
    module.get_open_trades("XAUUSD")

    assert calls["place"] == {
        "symbol": "XAUUSD", "order_type": "buy", "volume": 0.25, "price": 100.0,
        "sl": 99.0, "tp": 110.0, "magic": 7, "comment": "test",
    }
    assert calls["close"][0] == 1
    assert calls["close_all"][0] == "XAUUSD"
    assert calls["modify"][0] == 1
    assert calls["open"] == {"symbol": "XAUUSD"}


def test_place_trade_allows_a_second_xauusd_trade(monkeypatch):
    module = load_tools()
    module.trade_execution_guard.configure(
        TradingRunConfig("XAUUSD", "3D", "moving-average-trading-strategy")
    )
    calls = {}
    monkeypatch.setattr(module, "_open_orders", lambda **_: {"success": True, "data": [{"ticket": 123}]})
    monkeypatch.setattr(module, "_place_order", lambda **kwargs: calls.setdefault("place", kwargs))
    monkeypatch.setattr(module.mt5, "symbol_info_tick", lambda _: SimpleNamespace(ask=100.0, bid=99.9))
    monkeypatch.setattr(
        module.mt5,
        "symbol_info",
        lambda _: SimpleNamespace(volume_min=0.01, volume_max=10.0, volume_step=0.01),
    )

    result = module.place_trade("XAUUSD", "sell", 0.20, 101.0, 90.0)

    assert result == calls["place"]
    assert calls["place"]["volume"] == 0.20


def test_place_trade_rejects_stop_and_take_profit_on_wrong_sides(monkeypatch):
    module = load_tools()
    module.trade_execution_guard.configure(
        TradingRunConfig("XAUUSD", "3D", "moving-average-trading-strategy")
    )
    monkeypatch.setattr(module.mt5, "symbol_info_tick", lambda symbol: SimpleNamespace(ask=100.0, bid=99.9))
    monkeypatch.setattr(module.mt5, "symbol_info", lambda symbol: SimpleNamespace())

    buy = module.place_trade("XAUUSD", "buy", 0.10, 101.0, 110.0)
    sell = module.place_trade("XAUUSD", "sell", 0.10, 90.0, 101.0)

    assert buy["success"] is False and "Buy trades require" in buy["error"]["message"]
    assert sell["success"] is False and "Sell trades require" in sell["error"]["message"]


def test_place_trade_rejects_a_volume_outside_broker_constraints(monkeypatch):
    module = load_tools()
    module.trade_execution_guard.configure(TradingRunConfig("XAUUSD", "3D", "moving-average-trading-strategy"))
    monkeypatch.setattr(module.mt5, "symbol_info_tick", lambda _: SimpleNamespace(ask=100.0, bid=99.9))
    monkeypatch.setattr(
        module.mt5,
        "symbol_info",
        lambda _: SimpleNamespace(volume_min=0.01, volume_max=1.0, volume_step=0.01),
    )

    result = module.place_trade("XAUUSD", "buy", 1.01, 99.0, 110.0)

    assert result["success"] is False
    assert "requested volume" in result["error"]["message"]


def test_account_snapshot_returns_facts_or_a_structured_error(monkeypatch):
    module = load_tools()
    monkeypatch.setattr(
        module.mt5,
        "account_info",
        lambda: SimpleNamespace(balance=1000.0, equity=995.0, profit=-5.0, currency="USD"),
    )

    assert module.get_account_snapshot() == {
        "success": True,
        "data": {"balance": 1000.0, "equity": 995.0, "profit": -5.0, "currency": "USD"},
        "error": None,
    }

    monkeypatch.setattr(module.mt5, "account_info", lambda: None)
    assert module.get_account_snapshot()["success"] is False
