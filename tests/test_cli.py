import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_cli(monkeypatch):
    questionary = ModuleType("questionary")
    questionary.text = lambda *_args, **_kwargs: None
    questionary.select = lambda *_args, **_kwargs: None
    questionary.confirm = lambda *_args, **_kwargs: None

    tools = ModuleType("agent.agent_tools")
    tools.connect_mt5_terminal = lambda: {"success": True}
    runner = ModuleType("agent.agent")
    runner.run_trader = None
    backend = ModuleType("agent.agent_backend")
    backend.shutdown_sandbox = lambda: None

    monkeypatch.setitem(sys.modules, "questionary", questionary)
    monkeypatch.setitem(sys.modules, "agent.agent_tools", tools)
    monkeypatch.setitem(sys.modules, "agent.agent", runner)
    monkeypatch.setitem(sys.modules, "agent.agent_backend", backend)
    spec = importlib.util.spec_from_file_location(
        "agent.test_cli_module", PROJECT_ROOT / "agent" / "cli.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, questionary


@pytest.mark.parametrize("value", ("0.01", "1", "2.5"))
def test_cli_lot_size_validation_accepts_positive_finite_numbers(monkeypatch, value):
    cli, _ = load_cli(monkeypatch)

    assert cli.is_valid_lot_size(value) is True


@pytest.mark.parametrize(
    "value", (None, "", "abc", "0", "-0.01", "nan", "inf", "-inf")
)
def test_cli_lot_size_validation_rejects_invalid_values(monkeypatch, value):
    cli, _ = load_cli(monkeypatch)

    assert cli.is_valid_lot_size(value) is False


def test_cli_passes_converted_lot_size_to_runner(monkeypatch):
    cli, questionary = load_cli(monkeypatch)
    text_answers = iter(("test-id", "XAUUSD", "Protect capital", "0.01"))

    class Prompt:
        def __init__(self, answer):
            self.answer = answer

        def ask(self):
            return self.answer

    questionary.text = lambda *_args, **_kwargs: Prompt(next(text_answers))
    questionary.confirm = lambda *_args, **_kwargs: Prompt(True)
    captured = {}

    async def run_trader(**kwargs):
        captured.update(kwargs)

    cli.run_trader = run_trader
    cli.main()

    assert captured["lot_size"] == 0.01
    assert isinstance(captured["lot_size"], float)
    assert captured["goal"] == "Protect capital"


@pytest.mark.parametrize("value", ("Protect capital", "  Seek steady growth  "))
def test_cli_goal_validation_accepts_non_empty_text(monkeypatch, value):
    cli, _ = load_cli(monkeypatch)
    assert cli.is_valid_goal(value) is True


@pytest.mark.parametrize("value", (None, "", "   ", 1))
def test_cli_goal_validation_rejects_blank_or_non_text(monkeypatch, value):
    cli, _ = load_cli(monkeypatch)
    assert cli.is_valid_goal(value) is False
