from types import SimpleNamespace

import agent.agent_tools as agent_tools
from agent.paths import AGENT_TOOL_EVENTS_LOG_PATH


def test_tool_event_log_is_anchored_to_the_agent_package():
    assert agent_tools.LOG_FILE == AGENT_TOOL_EVENTS_LOG_PATH


def configure_broker(monkeypatch, calls):
    monkeypatch.setattr(
        agent_tools.mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(ask=100.0, bid=99.5),
    )
    monkeypatch.setattr(
        agent_tools.mt5,
        "symbol_info",
        lambda _symbol: SimpleNamespace(
            volume_min=0.01,
            volume_max=1.0,
            volume_step=0.01,
        ),
    )
    monkeypatch.setattr(
        agent_tools,
        "_place_order",
        lambda **kwargs: calls.setdefault("order", kwargs),
    )


def test_place_trade_normalizes_decision_and_execution_sides(monkeypatch):
    calls = {}
    configure_broker(monkeypatch, calls)

    agent_tools.place_trade("XAUUSD", "LONG", 0.25, 99.0, 101.0)
    assert calls["order"]["order_type"] == "buy"
    assert calls["order"]["price"] == 100.0
    assert calls["order"]["volume"] == 0.25

    calls.clear()
    agent_tools.place_trade("XAUUSD", "SELL", 0.25, 101.0, 99.0)
    assert calls["order"]["order_type"] == "sell"
    assert calls["order"]["price"] == 99.5


def test_place_trade_rejects_invalid_side_before_submitting(monkeypatch):
    calls = {}
    configure_broker(monkeypatch, calls)

    result = agent_tools.place_trade("XAUUSD", "hold", 0.25, 99.0, 101.0)

    assert result["success"] is False
    assert "order_type" in result["error"]["message"]
    assert calls == {}


def test_place_trade_rejects_invalid_levels_and_broker_volume(monkeypatch):
    calls = {}
    configure_broker(monkeypatch, calls)

    invalid_levels = agent_tools.place_trade("XAUUSD", "buy", 0.25, 101.0, 102.0)
    invalid_volume = agent_tools.place_trade("XAUUSD", "sell", 0.015, 101.0, 99.0)

    assert invalid_levels["success"] is False
    assert "Buy trades require" in invalid_levels["error"]["message"]
    assert invalid_volume["success"] is False
    assert "requested volume" in invalid_volume["error"]["message"]
    assert calls == {}
