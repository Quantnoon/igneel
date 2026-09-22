import re
from typing import Any, Literal, TypedDict

from agent.deep_agents import (
    atlas_agent,
    acnologia_agent,
    ignia_agent,
)

from agent.agent_tools import (
    VALID_TIMEFRAMES,
    get_open_trades,
    wait_for_market_update,
)


# ============================================================
# STATE
# ============================================================

class TradingState(TypedDict, total=False):
    symbol: str
    goal: str
    research_context: str

    # Market analysis
    market_analysis: str

    lot_size: float

    # Trade decision
    decision: Literal[
        "LONG",
        "SHORT",
        "WAIT",
        "NO_TRADE",
    ]
    decision_output: str
    stop_method: str
    risk_distance: float
    risk_reward_ratio: float

    # Order manager
    order_output: str

    # Monitoring
    wait_timeframe: str

    # Position state
    open_trades_exist: bool
    open_trades: list[dict[str, Any]]


# ============================================================
# HELPERS
# ============================================================

def validate_goal(value: object) -> str:
    """Return a required, normalized trading goal."""

    if not isinstance(value, str) or not (goal := value.strip()):
        raise ValueError("goal must be a non-empty trading task.")
    return goal


def extract_research_context(analysis: str, previous: str = "") -> str:
    """Keep Atlas's run-scoped approach brief between analysis cycles."""

    match = re.search(
        r"(?:^|\n)RESEARCH CONTEXT:\s*(.*?)(?=\nMARKET CONDITION:|\Z)",
        analysis,
        flags=re.IGNORECASE | re.DOTALL,
    )
    context = match.group(1).strip() if match else ""
    return context or previous

def get_last_message_content(result) -> str:
    """
    Extract the final text message from a DeepAgent result.
    """

    messages = result.get("messages", [])

    if not messages:
        return ""

    message = messages[-1]

    content = getattr(
        message,
        "content",
        "",
    )

    if isinstance(content, str):
        return content

    return str(content)


