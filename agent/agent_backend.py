import os
import uuid

from deepagents.backends import (
    CompositeBackend,
    FilesystemBackend,
    StoreBackend,
)
from langgraph.store.memory import InMemoryStore
from deepagents.backends import LangSmithSandbox
from deepagents.backends.utils import create_file_data
from dotenv import load_dotenv
from langsmith.sandbox import SandboxAuthenticationError, SandboxClient

from agent.paths import AGENT_ROOT, ENV_FILE, MEMORY_FILE, SKILLS_ROOT


# The sandbox client reads its credentials during construction. Load the
# project environment before any sandbox-related objects are created.
load_dotenv(ENV_FILE)


store = InMemoryStore()

agent_filesystem_backend = FilesystemBackend(
    root_dir=str(AGENT_ROOT)
)

skills_backend = FilesystemBackend(
    root_dir=str(SKILLS_ROOT)
)

memory_backend = StoreBackend(
    store=store,
    namespace=lambda _rt: (
        "agent",
        "memory",
    ),
)


def _create_langsmith_sandbox() -> tuple[SandboxClient, object]:
    """Create the single sandbox used by Atlas for this trader process."""
    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Atlas requires a LangSmith sandbox. Set LANGSMITH_API_KEY in .env "
            "before starting the trader."
        )

    client = SandboxClient(api_key=api_key)
    try:
        return client, client.create_sandbox()
    except SandboxAuthenticationError as exc:
        client.close()
        raise RuntimeError(
            "Unable to authenticate Atlas's LangSmith sandbox. Verify that "
            "LANGSMITH_API_KEY is valid and has sandbox access."
        ) from exc


sandbox_client, ls_sandbox = _create_langsmith_sandbox()
_sandbox_shutdown = False

sandbox_backend = LangSmithSandbox(
    sandbox=ls_sandbox
)

backend_with_sandbox = CompositeBackend(
    default=sandbox_backend,
    routes={
        "/memory/": memory_backend,
        "/skills/": skills_backend,
    },
)


backend = CompositeBackend(
    default=agent_filesystem_backend,
    routes={
        "/memory/": memory_backend,
        "/skills/": skills_backend,
    },
)


def shutdown_sandbox() -> None:
    """Delete Atlas's run-scoped sandbox and close its HTTP client once."""
    global _sandbox_shutdown

    if _sandbox_shutdown:
        return

    _sandbox_shutdown = True
    try:
        ls_sandbox.delete()
    finally:
        sandbox_client.close()

MEMORY_NAMESPACE = (
    "agent",
    "memory",
)
MEMORY_PATH = "/AGENTS.md"
_memory_seed_bytes: bytes | None = None
_memory_seed_text: str | None = None


def initialize_memory():
    """Seed the process-local memory store from the durable memory file."""
    global _memory_seed_bytes, _memory_seed_text

    existing = store.get(
        MEMORY_NAMESPACE,
        MEMORY_PATH,
    )

    if existing is not None:
        return

    memory_bytes = MEMORY_FILE.read_bytes()
    agents_md = memory_bytes.decode("utf-8")

    store.put(
        MEMORY_NAMESPACE,
        MEMORY_PATH,
        create_file_data(agents_md),
    )
    _memory_seed_bytes = memory_bytes
    _memory_seed_text = agents_md


def sync_memory() -> bool:
    """Persist changed in-memory AGENTS.md without overwriting manual edits."""
    global _memory_seed_bytes, _memory_seed_text

    if _memory_seed_bytes is None or _memory_seed_text is None:
        print("[MEMORY] Sync skipped: memory was not initialized.")
        return False

    responses = memory_backend.download_files([MEMORY_PATH])
    if len(responses) != 1:
        print("[MEMORY] Sync skipped: AGENTS.md is unavailable in the memory store.")
        return False

    response = responses[0]
    if response.error is not None or response.content is None:
        print("[MEMORY] Sync skipped: AGENTS.md is unavailable in the memory store.")
        return False

    try:
        memory_text = response.content.decode("utf-8")
    except UnicodeDecodeError:
        print("[MEMORY] Sync skipped: AGENTS.md contains non-UTF-8 content.")
        return False

    if memory_text == _memory_seed_text:
        return False

    try:
        if MEMORY_FILE.read_bytes() != _memory_seed_bytes:
            print("[MEMORY] Sync skipped: AGENTS.md was modified on disk during this run.")
            return False
    except OSError as exc:
        print(f"[MEMORY] Sync skipped: unable to verify AGENTS.md ({exc}).")
        return False

    temporary_file = MEMORY_FILE.with_name(f".{MEMORY_FILE.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_file.write_text(memory_text, encoding="utf-8")
        temporary_file.replace(MEMORY_FILE)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()

    _memory_seed_bytes = MEMORY_FILE.read_bytes()
    _memory_seed_text = memory_text
    print("[MEMORY] Persisted AGENTS.md updates.")
    return True
