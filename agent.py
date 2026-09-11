import sys
import asyncio
from agent_graph import trading_graph
from agent_tools import print_agent_event, connect_mt5_terminal

sys.stdout.reconfigure(encoding="utf-8")


config = {
    "configurable": {
        "thread_id": "market-monitor",
    },
    "recursion_limit": 10000
}

async def run_trader():
    input_data = {
        "symbol": "XAUUSD",

        "strategy_request": (
            "Look for scalping opportunities "
            "on lower timeframes. "
            "use as many strategy as posible to ensure that you open a trade on every new candle"
            "Use 0.01 volume when a valid trade is approved."
        ),

        "wait_timeframe": "M5",

        # Initial graph state
        "open_trades_exist": False,
        "open_trades": [],
    }
    
    async for event in trading_graph.astream_events(
        input_data,
        config=config,
        version="v2",
    ):
        print_agent_event(event)


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

