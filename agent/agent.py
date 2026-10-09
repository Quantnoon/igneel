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


def validate_resources(value: object) -> list[str]:
    """Return optional, normalized user-provided research resources."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("resources must be a list of non-empty strings.")

    normalized = []
    for resource in value:
        if not isinstance(resource, str) or not (cleaned := resource.strip()):
            raise ValueError("resources must be a list of non-empty strings.")
        normalized.append(cleaned)
    return normalized


async def run_trader(id, symbol, lot_size, goal, resources: list[str] | None = None):
    lot_size = validate_lot_size(lot_size)
    goal = validate_goal(goal)
    resources = validate_resources(resources)

    input_data = {
        "symbol": symbol,
        "goal": goal,
        "lot_size": lot_size,
        "resources": resources,
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


def validate_goal(value: object) -> str:
    """Return a required, normalized trading goal."""
    if not isinstance(value, str) or not (goal := value.strip()):
        raise ValueError("goal must be a non-empty trading task.")
    return goal

