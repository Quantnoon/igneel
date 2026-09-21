import math

from agent.agent_backend import initialize_memory, sync_memory
from agent.agent_graph import trading_graph


def validate_lot_size(value: object) -> float:
    """Return a positive, finite runtime lot size."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("lot_size must be a positive finite number.")

    lot_size = float(value)
    if not math.isfinite(lot_size) or lot_size <= 0:
        raise ValueError("lot_size must be a positive finite number.")

    return lot_size


async def run_trader(id, symbol, lot_size, strategy):
    lot_size = validate_lot_size(lot_size)

    input_data = {
        "symbol": symbol,
        "goal": "Grow this account in a short period of time",
        "lot_size": lot_size,
        "strategy": strategy,
        # Initial graph state
        "open_trades_exist": False,
        "open_trades": [],
    }

    config = {
        "configurable": {
            "thread_id": id,
        },
        "recursion_limit": 10000
    }

    initialize_memory()

    await trading_graph.ainvoke(
        input_data,
        config=config,
        version="v2",
    )
    sync_memory()

