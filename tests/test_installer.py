from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_installer_requires_a_user_supplied_existing_mt5_terminal():
    source = (PROJECT_ROOT / "live_bot" / "installer.iss").read_text(encoding="utf-8")

    assert "TerminalPath := FindEnvValue('TERMINAL_PATH');" in source
    assert "if TerminalPath = '' then" in source
    assert "if not FileExists(TerminalPath) then" in source
    assert "TERMINAL_PATH=' + #13#10 +" in source
    assert 'TERMINAL_PATH="C:\\Program Files\\MetaTrader 5\\terminal64.exe"' not in source


def test_installer_saves_configuration_only_beside_the_installed_app():
    source = (PROJECT_ROOT / "live_bot" / "installer.iss").read_text(encoding="utf-8")

    assert "EnvPath := ExpandConstant('{app}\\.env');" in source
    assert "SaveStringToFile(EnvPath, UTF8Encode(EnvMemo.Text), False)" in source


def test_pyinstaller_build_includes_an_immediate_splash_screen():
    source = (PROJECT_ROOT / "live_bot" / "build.bat").read_text(encoding="utf-8")
    gui_source = (PROJECT_ROOT / "live_bot" / "gui.py").read_text(encoding="utf-8")

    assert (PROJECT_ROOT / "live_bot" / "igneel-splash.png").is_file()
    assert '--splash "%LIVE_BOT_DIR%igneel-splash.png"' in source
    assert "--splash-center active" in source
    assert '--add-data "%LIVE_BOT_DIR%igneel-splash.png;."' in source
    assert "pyi_splash.close()" in gui_source
