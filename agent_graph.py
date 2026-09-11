import os

from langgraph.graph import (
    StateGraph,
    START,
)

from agent_nodes import (
    TradingState,

    check_position_node,
    route_position_state,

    market_analysis_node,

    trade_decision_node,
    route_trade_decision,

    order_manager_node,

    wait_market_node,
)


# ============================================================
# CREATE GRAPH
# ============================================================

builder = StateGraph(
    TradingState
)


# ============================================================
# NODES
# ============================================================

builder.add_node(
    "check_position",
    check_position_node,
)

builder.add_node(
    "market_analysis",
    market_analysis_node,
)

builder.add_node(
    "trade_decision",
    trade_decision_node,
)

builder.add_node(
    "order_manager",
    order_manager_node,
)

builder.add_node(
    "wait_market",
    wait_market_node,
)


# ============================================================
# START
# ============================================================

# First thing we ALWAYS do:
#
# Check whether a trade is already open.

builder.add_edge(
    START,
    "check_position",
)


# ============================================================
# CHECK POSITION ROUTING
# ============================================================

# OPEN POSITION:
#
# check_position
#     ↓
# order_manager
#
#
# NO OPEN POSITION:
#
# check_position
#     ↓
# market_analysis

builder.add_conditional_edges(
    "check_position",
    route_position_state,
    path_map={
        "order_manager": "order_manager",
        "market_analysis": "market_analysis",
    },
)


# ============================================================
# ENTRY ANALYSIS
# ============================================================

builder.add_edge(
    "market_analysis",
    "trade_decision",
)


# ============================================================
# TRADE DECISION ROUTING
# ============================================================

# WAIT / NO_TRADE
#       ↓
# wait_market
#
#
# LONG / SHORT
#       ↓
# order_manager

builder.add_conditional_edges(
    "trade_decision",
    route_trade_decision,
    path_map={
        "wait_market": "wait_market",
        "order_manager": "order_manager",
    },
)


# ============================================================
# ORDER MANAGER
# ============================================================

# Whether the manager:
#
# - opens a position;
# - holds;
# - modifies;
# - stacks;
# - partially closes;
# - closes;
#
# the next stage waits for fresh market data.

builder.add_edge(
    "order_manager",
    "wait_market",
)


# ============================================================
# FRESH MARKET DATA
# ============================================================

# IMPORTANT:
#
# NEVER:
#
# wait_market -> market_analysis
#
#
# ALWAYS:
#
# wait_market -> check_position
#
# because we must determine which mode the system
# should enter next.

builder.add_edge(
    "wait_market",
    "check_position",
)


# ============================================================
# COMPILE
# ============================================================

trading_graph = builder.compile()


# ============================================================
# GRAPH IMAGE
# ============================================================

def save_graph_image(
    path: str = "trading_graph.png",
    open_image: bool = True,
):
    png_data = (
        trading_graph
        .get_graph()
        .draw_mermaid_png()
    )

    with open(
        path,
        "wb",
    ) as file:
        file.write(
            png_data
        )

    print(
        f"[GRAPH] Image saved to {path}"
    )

    # if (
    #     open_image
    #     and hasattr(os, "startfile")
    # ):
    #     os.startfile(path)


# if __name__ == "__main__":
#     save_graph_image()