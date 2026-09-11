import sys
import asyncio

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
    wait_for_market_update,
    print_agent_event
)

from agent_models import get_openai_model

sys.stdout.reconfigure(encoding="utf-8")

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from agent_prompts import MARKET_ANALYSIS_SYSTEM_PROMPT, TRADE_DECISION_SYSTEM_PROMPT, ORDER_MANAGER_SYSTEM_PROMPT

model = get_openai_model("gpt-5.6-luna")

backend = FilesystemBackend(root_dir="./agent")

# ============================================================
# SPECIALIST DEEP AGENTS
# ============================================================

market_analysis_agent = create_deep_agent(
    model=model,
    system_prompt=MARKET_ANALYSIS_SYSTEM_PROMPT,
    backend=backend,
    skills=["/skills/"],
    tools=[
        get_compact_price_data,
    ],
)


trade_decision_agent = create_deep_agent(
    model=model,
    system_prompt=TRADE_DECISION_SYSTEM_PROMPT,
    backend=backend,
    tools=[],
)


order_manager_agent = create_deep_agent(
    model=model,
    system_prompt=ORDER_MANAGER_SYSTEM_PROMPT,
    backend=backend,
    tools=[
        get_open_trades,
        get_account_snapshot,
        modify_trade,
        place_trade,
        close_trade,
        close_all_trades,
    ],
)