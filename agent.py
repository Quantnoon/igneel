import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_tools import (
    close_all_trades,
    close_trade,
    connect_mt5_terminal,
    get_account_snapshot,
    get_compact_price_data,
    get_open_trades,
    get_price_data,
    modify_trade,
    place_trade,
    trade_execution_guard,
)
from trade_manager import load_trading_config, run_trading_loop

sys.stdout.reconfigure(encoding="utf-8")

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends.filesystem import FilesystemBackend

load_dotenv(Path(__file__).with_name(".env"))

TRADING_CONFIG = load_trading_config(Path(__file__).with_name("agent_config.json"))

research_instructions = """You are an autonomous forex trader.
Read /skills/market-data-analysis/SKILL.md and /skills/strategies/SKILL.md before
analyzing the market. The cycle context supplies `strategy`; read and use only that
strategy skill, and name it in the Market or Reason line. Do not evaluate, select,
load, or combine any other strategy. The configured strategy is the sole source of
truth for indicators, timeframes, entry, exit, risk/reward, and trade-management
decisions. The runtime supplies only account, trade, and configuration context; the
configured strategy chooses the price-data tool, lookback, timeframes, indicators,
freshness requirements, and every market-analysis report field.
Retrieve current price data before reaching a market conclusion, identifying an
entry, placing a trade, or managing an open trade. Base every decision solely on
retrieved market data and open-trade data. Do not invent prices, indicators,
account values, open trades, or claimed order outcomes. If retrieval fails, report
only the strategy's required unavailable-data values; do not list planned indicators
or timeframes as evidence and do not take a market-data-driven trade action.
For autonomous cycles, use `get_compact_price_data`; use `get_price_data` only when
the user explicitly asks for the complete raw price table. Keep the final report concise.

At the end of every cycle, return only this compact report format:

MARKET ANALYSIS
Indicators: <indicators used>
Timeframes: <timeframes used>
Market: <what the market is saying>

SIGNAL
Decision: <buy / sell / no signal>
Reason: <for no signal: actual timeframe, indicators/values or pattern, exact failed entry condition, and the concrete condition to wait for; for a signal: the evidence that qualifies it>
SL / TP / Exit: <chosen levels and exit logic, or N/A>

TRADE MANAGEMENT
Open trades: <count>
Conditions: <current trade conditions>
Action: <holding / trailing SL / closing / placing trade / no action>

Do not add any other sections. Keep factual account and open-trade context
separate from interpretation, and list action outcomes only when their tool
results confirm them. Never use vague no-signal reasons such as "clear entry",
"risk structure", "insufficient setup", or "conflicting evidence" without the
specific retrieved indicator/timeframe evidence and the condition being awaited.
"""

model = ChatOpenAI(
    model="gpt-5.6-luna",
    reasoning_effort="none",
    max_tokens=700,
    api_key=os.environ["OPENAI_API_KEY"],
)

backend = FilesystemBackend(root_dir="./agent")

agent = create_deep_agent(
    model=model,
    tools=[
        get_price_data,
        get_compact_price_data,
        place_trade,
        close_trade,
        close_all_trades,
        modify_trade,
        get_open_trades,
    ],
    system_prompt=research_instructions,
    backend=backend,
    skills=["/skills/"],
)


if __name__ == "__main__":
    try:
        connection_result = connect_mt5_terminal()
        if not connection_result.get("success", False):
            raise RuntimeError("Unable to connect to MetaTrader 5.")
        result = run_trading_loop(
            agent=agent,
            config=TRADING_CONFIG,
            account_snapshot=get_account_snapshot,
            open_trades=get_open_trades,
            execution_guard=trade_execution_guard,
            sleep=__import__("time").sleep,
        )
        print(result["reason"])
    except Exception as e:
        if "content-blocked" in str(e):
            print(e)
        else:
            raise
