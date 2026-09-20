import ast
import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langsmith.sandbox import SandboxAuthenticationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def import_backend(monkeypatch, *, api_key="sandbox-test-key", create_error=None):
    """Import the backend with a fake LangSmith client and no network access."""
    sys.modules.pop("agent.agent_backend", None)
    monkeypatch.setattr("dotenv.load_dotenv", MagicMock())

    if api_key is None:
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LANGSMITH_API_KEY", api_key)

    client = MagicMock()
    client.create_sandbox.side_effect = create_error
    client.create_sandbox.return_value = MagicMock()
    sandbox_client = MagicMock(return_value=client)
    monkeypatch.setattr("langsmith.sandbox.SandboxClient", sandbox_client)

    return importlib.import_module("agent.agent_backend"), sandbox_client, client


def test_backend_loads_environment_and_passes_langsmith_key_explicitly(monkeypatch):
    backend, sandbox_client, client = import_backend(monkeypatch)

    assert backend.load_dotenv.called
    sandbox_client.assert_called_once_with(api_key="sandbox-test-key")
    client.create_sandbox.assert_called_once_with()

    backend.shutdown_sandbox()
    client.create_sandbox.return_value.delete.assert_called_once_with()
    client.close.assert_called_once_with()


def test_backend_rejects_missing_langsmith_key_without_creating_a_sandbox(monkeypatch):
    sys.modules.pop("agent.agent_backend", None)
    monkeypatch.setattr("dotenv.load_dotenv", MagicMock())
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    sandbox_client = MagicMock()
    monkeypatch.setattr("langsmith.sandbox.SandboxClient", sandbox_client)

    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
        importlib.import_module("agent.agent_backend")

    sandbox_client.assert_not_called()


def test_backend_hides_authentication_response_details(monkeypatch):
    secret = "do-not-leak-this-key"
    error = SandboxAuthenticationError(f"401 for {secret}")

    with pytest.raises(RuntimeError) as caught:
        import_backend(monkeypatch, create_error=error)

    assert "LANGSMITH_API_KEY" in str(caught.value)
    assert secret not in str(caught.value)


def test_memory_backend_reads_the_disk_seed_without_graph_runtime(monkeypatch):
    backend, _, _ = import_backend(monkeypatch)

    backend.initialize_memory()
    result = backend.memory_backend.download_files(["/AGENTS.md"])

    assert result[0].content == backend.MEMORY_FILE.read_bytes()


def test_memory_initialization_does_not_overwrite_existing_store_value(monkeypatch):
    backend, _, _ = import_backend(monkeypatch)
    existing_memory = "Existing in-memory instruction."
    backend.store.put(
        backend.MEMORY_NAMESPACE,
        "/AGENTS.md",
        backend.create_file_data(existing_memory),
    )

    backend.initialize_memory()
    result = backend.memory_backend.download_files(["/AGENTS.md"])

    assert result[0].content.decode("utf-8") == existing_memory


def test_skill_route_lists_direct_skill_directories(monkeypatch):
    backend, _, _ = import_backend(monkeypatch)

    paths = [entry["path"] for entry in backend.backend.ls("/skills/").entries]

    assert "/skills/strategies/" in paths
    assert "/skills/technical-indicators/" in paths
    assert all(not path.startswith("/skills/skills/") for path in paths)


def test_skill_route_downloads_from_the_skill_root(monkeypatch):
    backend, _, _ = import_backend(monkeypatch)

    response = backend.backend.download_files(["/skills/technical-indicators/SKILL.md"])[0]

    assert response.error is None
    assert response.content is not None
    assert b"technical-indicators" in response.content


def test_memory_route_is_available_in_both_composite_backends(monkeypatch):
    backend, _, _ = import_backend(monkeypatch)
    backend.initialize_memory()

    for composite_backend in (backend.backend, backend.backend_with_sandbox):
        response = composite_backend.download_files(["/memory/AGENTS.md"])[0]
        assert response.error is None
        assert response.content == backend.MEMORY_FILE.read_bytes()


def initialize_temporary_memory(backend, monkeypatch, tmp_path, content="Initial memory."):
    memory_file = tmp_path / "AGENTS.md"
    memory_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(backend, "MEMORY_FILE", memory_file)
    backend.initialize_memory()
    return memory_file


