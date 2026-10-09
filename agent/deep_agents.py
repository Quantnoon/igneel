import sys

from agent.agent_tools import (
    close_all_trades,
    close_trade,
    get_account_snapshot,
    get_open_trades,
    get_symbol_specification,
    modify_trade,
    place_trade,
    create_price_data_file_tool,
)

from agent.agent_models import get_openai_model
from agent.web_tools import fetch_url, web_search

sys.stdout.reconfigure(encoding="utf-8")

from deepagents import create_deep_agent
from agent.agent_prompts import ATLAS_SYSTEM_PROMPT, ACNOLOGIA_SYSTEM_PROMPT, IGNIA_SYSTEM_PROMPT, GRANDINE_SYSTEM_PROMPT
from agent.agent_backend import (
    acnologia_backend_with_sandbox,
    acnologia_sandbox_backend,
    atlas_sandbox_backend,
    backend,
    backend_with_sandbox,
    grandine_backend_with_sandbox,
    grandine_sandbox_backend,
    store,
)

model = get_openai_model()

atlas_price_data_file = create_price_data_file_tool(atlas_sandbox_backend, "atlas")
acnologia_price_data_file = create_price_data_file_tool(acnologia_sandbox_backend, "acnologia")
grandine_price_data_file = create_price_data_file_tool(grandine_sandbox_backend, "grandine")

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
        atlas_price_data_file,
        web_search,
        fetch_url,
    ],
)


acnologia_agent = create_deep_agent(
    model=model,
    system_prompt=ACNOLOGIA_SYSTEM_PROMPT,
    backend=acnologia_backend_with_sandbox,
    store=store,
    memory=["/memory/AGENTS.md"],
    tools=[
        acnologia_price_data_file,
        get_symbol_specification,
    ],
)

grandine_subagent = {
    "name": "Grandine",
    "description": (
        "Read-only position-risk specialist for Ignia. For every existing "
        "position, use fresh sandbox price analysis plus broker facts to "
        "recommend HOLD, MODIFY_ORDER, or CLOSE_ORDER. Grandine never "
        "executes broker actions."
    ),
    "system_prompt": GRANDINE_SYSTEM_PROMPT,
    "store": store,
    "memory": ["/memory/AGENTS.md"],
    "backend": grandine_backend_with_sandbox,
    "tools": [
        grandine_price_data_file,
        get_open_trades,
        get_account_snapshot,
        get_symbol_specification,
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
