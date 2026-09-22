import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from agent.agent_prompts import (
    ACNOLOGIA_SYSTEM_PROMPT,
    ATLAS_SYSTEM_PROMPT,
    DATA_VALIDATION_CONTRACT,
    GRANDINE_SYSTEM_PROMPT,
    IGNIA_SYSTEM_PROMPT,
    MARKET_DATA_FILE_CONTRACT,
    SANDBOX_ANALYSIS_CONTRACT,
)
from agent.paths import AGENT_ROOT


def load_nodes(monkeypatch):
    agents = ModuleType("agent.deep_agents")
    agents.atlas_agent = object()
    agents.acnologia_agent = object()
    agents.ignia_agent = object()
    tools = ModuleType("agent.agent_tools")
    tools.VALID_TIMEFRAMES = {"M1", "M5", "M15", "H1", "H4", "D1", "W1"}
    tools.get_open_trades = lambda **_: {"success": True, "data": []}
    tools.wait_for_market_update = lambda *_: None
    monkeypatch.setitem(sys.modules, "agent.deep_agents", agents)
    monkeypatch.setitem(sys.modules, "agent.agent_tools", tools)
    spec = importlib.util.spec_from_file_location("agent.test_nodes", AGENT_ROOT / "agent_nodes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompts_are_goal_driven_and_preserve_specialist_boundaries():
    assert "persisted RESEARCH\nCONTEXT" in ATLAS_SYSTEM_PROMPT
    assert "strategy skill" not in ATLAS_SYSTEM_PROMPT.lower()
    assert "web_search" in ATLAS_SYSTEM_PROMPT
    assert "goal" in ACNOLOGIA_SYSTEM_PROMPT.lower()
    assert "web_search" in ACNOLOGIA_SYSTEM_PROMPT
    assert "WEB SOURCES:" in ACNOLOGIA_SYSTEM_PROMPT
    assert "goal and active research context" in IGNIA_SYSTEM_PROMPT
    assert "web_search" in GRANDINE_SYSTEM_PROMPT
    assert "WEB SOURCES:" in GRANDINE_SYSTEM_PROMPT
    assert "never place, modify,\nclose" in GRANDINE_SYSTEM_PROMPT


def test_market_data_and_sandbox_contracts_remain_detailed():
    assert "timeframes` must be a list" in MARKET_DATA_FILE_CONTRACT
    assert "Maximum date range by timeframe" in MARKET_DATA_FILE_CONTRACT
    assert "| M1 | 1D |" in MARKET_DATA_FILE_CONTRACT
    assert "| W1 | 2M |" in MARKET_DATA_FILE_CONTRACT
    assert 'timeframes: ["D1", "H4"]' in MARKET_DATA_FILE_CONTRACT
    assert "metadata including `success`, `path`" in MARKET_DATA_FILE_CONTRACT
    assert "TIMEFRAME PLAN" in MARKET_DATA_FILE_CONTRACT
    assert "open_{tf}, high_{tf}, low_{tf}, close_{tf}" in MARKET_DATA_FILE_CONTRACT
    assert "Run sandbox analysis with `python3`" in SANDBOX_ANALYSIS_CONTRACT
    assert "the `python` command is not available" in SANDBOX_ANALYSIS_CONTRACT
    assert "python3 - <<'PY'" in SANDBOX_ANALYSIS_CONTRACT
    assert "the CSV file exists and can be loaded" in DATA_VALIDATION_CONTRACT
    assert "relevant values are finite" in DATA_VALIDATION_CONTRACT

    for prompt in (ATLAS_SYSTEM_PROMPT, ACNOLOGIA_SYSTEM_PROMPT, GRANDINE_SYSTEM_PROMPT):
        assert "Maximum date range by timeframe" in prompt
        assert "Run sandbox analysis with `python3`" in prompt
        assert "python3 - <<'PY'" in prompt
        assert "relevant values are finite" in prompt


@pytest.mark.parametrize("value", (None, "", "   ", 4))
def test_goal_is_required(monkeypatch, value):
    with pytest.raises(ValueError, match="goal"):
        load_nodes(monkeypatch).validate_goal(value)


def test_research_context_is_extracted_and_preserved(monkeypatch):
    nodes = load_nodes(monkeypatch)
    analysis = """RESEARCH CONTEXT:
APPROACH: breakout
SOURCES: https://example.com
SOURCE REVIEW: FETCHED: https://example.com. SKIPPED: https://other.example - duplicate coverage.
TIMEFRAME PLAN: H4 context; H1 confirmation; M15 entry

MARKET CONDITION:
Range"""
    assert "APPROACH: breakout" in nodes.extract_research_context(analysis)
    assert "SOURCE REVIEW: FETCHED: https://example.com" in nodes.extract_research_context(analysis)
    assert "TIMEFRAME PLAN: H4 context; H1 confirmation; M15 entry" in nodes.extract_research_context(analysis)
    assert nodes.extract_research_context("MARKET CONDITION: Range", "saved") == "saved"


def test_atlas_receives_goal_and_persists_research_context(monkeypatch):
    nodes = load_nodes(monkeypatch)
    captured = {}

    class Atlas:
        async def ainvoke(self, request):
            captured.update(request)
            return {"messages": [type("Message", (), {"content": """RESEARCH CONTEXT:
APPROACH: trend following
RULES: use a trend break
SOURCES: https://example.com
INVALIDATION: range market

MARKET CONDITION:
Trending"""})()]}

    monkeypatch.setattr(nodes, "atlas_agent", Atlas())
    result = asyncio.run(nodes.market_analysis_node({"symbol": "XAUUSD", "goal": "Protect capital", "research_context": "old context"}))
    content = captured["messages"][0]["content"]
    assert "Goal:\nProtect capital" in content
    assert "old context" in content
    assert "trend following" in result["research_context"]


def test_acnologia_receives_goal_and_research_context(monkeypatch):
    nodes = load_nodes(monkeypatch)
    captured = {}

    class DecisionAgent:
        async def ainvoke(self, request):
            captured.update(request)
            return {"messages": [type("Message", (), {"content": """DECISION: WAIT
CONFIDENCE: LOW
ENTRY PRICE: NONE
STOP METHOD: NONE
STOP LOSS: NONE
TAKE PROFIT: NONE
RISK DISTANCE: NONE
RISK REWARD RATIO: NONE
LOT SIZE: NONE"""})()]}

    monkeypatch.setattr(nodes, "acnologia_agent", DecisionAgent())
    result = asyncio.run(nodes.trade_decision_node({"goal": "Protect capital", "research_context": "APPROACH: trend", "market_analysis": "analysis", "lot_size": 0.01}))
    content = captured["messages"][0]["content"]
    assert "Goal:\nProtect capital" in content
    assert "APPROACH: trend" in content
    assert result["decision"] == "WAIT"


def test_ignia_management_receives_goal_and_research_context(monkeypatch):
    nodes = load_nodes(monkeypatch)
    captured = {}

    class Ignia:
        async def ainvoke(self, request):
            captured.update(request)
            return {"messages": [type("Message", (), {"content": "managed"})()]}

    monkeypatch.setattr(nodes, "ignia_agent", Ignia())
    asyncio.run(nodes.order_manager_node({"symbol": "XAUUSD", "goal": "Protect capital", "research_context": "APPROACH: trend", "open_trades_exist": True, "open_trades": [{"ticket": 1}]}))
    content = captured["messages"][0]["content"]
    assert "Goal:\nProtect capital" in content
    assert "APPROACH: trend" in content


def test_deep_agents_grant_web_access_to_all_research_specialists():
    source = (AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8")
    assert source.count("web_search") >= 4
    assert source.count("fetch_url") >= 4


def test_decision_parser_enforces_levels_and_runtime_lot_size(monkeypatch):
    nodes = load_nodes(monkeypatch)
    valid = """DECISION: LONG
CONFIDENCE: HIGH
ENTRY PRICE: 100
STOP METHOD: ATR
STOP LOSS: 99
TAKE PROFIT: 102
RISK DISTANCE: 1
RISK REWARD RATIO: 2
LOT SIZE: 0.01
WAIT TIMEFRAME: M5"""
    assert nodes.parse_acnologia_decision(valid, 0.01)["decision"] == "LONG"
    with pytest.raises(RuntimeError, match="does not match"):
        nodes.parse_acnologia_decision(valid.replace("LOT SIZE: 0.01", "LOT SIZE: 0.02"), 0.01)
    with pytest.raises(RuntimeError, match="Invalid LONG"):
        nodes.parse_acnologia_decision(valid.replace("STOP LOSS: 99", "STOP LOSS: 101"), 0.01)


@pytest.mark.parametrize("decision", ("WAIT", "NO_TRADE"))
def test_non_trade_decision_normalizes_an_accidental_lot_size(monkeypatch, decision):
    nodes = load_nodes(monkeypatch)
    output = f"""DECISION: {decision}
CONFIDENCE: LOW
ENTRY PRICE: NONE
STOP METHOD: NONE
STOP LOSS: NONE
TAKE PROFIT: NONE
RISK DISTANCE: NONE
RISK REWARD RATIO: NONE
LOT SIZE: 0.01
WAIT TIMEFRAME: H1"""

    trade = nodes.parse_acnologia_decision(output, 0.01)

    assert trade["decision"] == decision
    assert trade["lot_size"] is None
    assert trade["wait_timeframe"] == "H1"
    assert nodes.route_trade_decision(trade) == "wait_market"


def test_acnologia_prompt_requires_none_execution_fields_for_non_trade_decisions():
    assert "For WAIT or NO_TRADE, return all execution fields as `NONE`" in ACNOLOGIA_SYSTEM_PROMPT
    assert "LOT SIZE: NONE" in ACNOLOGIA_SYSTEM_PROMPT
    assert "STOP METHOD: NONE" in ACNOLOGIA_SYSTEM_PROMPT
    assert "RISK REWARD RATIO: NONE" in ACNOLOGIA_SYSTEM_PROMPT


@pytest.mark.parametrize("stop_method", ("ATR", "SWING", "FIXED_POINTS"))
def test_decision_parser_accepts_each_supported_stop_method(monkeypatch, stop_method):
    nodes = load_nodes(monkeypatch)
    output = f"""DECISION: SHORT
CONFIDENCE: MODERATE
ENTRY PRICE: 100
STOP METHOD: {stop_method}
STOP LOSS: 101
TAKE PROFIT: 98
RISK DISTANCE: 1
RISK REWARD RATIO: 2
LOT SIZE: 0.01
WAIT TIMEFRAME: M15"""
    trade = nodes.parse_acnologia_decision(output, 0.01)

    assert trade["stop_method"] == stop_method
    assert trade["risk_distance"] == 1
    assert trade["risk_reward_ratio"] == 2


def test_decision_parser_rejects_invalid_risk_fields(monkeypatch):
    nodes = load_nodes(monkeypatch)
    output = """DECISION: LONG
CONFIDENCE: HIGH
ENTRY PRICE: 100
STOP METHOD: ATR
STOP LOSS: 99
TAKE PROFIT: 102
RISK DISTANCE: 1
RISK REWARD RATIO: 2
LOT SIZE: 0.01"""

    with pytest.raises(RuntimeError, match="RISK DISTANCE"):
        nodes.parse_acnologia_decision(output.replace("RISK DISTANCE: 1", "RISK DISTANCE: 2"), 0.01)
    with pytest.raises(RuntimeError, match="RISK REWARD RATIO"):
        nodes.parse_acnologia_decision(output.replace("RISK REWARD RATIO: 2", "RISK REWARD RATIO: 0"), 0.01)


def test_qualifying_atlas_analysis_cannot_wait_or_reverse(monkeypatch):
    nodes = load_nodes(monkeypatch)
    analysis = "DIRECTIONAL BIAS: BULLISH\nCONFIDENCE: MODERATE"

    with pytest.raises(RuntimeError, match="requires LONG or NO_TRADE, not WAIT"):
        nodes.validate_decision_matches_atlas(analysis, "WAIT")
    with pytest.raises(RuntimeError, match="requires LONG or NO_TRADE, not SHORT"):
        nodes.validate_decision_matches_atlas(analysis, "SHORT")
    nodes.validate_decision_matches_atlas(analysis, "LONG")
    nodes.validate_decision_matches_atlas(analysis, "NO_TRADE")


def test_wait_node_uses_selected_timeframe(monkeypatch):
    nodes = load_nodes(monkeypatch)
    captured = {}

    class WaitTool:
        async def ainvoke(self, payload):
            captured.update(payload)
            return {"success": True}

    monkeypatch.setattr(nodes, "wait_for_market_update", WaitTool())
    asyncio.run(nodes.wait_market_node({"symbol": "XAUUSD", "wait_timeframe": "H1"}))
    assert captured == {"symbol": "XAUUSD", "timeframe": "H1"}
