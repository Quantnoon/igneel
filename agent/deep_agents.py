import sys

from agent.agent_tools import (
    close_all_trades,
    close_trade,
    get_account_snapshot,
    get_compact_price_data,
    get_open_trades,
    get_price_data,
    modify_trade,
    place_trade,
)

from agent.agent_models import get_openai_model
from agent.web_tools import fetch_url, web_search

sys.stdout.reconfigure(encoding="utf-8")

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from agent.agent_prompts import ATLAS_SYSTEM_PROMPT, ACNOLOGIA_SYSTEM_PROMPT, IGNIA_SYSTEM_PROMPT
from agent.paths import AGENT_ROOT

model = get_openai_model("gpt-5.6-luna")

backend = FilesystemBackend(root_dir=str(AGENT_ROOT))

# ============================================================
# SPECIALIST DEEP AGENTS
# ============================================================

atlas_agent = create_deep_agent(
    model=model,
    system_prompt=ATLAS_SYSTEM_PROMPT,
    backend=backend,
    skills=["/skills/"],
    tools=[
        get_price_data,
        web_search,
        fetch_url,
    ],
)


acnologia_agent = create_deep_agent(
    model=model,
    system_prompt=ACNOLOGIA_SYSTEM_PROMPT,
    backend=backend,
    skills=["/skills/technical-indicators/"],
    tools=[
        get_price_data
    ],
)


ignia_agent = create_deep_agent(
    model=model,
    system_prompt=IGNIA_SYSTEM_PROMPT,
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