def extract_trades(result) -> list:
    """
    Normalize different possible get_open_trades
    response structures.

    Supported examples:

    {
        "success": True,
        "data": [...]
    }

    {
        "success": True,
        "data": {
            "trades": [...]
        }
    }

    {
        "trades": [...]
    }

    [...]
    """

    if isinstance(result, list):
        return result

    if not isinstance(result, dict):
        return []

    data = result.get("data")

    # data itself is a list
    if isinstance(data, list):
        return data

    # data contains a list
    if isinstance(data, dict):
        for key in (
            "trades",
            "positions",
            "open_trades",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return value

    # top-level list property
    for key in (
        "trades",
        "positions",
        "open_trades",
    ):
        value = result.get(key)

        if isinstance(value, list):
            return value

    return []


# ============================================================
# CHECK POSITION
# ============================================================

async def check_position_node(
    state: TradingState,
):
    """
    Check whether the requested symbol currently has an
    open position.

    Open position:
        -> order_manager

    No position:
        -> market_analysis
    """

    symbol = state["symbol"]

    print(
        f"\n\n[GRAPH] CHECK POSITION: {symbol}"
    )

    result = get_open_trades(
        symbol=symbol,
    )

    if (
        isinstance(result, dict)
        and result.get("success") is False
    ):
        raise RuntimeError(
            "Unable to retrieve open trades:\n"
            f"{result}"
        )

    trades = extract_trades(result)

    has_open_trades = len(trades) > 0

    print(
        f"[GRAPH] OPEN TRADES: {len(trades)}"
    )

    if has_open_trades:
        print(
            "[GRAPH] MODE: POSITION MANAGEMENT"
        )
    else:
        print(
            "[GRAPH] MODE: SEARCH FOR ENTRY"
        )

    return {
        "open_trades_exist": has_open_trades,
        "open_trades": trades,
    }


def route_position_state(
    state: TradingState,
) -> Literal[
    "order_manager",
    "market_analysis",
]:
    """
    Existing position:
        order manager

    No position:
        market analysis
    """

    if state.get(
        "open_trades_exist",
        False,
    ):
        return "order_manager"

    return "market_analysis"


# ============================================================
# MARKET ANALYSIS
# ============================================================

async def market_analysis_node(
    state: TradingState,
):
    """
    Analyze the market only when there is no currently
    open position being managed.
    """

    symbol = state["symbol"]
    goal = validate_goal(state.get("goal"))
    research_context = state.get("research_context", "")

    print(
        f"\n\n[GRAPH] ATLAS: "
        f"{symbol}"
    )

    result = await atlas_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Analyze the current market.

Symbol:
{symbol}

Goal:
{goal}

Persisted research context from prior cycles:
{research_context or "None. Research and select an approach for this run."}

There are currently no open trades requiring management.

Use the persisted approach unless its documented invalidation applies. Return
your current technical market analysis with a RESEARCH CONTEXT section.
""",
                }
            ]
        }
    )

    analysis = get_last_message_content(
        result
    )

    print(
        "\n[ATLAS RESULT]"
    )

    print(analysis)

    return {
        "market_analysis": analysis,
        "research_context": extract_research_context(analysis, research_context),
    }


# ============================================================
# TRADE DECISION
# ============================================================
import math
from typing import Any


def validate_lot_size(value: object) -> float:
    """Return one valid runtime lot size without applying a fallback."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("lot_size must be a positive finite number.")

    lot_size = float(value)
    if not math.isfinite(lot_size) or lot_size <= 0:
        raise ValueError("lot_size must be a positive finite number.")

    return lot_size


def parse_acnologia_decision(
    text: str,
    expected_lot_size: float,
) -> dict[str, Any]:
    """
    Parse Acnologia's response.

    Expected format:

    DECISION:
    LONG | SHORT | WAIT | NO_TRADE

    CONFIDENCE:
    HIGH | MODERATE | LOW

    ENTRY PRICE:
    <number> | NONE

    STOP METHOD:
    ATR | SWING | FIXED_POINTS | NONE

    STOP LOSS:
    <number> | NONE

    TAKE PROFIT:
    <number> | NONE

    RISK DISTANCE:
    <number> | NONE

    RISK REWARD RATIO:
    <number> | NONE

    LOT SIZE:
    <number> | NONE
    """

    if not text:
        raise RuntimeError(
            "Acnologia returned an empty response."
        )

    # -----------------------------
    # Decision
    # -----------------------------

    decision_match = re.search(
        r"\bDECISION\s*:\s*(NO_TRADE|LONG|SHORT|WAIT)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not decision_match:
        raise RuntimeError(
            "Acnologia did not return "
            f"a recognized DECISION.\n\n{text}"
        )

    decision = decision_match.group(1).upper()

    # -----------------------------
    # Confidence
    # -----------------------------

    confidence_match = re.search(
        r"\bCONFIDENCE\s*:\s*(HIGH|MODERATE|LOW)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not confidence_match:
        raise RuntimeError(
            "Acnologia did not return "
            f"a recognized CONFIDENCE.\n\n{text}"
        )

    confidence = confidence_match.group(1).upper()

    # -----------------------------
    # Helper
    # -----------------------------

    def parse_number(label: str):
        match = re.search(
            rf"\b{re.escape(label)}\s*:\s*(NONE|-?\d+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            raise RuntimeError(
                f"Acnologia did not return {label}.\n\n{text}"
            )

        value = match.group(1)

        if value.upper() == "NONE":
            return None

        return float(value)

    # -----------------------------
    # Execution values
    # -----------------------------

    entry_price = parse_number("ENTRY PRICE")
    stop_loss = parse_number("STOP LOSS")
    take_profit = parse_number("TAKE PROFIT")
    risk_distance = parse_number("RISK DISTANCE")
    risk_reward_ratio = parse_number("RISK REWARD RATIO")
    reported_lot_size = parse_number("LOT SIZE")

    stop_method_match = re.search(
        r"\bSTOP\s+METHOD\s*:\s*(ATR|SWING|FIXED_POINTS|NONE)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not stop_method_match:
        raise RuntimeError(f"Acnologia did not return STOP METHOD.\n\n{text}")
    stop_method = stop_method_match.group(1).upper()

    wait_timeframe_match = re.search(
        r"\bWAIT\s+TIMEFRAME\s*:\s*([A-Z0-9]+)\b",
        text,
        flags=re.IGNORECASE,
    )
    wait_timeframe = (
        wait_timeframe_match.group(1).upper()
        if wait_timeframe_match
        else "M15"
    )
    if wait_timeframe not in VALID_TIMEFRAMES:
        wait_timeframe = "M15"

    # -----------------------------
    # Validate LONG / SHORT
    # -----------------------------

    if decision in {"LONG", "SHORT"}:
        if entry_price is None:
            raise RuntimeError(
                f"{decision} requires ENTRY PRICE."
            )

        if stop_loss is None:
            raise RuntimeError(
                f"{decision} requires STOP LOSS."
            )

        if take_profit is None:
            raise RuntimeError(
                f"{decision} requires TAKE PROFIT."
            )

        if reported_lot_size is None:
            raise RuntimeError(
                f"{decision} requires LOT SIZE."
            )

        if stop_method == "NONE":
            raise RuntimeError(f"{decision} requires STOP METHOD.")

        if risk_distance is None or not math.isfinite(risk_distance) or risk_distance <= 0:
            raise RuntimeError(f"{decision} requires a positive RISK DISTANCE.")

        if risk_reward_ratio is None or not math.isfinite(risk_reward_ratio) or risk_reward_ratio <= 0:
            raise RuntimeError(f"{decision} requires a positive RISK REWARD RATIO.")

        if not math.isclose(
            reported_lot_size,
            expected_lot_size,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                "Acnologia returned a LOT SIZE that does not match the runtime lot_size."
            )
    else:
        # WAIT and NO_TRADE never reach order execution.  A model may echo the
        # supplied runtime lot size despite the output contract; normalize that
        # harmless formatting error instead of stopping the trading loop.
        reported_lot_size = None
        stop_method = "NONE"
        risk_distance = None
        risk_reward_ratio = None

    # LONG:
    # SL < ENTRY < TP
    if decision == "LONG":
        if not stop_loss < entry_price < take_profit:
            raise RuntimeError(
                "Invalid LONG trade levels: expected "
                "STOP LOSS < ENTRY PRICE < TAKE PROFIT.\n\n"
                f"SL={stop_loss}, "
                f"ENTRY={entry_price}, "
                f"TP={take_profit}"
            )

    # SHORT:
    # TP < ENTRY < SL
    if decision == "SHORT":
        if not take_profit < entry_price < stop_loss:
            raise RuntimeError(
                "Invalid SHORT trade levels: expected "
                "TAKE PROFIT < ENTRY PRICE < STOP LOSS.\n\n"
                f"TP={take_profit}, "
                f"ENTRY={entry_price}, "
                f"SL={stop_loss}"
            )

    if decision in {"LONG", "SHORT"}:
        actual_risk = abs(entry_price - stop_loss)
        actual_reward = abs(take_profit - entry_price)
        if not math.isclose(actual_risk, risk_distance, rel_tol=1e-6, abs_tol=1e-10):
            raise RuntimeError("RISK DISTANCE does not match the entry-to-stop distance.")
        if not math.isclose(actual_reward, risk_distance * risk_reward_ratio, rel_tol=1e-6, abs_tol=1e-8):
            raise RuntimeError("TAKE PROFIT does not match RISK DISTANCE multiplied by RISK REWARD RATIO.")

    return {
        "decision": decision,
        "confidence": confidence,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "lot_size": expected_lot_size if decision in {"LONG", "SHORT"} else None,
        "stop_method": stop_method,
        "risk_distance": risk_distance,
        "risk_reward_ratio": risk_reward_ratio,
        "wait_timeframe": wait_timeframe,
    }


def validate_decision_matches_atlas(analysis: str, decision: str) -> None:
    """Reject WAIT or an opposite side when Atlas supplied a qualifying bias."""
    bias_match = re.search(r"\bDIRECTIONAL\s+BIAS\s*:\s*(BULLISH|BEARISH|NEUTRAL|MIXED)\b", analysis, flags=re.IGNORECASE)
    confidence_match = re.search(r"\bCONFIDENCE\s*:\s*(HIGH|MODERATE|LOW)\b", analysis, flags=re.IGNORECASE)
    if not bias_match or not confidence_match:
        return

    bias = bias_match.group(1).upper()
    confidence = confidence_match.group(1).upper()
    qualifying_direction = (
        "LONG" if bias == "BULLISH" and confidence in {"MODERATE", "HIGH"}
        else "SHORT" if bias == "BEARISH" and confidence in {"MODERATE", "HIGH"}
        else None
    )
    if qualifying_direction and decision not in {qualifying_direction, "NO_TRADE"}:
        raise RuntimeError(f"Qualifying Atlas {bias}/{confidence} analysis requires {qualifying_direction} or NO_TRADE, not {decision}.")
    if qualifying_direction is None and decision != "WAIT":
        raise RuntimeError(f"Atlas {bias}/{confidence} analysis requires WAIT, not {decision}.")


async def trade_decision_node(state: TradingState):
    """
    Evaluate market analysis and return:

    - decision
    - confidence
    - entry price
    - stop loss
    - take profit
    - lot size
    """

    analysis = state["market_analysis"]
    goal = validate_goal(state.get("goal"))
    research_context = state.get("research_context", "")
    lot_size = validate_lot_size(state.get("lot_size"))

    print("\n\n[GRAPH] ACNOLOGIA")

    result = await acnologia_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Evaluate the following market analysis and make the final trade decision.

Goal:
{goal}

Active research context:
{research_context or "Unavailable; rely on Atlas's report."}

LOT SIZE:
{lot_size}

Use the supplied LOT SIZE exactly as provided.
Do not calculate or modify it.

Market analysis:

{analysis}
""",
                }
            ]
        }
    )

    output = get_last_message_content(result)

    trade = parse_acnologia_decision(output, lot_size)
    validate_decision_matches_atlas(analysis, trade["decision"])

    print(f"\n[ACNOLOGIA DECISION: {trade['decision']}]")
    print(f"[CONFIDENCE: {trade['confidence']}]")
    print(f"[ENTRY PRICE: {trade['entry_price']}]")
    print(f"[STOP LOSS: {trade['stop_loss']}]")
    print(f"[TAKE PROFIT: {trade['take_profit']}]")
    print(f"[LOT SIZE: {trade['lot_size']}]")
    print(f"[STOP METHOD: {trade['stop_method']}]")
    print(f"[RISK DISTANCE: {trade['risk_distance']}]")
    print(f"[RISK REWARD RATIO: {trade['risk_reward_ratio']}]")
    print(f"[WAIT TIMEFRAME: {trade['wait_timeframe']}]")

    print(output)

    return {
        "decision": trade["decision"],
        "confidence": trade["confidence"],
        "entry_price": trade["entry_price"],
        "stop_loss": trade["stop_loss"],
        "take_profit": trade["take_profit"],
        "lot_size": lot_size,
        "stop_method": trade["stop_method"],
        "risk_distance": trade["risk_distance"],
        "risk_reward_ratio": trade["risk_reward_ratio"],
        "wait_timeframe": trade["wait_timeframe"],
        "decision_output": output,
    }

def route_trade_decision(
    state: TradingState,
) -> Literal[
    "wait_market",
    "order_manager",
]:
    """
    WAIT / NO_TRADE:
        wait for fresh market data.

    LONG / SHORT:
        send to order manager.
    """

    decision = state["decision"]

    if decision in {
        "WAIT",
        "NO_TRADE",
    }:
        return "wait_market"

    if decision in {
        "LONG",
        "SHORT",
    }:
        return "order_manager"

    raise RuntimeError(
        f"Unsupported trade decision: {decision}"
    )


# ============================================================
# ORDER MANAGER
# ============================================================

async def order_manager_node(
    state: TradingState,
):
    """
    The order manager has two modes:

    1. ENTRY MODE
       Triggered by LONG or SHORT when no position exists.

    2. POSITION MANAGEMENT MODE
       Triggered because check_position found an open trade.
    """

    symbol = state["symbol"]
    goal = validate_goal(state.get("goal"))
    research_context = state.get("research_context", "")

    open_trades_exist = state.get(
        "open_trades_exist",
        False,
    )

    open_trades = state.get(
        "open_trades",
        [],
    )

    # ========================================================
    # EXISTING POSITION MANAGEMENT
    # ========================================================

    if open_trades_exist:

        print(
            f"\n\n[GRAPH] IGNIA: "
            f"MANAGE {symbol}"
        )

        result = await ignia_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"""
Manage the existing open trade or trades.

Symbol:
{symbol}

Goal:
{goal}

Active research context to pass to Grandine:
{research_context or "Unavailable"}

Trades detected by the graph:

{open_trades}

There is already open exposure on this symbol.

Do NOT search for a new trade direction.

Do NOT require a fresh LONG or SHORT signal.

Inspect the latest account state and open trades using your
available tools before taking action.

Determine whether the correct management action is:

HOLD
MODIFY_ORDER
STACK_ORDER
PARTIAL_CLOSE
CLOSE_ORDER

Evaluate applicable position-management conditions, including:

- current profit or loss;
- entry price;
- current market price;
- stop loss;
- take profit;
- break-even activation;
- trailing-stop activation;
- whether a stop should advance;
- whether the current trade should remain open;
- whether the trade should be partially or fully closed.

Never move a protective stop backwards to increase risk.

Do not submit duplicate modifications.

Do not accidentally create a duplicate position.

If no management condition has been triggered, return HOLD.

Return the action taken and the reason.
""",
                    }
                ]
            }
        )

        output = get_last_message_content(
            result
        )

        print(
            "\n[ORDER MANAGEMENT RESULT]"
        )

        print(output)

        return {
            "order_output": output,
        }

    # ========================================================
    # NEW TRADE ENTRY
    # ========================================================

    decision = state.get("decision")

    analysis = state.get(
        "market_analysis",
        "",
    )

    decision_output = state.get(
        "decision_output",
        "",
    )
    lot_size = validate_lot_size(state.get("lot_size"))

    if decision not in {
        "LONG",
        "SHORT",
    }:
        raise RuntimeError(
            "order_manager entered ENTRY MODE "
            "without LONG or SHORT."
        )

    print(
        f"\n\n[GRAPH] IGNIA: "
        f"NEW {decision} {symbol}"
    )

    result = await ignia_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Handle this approved trading opportunity.

Symbol:
{symbol}

Goal:
{goal}

Active research context:
{research_context or "Unavailable"}

Decision:
{decision}

Approved runtime lot size:
{lot_size}

Trade decision:

{decision_output}

Market analysis:

{analysis}

The graph previously detected no open trade for this symbol.

Before opening anything:

1. Inspect the account.
2. Check open trades again.
3. Confirm another trade has not appeared since the previous check.
4. Validate the intended trade parameters.
5. Validate volume, stop loss and broker requirements.
6. Execute only if the trade remains valid.

Do not accidentally duplicate an existing position.

Do not change the approved trading direction.

Use the approved runtime lot size exactly as provided. Do not calculate or
change it.

Return the action taken and relevant execution information.
""",
                }
            ]
        }
    )

    output = get_last_message_content(
        result
    )

    print(
        "\n[ORDER EXECUTION RESULT]"
    )

    print(output)

    return {
        "order_output": output,
    }


# ============================================================
# WAIT FOR MARKET UPDATE
# ============================================================

async def wait_market_node(
    state: TradingState,
):
    """
    Wait for a fresh candle.

    After this node the graph ALWAYS goes to check_position.

    It does NOT directly return to market_analysis.
    """

    symbol = state["symbol"]

    timeframe = state.get(
        "wait_timeframe",
        "M15",
    )

    print(
        f"\n\n[GRAPH] WAITING: "
        f"{symbol} {timeframe}"
    )

    result = await wait_for_market_update.ainvoke(
        {
            "symbol": symbol,
            "timeframe": timeframe,
        }
    )

    if not result.get(
        "success",
        False,
    ):
        raise RuntimeError(
            "wait_for_market_update failed:\n"
            f"{result}"
        )

    print(
        f"\n[GRAPH] NEW MARKET UPDATE: "
        f"{symbol} {timeframe}"
    )

    return {}
