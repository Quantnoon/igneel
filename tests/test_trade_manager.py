import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from trade_manager import (
    TradeExecutionGuard,
    TradingRunConfig,
    append_decision_log,
    load_trading_config,
    run_trading_loop,
)


def config():
    return TradingRunConfig(
        symbol="XAUUSD",
        date_range="3D",
        strategy="moving-average-trading-strategy",
        poll_seconds=60,
        decision_log="agent_decisions.jsonl",
    )


def test_execution_guard_blocks_unconfigured_and_wrong_symbol_entries():
    guard = TradeExecutionGuard()
    assert guard.placement_error("XAUUSD") == "Trading has not been configured."

    guard.configure(config())
    assert guard.placement_error("EURUSD") == "Trades may only be placed for the configured symbol."
    assert guard.placement_error("XAUUSD") is None


def test_trendline_strategy_is_a_supported_runtime_configuration():
    config = TradingRunConfig("XAUUSD", "3D", "trendline-trading-strategy")

    assert config.strategy == "trendline-trading-strategy"


def test_load_trading_config_validates_required_fields_and_values(tmp_path):
    path = tmp_path / "agent_config.json"
    path.write_text(
        json.dumps(
            {
                "symbol": "EURUSD", "date_range": "2W", "strategy": "moving-average-trading-strategy", "magic": 7, "comment": "test",
                "poll_seconds": 30, "decision_log": "decisions.jsonl",
            }
        ),
        encoding="utf-8",
    )

    assert load_trading_config(path) == TradingRunConfig(
        symbol="EURUSD", date_range="2W", strategy="moving-average-trading-strategy", poll_seconds=30, decision_log="decisions.jsonl", magic=7, comment="test"
    )

    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="symbol"):
        load_trading_config(path)

    path.write_text('{"symbol":"EURUSD","date_range":"2W","strategy":"moving-average-trading-strategy","magic":0,"comment":"x","poll_seconds":30}', encoding="utf-8")
    with pytest.raises(ValueError, match="decision_log"):
        load_trading_config(path)

    path.write_text('{"symbol":"EURUSD","date_range":"2W","strategy":"moving-average-trading-strategy","magic":0,"comment":"x","poll_seconds":0,"decision_log":"x.jsonl"}', encoding="utf-8")
    with pytest.raises(ValueError, match="poll_seconds"):
        load_trading_config(path)

    path.write_text('{"symbol":"EURUSD","date_range":"tomorrow","strategy":"moving-average-trading-strategy","magic":0,"comment":"x","poll_seconds":30,"decision_log":"x.jsonl"}', encoding="utf-8")
    with pytest.raises(ValueError, match="date_range"):
        load_trading_config(path)

    path.write_text('{"symbol":"EURUSD","date_range":"2W","strategy":"unknown","magic":0,"comment":"x","poll_seconds":30,"decision_log":"x.jsonl"}', encoding="utf-8")
    with pytest.raises(ValueError, match="strategy"):
        load_trading_config(path)

    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="configuration JSON"):
        load_trading_config(path)


class FakeAgent:
    def __init__(self):
        self.prompts = []

    def invoke(self, payload):
        self.prompts.append(payload["messages"][0]["content"])
        return {
            "messages": [
                SimpleNamespace(tool_calls=[{"id": "call-1", "name": "place_trade", "args": {"volume": 0.1}}]),
                SimpleNamespace(tool_call_id="call-1", name="place_trade", content='{"success": true}'),
                SimpleNamespace(
                    content=(
                        "MARKET ANALYSIS\nIndicators: EMA\nTimeframes: H1\nMarket: mixed\n\n"
                        "SIGNAL\nDecision: no signal\nReason: M15 RSI is falling below 50; wait for an M15 RSI turn above 50.\nSL / TP / Exit: N/A\n\n"
                        "TRADE MANAGEMENT\nOpen trades: 0\nConditions: none\nAction: no action"
                    )
                ),
            ]
        }


def test_loop_emits_no_signal_cycle_sleeps_and_stops_cleanly():
    agent = FakeAgent()
    guard = TradeExecutionGuard()
    emitted = []
    sleep_calls = []
    records = []

    def stop_after_first_sleep(seconds):
        sleep_calls.append(seconds)
        raise KeyboardInterrupt

    result = run_trading_loop(
        agent=agent,
        config=config(),
        account_snapshot=lambda: {"success": True, "data": {"balance": 1000, "equity": 995, "profit": -5}},
        open_trades=lambda symbol: {"success": True, "data": []},
        execution_guard=guard,
        sleep=stop_after_first_sleep,
        audit_log_writer=lambda path, record: records.append((path, record)),
        emit=emitted.append,
    )

    assert result == {"status": "stopped", "reason": "Trading loop stopped by user."}
    assert sleep_calls == [60]
    assert len(agent.prompts) == 1
    assert "symbol=XAUUSD; date_range=3D; strategy=moving-average-trading-strategy" in agent.prompts[0]
    assert "entry_signal" not in agent.prompts[0]
    assert "initial" not in agent.prompts[0].lower()
    assert "reply exactly 'No signal'" not in agent.prompts[0]
    assert "account_snapshot={'success': True" in agent.prompts[0]
    assert len(records) == 1
    assert records[0][0] == "agent_decisions.jsonl"
    assert records[0][1]["strategy"] == "moving-average-trading-strategy"
    assert records[0][1]["tool_events"][0]["name"] == "place_trade"
    assert records[0][1]["tool_events"][1]["content"] == '{"success": true}'
    assert "MARKET ANALYSIS" in emitted[0]
    assert "SIGNAL" in emitted[0]
    assert "TRADE MANAGEMENT" in emitted[0]
    assert "Account snapshot" not in emitted[0]
    assert "Actual tool events" not in emitted[0]
    assert "{" not in emitted[0]
    assert guard.config is None


def test_loop_invokes_strategy_owned_analysis_on_every_poll():
    agent = FakeAgent()
    guard = TradeExecutionGuard()
    emitted = []
    calls = 0

    def sleep_twice(seconds):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt

    run_trading_loop(
        agent=agent,
        config=config(),
        account_snapshot=lambda: {"success": True, "data": {}},
        open_trades=lambda symbol: {"success": True, "data": []},
        execution_guard=guard,
        sleep=sleep_twice,
        audit_log_writer=lambda path, record: None,
        emit=emitted.append,
        now=lambda: datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )

    assert len(agent.prompts) == 2
    assert "M15" not in agent.prompts[0]
    assert "H1" not in agent.prompts[0]
    assert "price-data tool choice" in agent.prompts[0]
    assert "no new completed M15 candle" not in emitted[1]


def test_append_decision_log_appends_valid_json_lines(tmp_path):
    path = tmp_path / "audit" / "decisions.jsonl"
    append_decision_log(path, {"cycle": 1, "report": "No signal"})
    append_decision_log(path, {"cycle": 2, "report": "Placed trade"})

    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == [
        {"cycle": 1, "report": "No signal"},
        {"cycle": 2, "report": "Placed trade"},
    ]
