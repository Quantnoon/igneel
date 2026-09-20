import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

import asyncio

from agent.agent_backend import initialize_memory, shutdown_sandbox, sync_memory
from agent.agent_graph import trading_graph
from agent.agent_tools import print_agent_event, connect_mt5_terminal

sys.stdout.reconfigure(encoding="utf-8")


config = {
    "configurable": {
        "thread_id": "market-monitor",
    },
    "recursion_limit": 10000
}

async def run_trader():
    input_data = {
        "symbol": "BTCUSD",

        "account_setup": (
            "Use 0.01 volume when a valid trade is approved."
        ),

        # Initial graph state
        "open_trades_exist": False,
        "open_trades": [],
    }

    initialize_memory()

    await trading_graph.ainvoke(
        input_data,
        config=config,
        version="v2",
    )
    sync_memory()


if __name__ == "__main__":
    try:
        connection_result = connect_mt5_terminal()
        if not connection_result.get("success", False):
            raise RuntimeError("Unable to connect to MetaTrader 5.")

        asyncio.run(
            run_trader()
        )
    except Exception as e:
        if "content-blocked" in str(e):
            print(e)
        else:
            raise
    finally:
        shutdown_sandbox()