def test_sync_memory_persists_a_changed_store_value(monkeypatch, tmp_path):
    backend, _, _ = import_backend(monkeypatch)
    memory_file = initialize_temporary_memory(backend, monkeypatch, tmp_path)
    changed_memory = "Improved durable memory."
    backend.store.put(
        backend.MEMORY_NAMESPACE,
        backend.MEMORY_PATH,
        backend.create_file_data(changed_memory),
    )

    assert backend.sync_memory() is True
    assert memory_file.read_text(encoding="utf-8") == changed_memory


def test_sync_memory_skips_an_unchanged_store_value(monkeypatch, tmp_path):
    backend, _, _ = import_backend(monkeypatch)
    memory_file = initialize_temporary_memory(backend, monkeypatch, tmp_path)

    assert backend.sync_memory() is False
    assert memory_file.read_text(encoding="utf-8") == "Initial memory."


def test_sync_memory_keeps_manual_disk_edits(monkeypatch, tmp_path):
    backend, _, _ = import_backend(monkeypatch)
    memory_file = initialize_temporary_memory(backend, monkeypatch, tmp_path)
    backend.store.put(
        backend.MEMORY_NAMESPACE,
        backend.MEMORY_PATH,
        backend.create_file_data("Agent update."),
    )
    memory_file.write_text("Manual disk edit.", encoding="utf-8")

    assert backend.sync_memory() is False
    assert memory_file.read_text(encoding="utf-8") == "Manual disk edit."


def test_sync_memory_rejects_non_utf8_store_content(monkeypatch, tmp_path):
    backend, _, _ = import_backend(monkeypatch)
    memory_file = initialize_temporary_memory(backend, monkeypatch, tmp_path)
    monkeypatch.setattr(
        backend.memory_backend,
        "download_files",
        lambda _: [SimpleNamespace(error=None, content=b"\xff")],
    )

    assert backend.sync_memory() is False
    assert memory_file.read_text(encoding="utf-8") == "Initial memory."


def load_agent_runner(monkeypatch, graph_error=None):
    backend = ModuleType("agent.agent_backend")
    backend.initialize_memory = MagicMock()
    backend.shutdown_sandbox = MagicMock()
    backend.sync_memory = MagicMock()

    class Graph:
        async def ainvoke(self, *_args, **_kwargs):
            if graph_error is not None:
                raise graph_error

    graph = ModuleType("agent.agent_graph")
    graph.trading_graph = Graph()
    tools = ModuleType("agent.agent_tools")
    tools.print_agent_event = MagicMock()
    tools.connect_mt5_terminal = MagicMock()

    monkeypatch.setitem(sys.modules, "agent.agent_backend", backend)
    monkeypatch.setitem(sys.modules, "agent.agent_graph", graph)
    monkeypatch.setitem(sys.modules, "agent.agent_tools", tools)
    spec = importlib.util.spec_from_file_location(
        "agent.test_agent_runner_module",
        PROJECT_ROOT / "agent" / "agent.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, backend


def test_successful_trader_run_syncs_memory(monkeypatch):
    runner, backend = load_agent_runner(monkeypatch)

    asyncio.run(runner.run_trader())

    backend.initialize_memory.assert_called_once_with()
    backend.sync_memory.assert_called_once_with()


def test_failed_trader_run_does_not_sync_memory(monkeypatch):
    runner, backend = load_agent_runner(monkeypatch, graph_error=RuntimeError("graph failed"))

    with pytest.raises(RuntimeError, match="graph failed"):
        asyncio.run(runner.run_trader())

    backend.initialize_memory.assert_called_once_with()
    backend.sync_memory.assert_not_called()


def test_atlas_uses_the_sandbox_backend_only():
    tree = ast.parse((PROJECT_ROOT / "agent" / "deep_agents.py").read_text(encoding="utf-8"))
    agent_backends = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if getattr(node.value.func, "id", None) != "create_deep_agent":
            continue
        name = getattr(node.targets[0], "id", None)
        backend = next((item.value.id for item in node.value.keywords if item.arg == "backend"), None)
        agent_backends[name] = backend

    assert agent_backends["atlas_agent"] == "backend_with_sandbox"
    assert agent_backends["acnologia_agent"] == "backend"
    assert agent_backends["ignia_agent"] == "backend"
