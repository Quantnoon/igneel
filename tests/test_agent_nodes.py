import asyncio
import importlib.util
import sys
from pathlib import Path
import re
from types import ModuleType

import pytest

from agent.agent_prompts import (
    ACNOLOGIA_SYSTEM_PROMPT,
    ATLAS_SYSTEM_PROMPT,
    GRANDINE_SYSTEM_PROMPT,
    IGNIA_SYSTEM_PROMPT,
)
from agent.paths import (
    AGENT_TOOL_EVENTS_LOG_PATH,
    AGENT_ROOT,
    LARGE_TOOL_RESULTS_DIR,
    SKILLS_ROOT,
)


def load_agent_nodes(monkeypatch):
    deep_agents = ModuleType("agent.deep_agents")
    deep_agents.atlas_agent = object()
    deep_agents.acnologia_agent = object()
    deep_agents.ignia_agent = object()
    agent_tools = ModuleType("agent.agent_tools")
    agent_tools.VALID_TIMEFRAMES = {"D1", "H4", "H1", "M15", "M5", "M1"}
    agent_tools.get_open_trades = lambda **_: {"success": True, "data": []}
    agent_tools.wait_for_market_update = lambda *_: None

    monkeypatch.setitem(sys.modules, "agent.deep_agents", deep_agents)
    monkeypatch.setitem(sys.modules, "agent.agent_tools", agent_tools)
    spec = importlib.util.spec_from_file_location(
        "agent.test_agent_nodes_module",
        AGENT_ROOT / "agent_nodes.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_input_does_not_set_wait_timeframe():
    assert '"wait_timeframe"' not in (AGENT_ROOT / "agent.py").read_text(encoding="utf-8")


def test_agent_initializes_memory_before_invoking_the_graph():
    source = (AGENT_ROOT / "agent.py").read_text(encoding="utf-8")

    assert source.index("    initialize_memory()") < source.index("    await trading_graph.ainvoke")
    assert source.index("    await trading_graph.ainvoke") < source.index("    sync_memory()")


def test_agent_runtime_paths_are_rooted_in_the_package():
    source = (AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8")

    assert AGENT_ROOT.name == "agent"
    assert SKILLS_ROOT == AGENT_ROOT / "skills"
    assert LARGE_TOOL_RESULTS_DIR == AGENT_ROOT / "large_tool_results"
    assert AGENT_TOOL_EVENTS_LOG_PATH == AGENT_ROOT / "agent_tool_events.jsonl"
    assert "from agent.agent_backend import store, backend, backend_with_sandbox" in source
    assert "backend=backend" in source
    assert "/skills/technical-indicators/SKILL.md" in ACNOLOGIA_SYSTEM_PROMPT


def test_agent_identities_are_renamed_consistently():
    source = (AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8")
    telemetry = (AGENT_ROOT / "agent_tools.py").read_text(encoding="utf-8")

    assert "You are Atlas" in ATLAS_SYSTEM_PROMPT
    assert "You are Acnologia" in ACNOLOGIA_SYSTEM_PROMPT
    assert "You are Ignia" in IGNIA_SYSTEM_PROMPT
    assert "atlas_agent = create_deep_agent" in source
    assert "acnologia_agent = create_deep_agent" in source
    assert "ignia_agent = create_deep_agent" in source
    assert all(name in telemetry for name in ("Atlas", "Acnologia", "Ignia"))


def test_atlas_prompt_uses_the_workflow_supplied_strategy_skill_path():
    assert "Strategy skill path" in ATLAS_SYSTEM_PROMPT
    assert "do not inspect, select, or combine rules from other strategy skills" in ATLAS_SYSTEM_PROMPT
    assert "/skills/strategies/doji-candlestick-strategy/SKILL.md" not in ATLAS_SYSTEM_PROMPT


def test_strategy_skill_resolver_maps_known_strategy_directories(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    for strategy in (
        "doji-candlestick-strategy",
        "trendline",
    ):
        assert nodes.resolve_strategy_skill(strategy) == (
            strategy,
            f"/skills/strategies/{strategy}/SKILL.md",
        )


@pytest.mark.parametrize("strategy", (None, "", "../sma", "sma/SKILL.md", "unknown-strategy"))
def test_strategy_skill_resolver_rejects_invalid_or_unknown_values(monkeypatch, strategy):
    nodes = load_agent_nodes(monkeypatch)

    with pytest.raises(ValueError):
        nodes.resolve_strategy_skill(strategy)


def test_market_analysis_passes_only_the_resolved_strategy_path_to_atlas(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    class Atlas:
        def __init__(self):
            self.request = None

        async def ainvoke(self, request):
            self.request = request
            message = type("Message", (), {"content": "analysis"})()
            return {"messages": [message]}

    atlas = Atlas()
    nodes.atlas_agent = atlas

    result = asyncio.run(nodes.market_analysis_node({
        "symbol": "XAUUSD",
        "strategy": "doji-candlestick-strategy",
        "strategy_request": "Analyze a setup.",
    }))

    content = atlas.request["messages"][0]["content"]
    assert result == {"market_analysis": "analysis"}
    assert "Active strategy:\ndoji-candlestick-strategy" in content
    assert "Strategy skill path:\n/skills/strategies/doji-candlestick-strategy/SKILL.md" in content
    assert "do not read or combine rules from other strategy skills" in content


def test_trade_decision_prompt_uses_bias_and_confidence_for_direction():
    prompt = ACNOLOGIA_SYSTEM_PROMPT

    assert "BULLISH with MODERATE or HIGH confidence: select LONG." in prompt
    assert "BEARISH with MODERATE or HIGH confidence: select SHORT." in prompt
    assert "NEUTRAL or MIXED bias, or LOW confidence: return WAIT." in prompt
    assert "only inputs used to select trade direction" in prompt
    assert "Do not use this data to re-evaluate the directional signal." in prompt
    assert "confirm that the setup is still valid" not in prompt


def test_trade_decision_prompt_requires_indicator_reference_for_sltp_data():
    prompt = ACNOLOGIA_SYSTEM_PROMPT

    assert "## TECHNICAL-INDICATOR REFERENCE" in prompt
    assert "/skills/technical-indicators/SKILL.md" in prompt
    assert "offset=0" in prompt and "limit=1000" in prompt
    assert "before calling `get_price_data`" in prompt
    assert "Choose only the supported technical indicators needed to calculate entry," in prompt
    assert "Do not select indicators for directional\nconfirmation" in prompt
    assert "do not read or rely on the strategy skill in this node" in prompt


def test_acnologia_has_indicator_skill_and_price_data_tool():
    source = (AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8")
    decision_agent = re.search(
        r"acnologia_agent = create_deep_agent\((.*?)\n\)",
        source,
        flags=re.DOTALL,
    ).group(1)

    assert 'skills=["/skills/technical-indicators/"]' in decision_agent
    assert "get_price_data" in decision_agent


def test_grandine_is_a_read_only_threshold_management_subagent():
    source = (AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8")
    registration = re.search(
        r"grandine_subagent = \{(.*?)\n\}",
        source,
        flags=re.DOTALL,
    ).group(1)

    assert "Analyze each existing position for Ignia" in registration
    assert 'skills": ["/skills/technical-indicators/"]' in registration
    assert all(tool in registration for tool in (
        "get_price_data",
        "get_open_trades",
        "get_account_snapshot",
    ))
    assert all(tool not in registration for tool in (
        "modify_trade",
        "close_trade",
        "place_trade",
        "close_all_trades",
    ))


def test_grandine_prompt_enforces_equity_threshold_analysis_and_safety():
    prompt = GRANDINE_SYSTEM_PROMPT

    assert "position profit / current account equity * 100" in prompt
    assert "P/L percentage <= -5%" in prompt
    assert "P/L percentage >= +5%" in prompt
    assert "/skills/technical-indicators/SKILL.md" in prompt
    assert "Call `get_price_data`" in prompt
    assert "Never recommend widening a protective\nstop" in prompt
    assert "Do not recommend new entries, reversals, stacking, partial closes" in prompt
    assert "TICKET:" in prompt
    assert "FRESH MARKET EVIDENCE:" in prompt
    assert "RECOMMENDATION:" in prompt


def test_ignia_delegates_management_analysis_and_retains_execution_control():
    prompt = IGNIA_SYSTEM_PROMPT

    assert "## GRANDINE ANALYSIS (REQUIRED)" in prompt
    assert "delegate every POSITION MANAGEMENT\nreview to Grandine" in prompt
    assert "You retain sole responsibility for broker execution." in prompt
    assert "Re-read the latest open-trade state." in prompt


def test_trade_decision_parser_accepts_qualified_long_and_short_outputs(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    long = nodes.parse_acnologia_decision("""DECISION: LONG
CONFIDENCE: HIGH
ENTRY PRICE: 100
STOP LOSS: 99
TAKE PROFIT: 102
LOT SIZE: 0.01
WAIT TIMEFRAME: M5""", 0.01)
    short = nodes.parse_acnologia_decision("""DECISION: SHORT
CONFIDENCE: MODERATE
ENTRY PRICE: 100
STOP LOSS: 101
TAKE PROFIT: 98
LOT SIZE: 0.01
WAIT TIMEFRAME: M15""", 0.01)

    assert long["decision"] == "LONG"
    assert short["decision"] == "SHORT"


def test_trade_decision_prompt_requires_no_trade_for_invalid_execution_levels():
    assert "If valid levels cannot be determined, return NO_TRADE." in ACNOLOGIA_SYSTEM_PROMPT


@pytest.mark.parametrize("value", (0.01, 1, 0.25))
def test_validate_lot_size_accepts_positive_finite_numbers(monkeypatch, value):
    nodes = load_agent_nodes(monkeypatch)

    assert nodes.validate_lot_size(value) == float(value)


@pytest.mark.parametrize("value", (None, "0.01", True, 0, -0.01, float("nan"), float("inf")))
def test_validate_lot_size_rejects_missing_or_invalid_values(monkeypatch, value):
    nodes = load_agent_nodes(monkeypatch)

    with pytest.raises(ValueError, match="lot_size"):
        nodes.validate_lot_size(value)


def test_trade_decision_parser_rejects_lot_size_that_differs_from_runtime_value(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    with pytest.raises(RuntimeError, match="does not match"):
        nodes.parse_acnologia_decision("""DECISION: LONG
CONFIDENCE: HIGH
ENTRY PRICE: 100
STOP LOSS: 99
TAKE PROFIT: 102
LOT SIZE: 0.02""", 0.01)


def test_trade_decision_node_uses_runtime_lot_size(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)
    captured = {}

    class DecisionAgent:
        async def ainvoke(self, payload):
            captured.update(payload)
            return {
                "messages": [
                    type(
                        "Message",
                        (),
                        {
                            "content": """DECISION: NO_TRADE
CONFIDENCE: LOW
ENTRY PRICE: NONE
STOP LOSS: NONE
TAKE PROFIT: NONE
LOT SIZE: NONE"""
                        },
                    )()
                ]
            }

    monkeypatch.setattr(nodes, "acnologia_agent", DecisionAgent())

    result = asyncio.run(
        nodes.trade_decision_node(
            {
                "market_analysis": "No entry signal.",
                "lot_size": 0.02,
            }
        )
    )

    assert "LOT SIZE:\n0.02" in captured["messages"][0]["content"]
    assert result["lot_size"] == 0.02
    assert result["decision"] == "NO_TRADE"
    assert result["wait_timeframe"] == "M15"


def test_trade_decision_node_rejects_invalid_lot_size_before_calling_acnologia(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    class DecisionAgent:
        def __init__(self):
            self.called = False

        async def ainvoke(self, _payload):
            self.called = True

    agent = DecisionAgent()
    monkeypatch.setattr(nodes, "acnologia_agent", agent)

    with pytest.raises(ValueError, match="lot_size"):
        asyncio.run(nodes.trade_decision_node({
            "market_analysis": "No entry signal.",
            "lot_size": 0,
        }))

    assert agent.called is False


def test_order_manager_passes_runtime_lot_size_to_ignia(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)
    captured = {}

    class Ignia:
        async def ainvoke(self, payload):
            captured.update(payload)
            message = type("Message", (), {"content": "order handled"})()
            return {"messages": [message]}

    monkeypatch.setattr(nodes, "ignia_agent", Ignia())

    asyncio.run(nodes.order_manager_node({
        "symbol": "XAUUSD",
        "open_trades_exist": False,
        "decision": "LONG",
        "lot_size": 0.02,
        "decision_output": "DECISION: LONG",
        "market_analysis": "Qualified setup.",
    }))

    content = captured["messages"][0]["content"]
    assert "Approved runtime lot size:\n0.02" in content
    assert "Use the approved runtime lot size exactly as provided." in content


def test_trade_decision_node_stores_valid_wait_timeframe(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    class DecisionAgent:
        async def ainvoke(self, _payload):
            return {
                "messages": [
                    type(
                        "Message",
                        (),
                        {
                            "content": """DECISION: WAIT
CONFIDENCE: MODERATE
ENTRY PRICE: NONE
STOP LOSS: NONE
TAKE PROFIT: NONE
LOT SIZE: NONE
WAIT TIMEFRAME: m5"""
                        },
                    )()
                ]
            }

    monkeypatch.setattr(nodes, "acnologia_agent", DecisionAgent())

    result = asyncio.run(
        nodes.trade_decision_node(
            {"market_analysis": "Await M5 confirmation.", "lot_size": 0.01}
        )
    )

    assert result["wait_timeframe"] == "M5"


def test_parse_acnologia_decision_falls_back_for_missing_or_unsupported_wait_timeframe(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)
    output = """DECISION: NO_TRADE
CONFIDENCE: LOW
ENTRY PRICE: NONE
STOP LOSS: NONE
TAKE PROFIT: NONE
LOT SIZE: NONE"""

    assert nodes.parse_acnologia_decision(output, 0.01)["wait_timeframe"] == "M15"
    assert nodes.parse_acnologia_decision(output + "\nWAIT TIMEFRAME: S5", 0.01)["wait_timeframe"] == "M15"


def test_wait_market_node_uses_state_timeframe(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)
    captured = {}

    class WaitTool:
        async def ainvoke(self, payload):
            captured.update(payload)
            return {"success": True}

    monkeypatch.setattr(nodes, "wait_for_market_update", WaitTool())

    asyncio.run(nodes.wait_market_node({"symbol": "XAUUSD", "wait_timeframe": "H1"}))

    assert captured == {"symbol": "XAUUSD", "timeframe": "H1"}
