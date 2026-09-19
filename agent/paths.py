"""Stable filesystem locations owned by the agent package."""

from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env"
SKILLS_ROOT = AGENT_ROOT / "skills"
LARGE_TOOL_RESULTS_DIR = AGENT_ROOT / "large_tool_results"
AGENT_CONFIG_PATH = AGENT_ROOT / "agent_config.json"
AGENT_DECISIONS_LOG_PATH = AGENT_ROOT / "agent_decisions.jsonl"
AGENT_TOOL_EVENTS_LOG_PATH = AGENT_ROOT / "agent_tool_events.jsonl"
