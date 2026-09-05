import importlib
import sys
from collections import namedtuple

import pytest


@pytest.fixture
def connection(monkeypatch):
    class FakeMT5:
        def __init__(self):
            self.initialize_calls = []
            self.initialized = True
            self.account = None
            self.terminal = None
            self.diagnostic = (0, "")
            self.raise_on = None

        def initialize(self, *args, **kwargs):
            self.initialize_calls.append((args, kwargs))
            if self.raise_on == "initialize":
                raise RuntimeError("connection failed")
            return self.initialized

        def account_info(self):
            if self.raise_on == "account_info":
                raise RuntimeError("metadata failed")
            return self.account

        def terminal_info(self):
            if self.raise_on == "terminal_info":
                raise RuntimeError("metadata failed")
            return self.terminal

        def last_error(self):
            return self.diagnostic

    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    sys.modules.pop("connection", None)
    module = importlib.import_module("connection")
    return module, fake


def details(**overrides):
    values = {"login": 123, "password": "secret", "server": "Demo"}
    values.update(overrides)
    return values


def test_success_converts_namedtuples(connection):
    module, fake = connection
    Account = namedtuple("Account", "login balance")
    Terminal = namedtuple("Terminal", "connected build")
    fake.account = Account(123, 1000.5)
    fake.terminal = Terminal(True, 4000)

    result = module.connect(details())

    assert result == {
        "success": True,
        "account_info": {"login": 123, "balance": 1000.5},
        "terminal_info": {"connected": True, "build": 4000},
        "error": None,
    }
    assert fake.initialize_calls == [((), {"login": 123, "password": "secret", "server": "Demo"})]


def test_forwards_path_and_optional_arguments_and_ignores_unknown(connection):
    module, fake = connection
    fake.account = {}
    fake.terminal = {}

    result = module.connect(details(path="terminal.exe", timeout=10, portable=True, ignored="value"))

    assert result["success"] is True
    assert fake.initialize_calls == [(
        ("terminal.exe",),
        {"login": 123, "password": "secret", "server": "Demo", "timeout": 10, "portable": True},
    )]


@pytest.mark.parametrize("value, message", [
    (None, "account_details must be a dictionary."),
    ({"password": "x", "server": "s"}, "Missing required account field: login."),
    (details(login=True), "login must be an integer."),
    (details(password=""), "password must be a non-empty string."),
    (details(server=1), "server must be a non-empty string."),
    (details(path=""), "path must be a non-empty string when supplied."),
    (details(path=None), "path must be a non-empty string when supplied."),
    (details(timeout=0), "timeout must be a positive integer when supplied."),
    (details(timeout=None), "timeout must be a positive integer when supplied."),
    (details(timeout=True), "timeout must be a positive integer when supplied."),
    (details(portable=None), "portable must be a boolean when supplied."),
    (details(portable=1), "portable must be a boolean when supplied."),
])
def test_validation_returns_stable_failure_without_mt5_call(connection, value, message):
    module, fake = connection

    result = module.connect(value)

    assert result == {"success": False, "account_info": None, "terminal_info": None,
                      "error": {"code": None, "message": message}}
    assert fake.initialize_calls == []


def test_initialize_failure_normalizes_last_error_and_does_not_expose_password(connection):
    module, fake = connection
    fake.initialized = False
    fake.diagnostic = (100, "login 123 rejected for Demo using secret")

    result = module.connect(details())

    assert result["success"] is False
    assert result["error"] == {
        "code": 100,
        "message": "login [REDACTED] rejected for [REDACTED] using [REDACTED]",
    }
    assert "secret" not in str(result)


@pytest.mark.parametrize("diagnostic", [None, "unexpected", (True, ""), ("bad", 1)])
def test_initialize_failure_falls_back_for_unexpected_diagnostic(connection, diagnostic):
    module, fake = connection
    fake.initialized = False
    fake.diagnostic = diagnostic

    result = module.connect(details())

    assert result["error"] == {"code": None, "message": "MetaTrader 5 initialization failed."}


def test_mt5_exception_returns_normalized_failure(connection):
    module, fake = connection
    fake.raise_on = "initialize"

    result = module.connect(details())

    assert result == {"success": False, "account_info": None, "terminal_info": None,
                      "error": {"code": None, "message": "MetaTrader 5 operation failed unexpectedly."}}


def test_metadata_exception_returns_normalized_failure(connection):
    module, fake = connection
    fake.raise_on = "account_info"

    result = module.connect(details())

    assert result == {"success": False, "account_info": None, "terminal_info": None,
                      "error": {"code": None, "message": "MetaTrader 5 operation failed unexpectedly."}}


@pytest.mark.parametrize("missing", ["account_info", "terminal_info"])
def test_partial_metadata_success_includes_latest_diagnostic(connection, missing):
    module, fake = connection
    fake.account = {} if missing != "account_info" else None
    fake.terminal = {} if missing != "terminal_info" else None
    fake.diagnostic = (42, "metadata unavailable")

    result = module.connect(details())

    assert result["success"] is True
    assert result["account_info"] == fake.account
    assert result["terminal_info"] == fake.terminal
    assert result["error"] == {"code": 42, "message": "metadata unavailable"}
