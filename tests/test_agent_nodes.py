import asyncio
import importlib.util
import sys
from pathlib import Path
import re
from types import ModuleType

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
WAIT TIMEFRAME: M5""")
    short = nodes.parse_acnologia_decision("""DECISION: SHORT
CONFIDENCE: MODERATE
ENTRY PRICE: 100
STOP LOSS: 101
TAKE PROFIT: 98
LOT SIZE: 0.01
WAIT TIMEFRAME: M15""")

    assert long["decision"] == "LONG"
    assert short["decision"] == "SHORT"


def test_trade_decision_prompt_requires_no_trade_for_invalid_execution_levels():
    assert "If valid levels cannot be determined, return NO_TRADE." in ACNOLOGIA_SYSTEM_PROMPT


def test_resolve_lot_size_extracts_common_prose_formats(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    assert nodes.resolve_lot_size("Use 0.01 volume when a trade is approved.") == 0.01
    assert nodes.resolve_lot_size("Configured lot size: 0.02.") == 0.02


def test_resolve_lot_size_uses_first_explicit_value(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    assert nodes.resolve_lot_size("Use 0.01 volume normally and 0.02 lots in London.") == 0.01


def test_resolve_lot_size_falls_back_for_missing_or_invalid_values(monkeypatch):
    nodes = load_agent_nodes(monkeypatch)

    for account_setup in ("Risk 1% per trade.", "Use 0 volume.", "Use -0.01 lots.", "Use lots."):
        assert nodes.resolve_lot_size(account_setup) == 0.01


def test_trade_decision_node_accepts_prose_account_setup(monkeypatch):
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
                "account_setup": "Use 0.02 volume when a valid trade is approved.",
            }
        )
    )

    assert "LOT SIZE:\n0.02" in captured["messages"][0]["content"]
    assert result["decision"] == "NO_TRADE"
    assert result["wait_timeframe"] == "M15"


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
            {"market_analysis": "Await M5 confirmation.", "account_setup": "Use 0.01 volume."}
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

    assert nodes.parse_acnologia_decision(output)["wait_timeframe"] == "M15"
    assert nodes.parse_acnologia_decision(output + "\nWAIT TIMEFRAME: S5")["wait_timeframe"] == "M15"


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
