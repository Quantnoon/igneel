from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_relocated_entrypoints_bootstrap_package_imports_when_run_directly():
    for relative_path in (
        "agent/agent.py",
        "backtest/backtest.py",
        "live_bot/live_bot.py",
    ):
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        assert 'if __package__ in {None, ""}:' in source
        assert "project_root = Path(__file__).resolve().parent.parent" in source
        assert "sys.path.insert(0, str(project_root))" in source


def test_relocated_configs_load_the_root_environment_file():
    for relative_path in (
        "backtest/backtest_config.py",
        "live_bot/live_config.py",
        "live_bot/monitor.py",
    ):
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert 'Path(__file__).resolve().parent.parent / ".env"' in source


def test_backtest_writes_to_the_repository_webview_directory():
    source = (PROJECT_ROOT / "backtest/backtest.py").read_text(encoding="utf-8")

    assert 'Path(__file__).resolve().parent.parent / "webview" / "strategies"' in source
