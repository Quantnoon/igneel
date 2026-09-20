"""Stable filesystem locations owned by the agent package."""

from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env"
MEMORY_FILE = AGENT_ROOT / "memory" / "AGENTS.md"
SKILLS_ROOT = AGENT_ROOT / "skills"
LARGE_TOOL_RESULTS_DIR = AGENT_ROOT / "large_tool_results"
AGENT_TOOL_EVENTS_LOG_PATH = AGENT_ROOT / "agent_tool_events.jsonl"
