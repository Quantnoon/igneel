import sys

from agent.agent_tools import (
    close_all_trades,
    close_trade,
    get_account_snapshot,
    get_open_trades,
    get_symbol_specification,
    modify_trade,
    place_trade,
    get_price_data_file
)

from agent.agent_models import get_openai_model
from agent.web_tools import fetch_url, web_search

sys.stdout.reconfigure(encoding="utf-8")

from deepagents import create_deep_agent
from agent.agent_prompts import ATLAS_SYSTEM_PROMPT, ACNOLOGIA_SYSTEM_PROMPT, IGNIA_SYSTEM_PROMPT, GRANDINE_SYSTEM_PROMPT
from agent.agent_backend import store, backend, backend_with_sandbox

model = get_openai_model("gpt-5.6-luna")

# ============================================================
# SPECIALIST DEEP AGENTS
# ============================================================

atlas_agent = create_deep_agent(
    model=model,
    system_prompt=ATLAS_SYSTEM_PROMPT,
    backend=backend_with_sandbox,
    store=store,
    memory=["/memory/AGENTS.md"],
    tools=[
        get_price_data_file,
        web_search,
        fetch_url,
    ],
)


acnologia_agent = create_deep_agent(
    model=model,
    system_prompt=ACNOLOGIA_SYSTEM_PROMPT,
    backend=backend_with_sandbox,
    store=store,
    memory=["/memory/AGENTS.md"],
    tools=[
        get_price_data_file,
        get_symbol_specification,
        web_search,
        fetch_url,
    ],
)

grandine_subagent = {
    "name": "Grandine",
    "description": (
        "Analyze each existing position for Ignia. Calculate its P/L as a "
        "percentage of account equity and, at or beyond -5% or +5%, retrieve "
        "fresh indicator-backed price data and recommend HOLD, MODIFY_ORDER, "
        "or CLOSE_ORDER. Grandine never executes broker actions."
    ),
    "system_prompt": GRANDINE_SYSTEM_PROMPT,
    "store": store,
    "memory": ["/memory/AGENTS.md"],
    "backend": backend_with_sandbox,
    "tools": [
        get_price_data_file,
        get_open_trades,
        get_account_snapshot,
        web_search,
        fetch_url,
    ],
    "model": model,
}


ignia_agent = create_deep_agent(
    model=model,
    system_prompt=IGNIA_SYSTEM_PROMPT,
    backend=backend,
    store=store,
    memory=["/memory/AGENTS.md"],
    tools=[
        get_open_trades,
        get_account_snapshot,
        modify_trade,
        place_trade,
        close_trade,
        close_all_trades,
    ],
    subagents=[grandine_subagent]
)
