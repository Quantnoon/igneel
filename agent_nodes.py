from typing import Any, Literal, TypedDict

from deep_agents import (
    market_analysis_agent,
    trade_decision_agent,
    order_manager_agent,
    wait_for_market_update,
)

from agent_tools import get_open_trades


# ============================================================
# STATE
# ============================================================

class TradingState(TypedDict, total=False):
    symbol: str
    strategy_request: str

    # Market analysis
    market_analysis: str

    # Trade decision
    decision: Literal[
        "LONG",
        "SHORT",
        "WAIT",
        "NO_TRADE",
    ]
    decision_output: str

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


import re


def parse_trade_decision(text: str) -> str:
    """
    Parse the decision from the trade-decision-agent response.

    Supports formats such as:

    DECISION: WAIT

    DECISION:
    WAIT

    DECISION : LONG
    """

    if not text:
        raise RuntimeError(
            "trade-decision-agent returned an empty response."
        )

    match = re.search(
        r"\bDECISION\s*:\s*(NO_TRADE|LONG|SHORT|WAIT)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        raise RuntimeError(
            "trade-decision-agent did not return "
            "a recognized DECISION.\n\n"
            f"{text}"
        )

    return match.group(1).upper()


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

    request = state.get(
        "strategy_request",
        "",
    )

    print(
        f"\n\n[GRAPH] MARKET ANALYSIS: "
        f"{symbol}"
    )

    result = await market_analysis_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Analyze the current market.

Symbol:
{symbol}

Trading objective:
{request}

There are currently no open trades requiring management.

Investigate the current technical market condition using your
available market-data tools and technical-indicator skill.

Return your current technical market analysis.
""",
                }
            ]
        }
    )

    analysis = get_last_message_content(
        result
    )

    print(
        "\n[MARKET ANALYSIS RESULT]"
    )

    print(analysis)

    return {
        "market_analysis": analysis,
    }


# ============================================================
# TRADE DECISION
# ============================================================

async def trade_decision_node(
    state: TradingState,
):
    """
    Convert market analysis into:

    LONG
    SHORT
    WAIT
    NO_TRADE
    """

    analysis = state["market_analysis"]

    print(
        "\n\n[GRAPH] TRADE DECISION"
    )

    result = await trade_decision_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Evaluate the following market analysis.

Return exactly one trading decision:

LONG
SHORT
WAIT
NO_TRADE

Do not force a trade.

Market analysis:

{analysis}
""",
                }
            ]
        }
    )

    output = get_last_message_content(
        result
    )

    decision = parse_trade_decision(
        output
    )

    print(
        f"\n[TRADE DECISION: {decision}]"
    )

    print(output)

    return {
        "decision": decision,
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
            f"\n\n[GRAPH] ORDER MANAGER: "
            f"MANAGE {symbol}"
        )

        result = await order_manager_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"""
Manage the existing open trade or trades.

Symbol:
{symbol}

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

    if decision not in {
        "LONG",
        "SHORT",
    }:
        raise RuntimeError(
            "order_manager entered ENTRY MODE "
            "without LONG or SHORT."
        )

    print(
        f"\n\n[GRAPH] ORDER MANAGER: "
        f"NEW {decision} {symbol}"
    )

    result = await order_manager_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Handle this approved trading opportunity.

Symbol:
{symbol}

Decision:
{decision}

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