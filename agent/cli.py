import questionary
import sys
import math
import json
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from agent.agent_tools import connect_mt5_terminal
from agent.agent import run_trader
import asyncio
from agent.agent_backend import shutdown_sandbox

sys.stdout.reconfigure(encoding="utf-8")

def main():
    identifier = questionary.text(
        "Enter your unique identifier:",
        default="market"
    ).ask()

    symbol = questionary.text(
        "Select symbol:",
        default="Volatility 10 Index"
    ).ask()

    goal = questionary.text(
        "Enter the trading goal/task:",
        default="double the account balance",
        validate=lambda value: (
            True if is_valid_goal(value) else "Enter a non-empty trading goal"
        ),
    ).ask()

    resources_text = questionary.text(
        "Enter resources as a JSON array (text and/or URLs):",
        default='["Scalp in lower timeframes"]',
        validate=lambda value: (
            True if is_valid_resources(value) else "Enter a JSON array of non-empty strings"
        ),
    ).ask()
    resources = parse_resources(resources_text)

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
        "goal": goal.strip(),
        "lot_size": lot_size,
        "resources": resources,
    }

    print("\nConfiguration")
    print(f"Identifier: {config['identifier']}")
    print(f"Symbol:     {config['symbol']}")
    print(f"Goal:       {config['goal']}")
    print(f"Lot size:   {config['lot_size']}")
    print(f"Resources:  {len(config['resources'])}")

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
                    goal=config["goal"],
                    lot_size=config["lot_size"],
                    resources=config["resources"],
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


def is_valid_goal(value):
    return isinstance(value, str) and bool(value.strip())


def parse_resources(value):
    try:
        resources = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("resources must be a JSON array of non-empty strings") from exc

    if not isinstance(resources, list):
        raise ValueError("resources must be a JSON array of non-empty strings")

    normalized = []
    for resource in resources:
        if not isinstance(resource, str) or not (cleaned := resource.strip()):
            raise ValueError("resources must be a JSON array of non-empty strings")
        normalized.append(cleaned)
    return normalized


def is_valid_resources(value):
    try:
        parse_resources(value)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    main()
