import questionary
import sys
import math
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from agent.agent_tools import connect_mt5_terminal
from agent.agent import run_trader
import asyncio
from agent.agent_backend import shutdown_sandbox

sys.stdout.reconfigure(encoding="utf-8")

STRATEGIES = {
    "SAM Strategy": "sma",
    "Trendline Strategy": "trendline",
    "doji Candlestick Strategy": "doji-candlestick-strategy",
    "liquidity Sweep": "liquidity-sweep"
}


def main():
    identifier = questionary.text(
        "Enter your unique identifier:",
        default="market"
    ).ask()

    symbol = questionary.text(
        "Select symbol:"
    ).ask()

    strategy_name = questionary.select(
        "Select strategy:",
        choices=list(STRATEGIES.keys()),
    ).ask()

    strategy_key = STRATEGIES[strategy_name]

    lot_size_text = questionary.text(
        "Enter lot size:",
        validate=lambda value: (
            True
            if is_valid_lot_size(value)
            else "Enter a valid lot size greater than 0"
        ),
    ).ask()
    lot_size = float(lot_size_text)

    config = {
        "identifier": identifier,
        "symbol": symbol,
        "strategy": strategy_key,
        "lot_size": lot_size,
    }

    print("\nConfiguration")
    print(f"Identifier: {config['identifier']}")
    print(f"Symbol:     {config['symbol']}")
    print(f"Strategy:   {strategy_name}")
    print(f"Key:        {config['strategy']}")
    print(f"Lot size:   {config['lot_size']}")

    start = questionary.confirm(
        "Start trading?",
        default=True,
    ).ask()

    if start:
        try:
            connection_result = connect_mt5_terminal()
            if not connection_result.get("success", False):
                raise RuntimeError("Unable to connect to MetaTrader 5.")

            asyncio.run(
                run_trader(
                    id=identifier,
                    symbol=symbol,
                    strategy=strategy_key,
                    lot_size=config["lot_size"],
                )
            )
        except Exception as e:
            if "content-blocked" in str(e):
                print(e)
            else:
                raise
        finally:
            shutdown_sandbox()


def is_valid_lot_size(value):
    try:
        lot_size = float(value)
        return math.isfinite(lot_size) and lot_size > 0
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
