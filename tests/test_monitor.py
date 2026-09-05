from datetime import datetime, timezone
import sys
from types import SimpleNamespace

import pytest

sys.modules.setdefault("MetaTrader5", SimpleNamespace())
import monitor


class FakeDatabase:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeAccount:
    instances = []
    account_info = {"starting_balance": 1000, "current_balance": 1000}
    error = None

    def __init__(self):
        self._db = FakeDatabase()
        self.instances.append(self)

    def get_account_info(self):
        if self.error:
            raise self.error
        return self.account_info


@pytest.fixture(autouse=True)
def monitor_dependencies(monkeypatch):
    FakeAccount.instances = []
    FakeAccount.account_info = {"starting_balance": 1000, "current_balance": 1000}
    FakeAccount.error = None
    monkeypatch.setattr(monitor, "Account", FakeAccount)
    monkeypatch.setattr(monitor, "_utc_now", lambda: datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
    monkeypatch.setattr(monitor, "open_orders", lambda **kwargs: {"success": True, "data": [], "error": None})


def config(**overrides):
    values = {
        "symbol": "EURUSD",
        "trading_sessions": [],
        "daily_dd": 0.05,
        "maximum_dd": 0.10,
        "allow_many_trades": True,
    }
    values.update(overrides)
    return values


def test_empty_sessions_allow_all_times_and_result_shape_is_exact(monkeypatch):
    monkeypatch.setattr(monitor, "_utc_now", lambda: datetime(2026, 8, 24, 23, 59, tzinfo=timezone.utc))

    assert monitor.can_trade(config()) == {
        "status": "can_trade",
        "reason": "Trading is allowed.",
    }
    assert FakeAccount.instances[0]._db.closed is True


@pytest.mark.parametrize("session,hour,minute", [
    ("asia", 0, 0),
    ("Asia", 8, 59),
    ("london", 8, 0),
    ("LONDON", 16, 59),
    ("new-york", 13, 0),
    ("New York", 21, 59),
    ("asia", 8, 30),
    ("london", 8, 30),
    ("london", 13, 30),
    ("new_york", 13, 30),
    ("london-new-york-overlap", 13, 0),
    ("London New York Overlap", 16, 59),
])
def test_named_sessions_include_starts_ends_and_overlaps(monkeypatch, session, hour, minute):
    monkeypatch.setattr(
        monitor,
        "_utc_now",
        lambda: datetime(2026, 8, 24, hour, minute, tzinfo=timezone.utc),
    )

    assert monitor.can_trade(config(trading_sessions=[session]))["status"] == "can_trade"


@pytest.mark.parametrize("session,hour", [
    ("asia", 9),
    ("london", 17),
    ("new_york", 22),
    ("london_new_york_overlap", 17),
])
def test_session_end_is_exclusive(monkeypatch, session, hour):
    monkeypatch.setattr(monitor, "_utc_now", lambda: datetime(2026, 8, 24, hour, tzinfo=timezone.utc))

    assert monitor.can_trade(config(trading_sessions=[session])) == {
        "status": "blocked",
        "reason": "Trading session is not active.",
    }


@pytest.mark.parametrize("overrides,reason", [
    ({"symbol": ""}, "Invalid bot configuration: symbol must be a non-empty string."),
    ({"trading_sessions": "asia"}, "Invalid bot configuration: trading_sessions must be a list."),
    ({"trading_sessions": ["unknown"]}, "Invalid bot configuration: Unknown trading session: unknown."),
    ({"daily_dd": -0.01}, "Invalid bot configuration: daily_dd must be a non-negative finite number."),
    ({"maximum_dd": True}, "Invalid bot configuration: maximum_dd must be a non-negative finite number."),
    ({"allow_many_trades": 1}, "Invalid bot configuration: allow_many_trades must be a boolean."),
])
def test_invalid_config_blocks_safely(overrides, reason):
    assert monitor.can_trade(config(**overrides)) == {"status": "blocked", "reason": reason}
    assert FakeAccount.instances == []


def test_missing_required_config_field_blocks_safely():
    bot_config = config()
    del bot_config["symbol"]

    assert monitor.can_trade(bot_config) == {
        "status": "blocked",
        "reason": "Invalid bot configuration: Missing required bot configuration field: symbol.",
    }


@pytest.mark.parametrize("account_info,reason", [
    ({"current_balance": 1000}, "Account balances are missing or non-numeric."),
    ({"starting_balance": "bad", "current_balance": 1000}, "Account balances are missing or non-numeric."),
    ({"starting_balance": True, "current_balance": 1000}, "Account balances are missing or non-numeric."),
    ({"starting_balance": 0, "current_balance": 1000}, "Starting balance must be greater than zero."),
    (None, "Account state is unavailable."),
])
def test_invalid_account_state_blocks_and_closes_database(account_info, reason):
    FakeAccount.account_info = account_info

    assert monitor.can_trade(config()) == {"status": "blocked", "reason": reason}
    assert FakeAccount.instances[0]._db.closed is True


def test_account_loading_failure_blocks_and_closes_database():
    FakeAccount.error = RuntimeError("database unavailable")

    assert monitor.can_trade(config()) == {
        "status": "blocked",
        "reason": "Account state could not be loaded.",
    }
    assert FakeAccount.instances[0]._db.closed is True


@pytest.mark.parametrize("balance,expected", [
    (951, {"status": "can_trade", "reason": "Trading is allowed."}),
    (950, {"status": "blocked", "reason": "Daily drawdown limit reached (5.00%)."}),
    (900, {
        "status": "blocked",
        "reason": "Daily drawdown limit reached (5.00%). Maximum drawdown limit reached (10.00%).",
    }),
])
def test_drawdown_thresholds_use_starting_balance(balance, expected):
    FakeAccount.account_info = {"starting_balance": 1000, "current_balance": balance}

    assert monitor.can_trade(config()) == expected


def test_allow_many_trades_skips_open_order_query(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("open_orders should not be called")

    monkeypatch.setattr(monitor, "open_orders", fail_if_called)

    assert monitor.can_trade(config(allow_many_trades=True))["status"] == "can_trade"


@pytest.mark.parametrize("target", ["pending", "position"])
def test_matching_pending_order_or_position_blocks(monkeypatch, target):
    monkeypatch.setattr(
        monitor,
        "open_orders",
        lambda **kwargs: {
            "success": True,
            "data": [{"symbol": "EURUSD", "target": target}],
            "error": None,
        },
    )

    assert monitor.can_trade(config(allow_many_trades=False)) == {
        "status": "blocked",
        "reason": "An order or position already exists for EURUSD.",
    }


def test_nonmatching_entries_allow_trade_and_query_requested_symbol(monkeypatch):
    calls = []

    def orders(**kwargs):
        calls.append(kwargs)
        return {"success": True, "data": [{"symbol": "GBPUSD", "target": "position"}], "error": None}

    monkeypatch.setattr(monitor, "open_orders", orders)

    assert monitor.can_trade(config(allow_many_trades=False))["status"] == "can_trade"
    assert calls == [{"symbol": "EURUSD"}]


@pytest.mark.parametrize("result", [
    {"success": False, "data": None, "error": {"message": "failed"}},
    None,
    {"success": True, "data": None, "error": None},
])
def test_open_order_query_failure_blocks(monkeypatch, result):
    monkeypatch.setattr(monitor, "open_orders", lambda **kwargs: result)

    assert monitor.can_trade(config(allow_many_trades=False)) == {
        "status": "blocked",
        "reason": "Unable to check open orders and positions.",
    }


def test_open_order_query_exception_blocks(monkeypatch):
    def raise_query_error(**kwargs):
        raise RuntimeError("terminal unavailable")

    monkeypatch.setattr(monitor, "open_orders", raise_query_error)

    assert monitor.can_trade(config(allow_many_trades=False)) == {
        "status": "blocked",
        "reason": "Unable to check open orders and positions.",
    }


def test_multiple_blockers_are_combined_in_deterministic_order(monkeypatch):
    FakeAccount.account_info = {"starting_balance": 1000, "current_balance": 800}
    monkeypatch.setattr(monitor, "_utc_now", lambda: datetime(2026, 8, 24, 23, tzinfo=timezone.utc))
    monkeypatch.setattr(
        monitor,
        "open_orders",
        lambda **kwargs: {"success": True, "data": [{"symbol": "EURUSD", "target": "pending"}], "error": None},
    )

    assert monitor.can_trade(config(trading_sessions=["asia"], allow_many_trades=False)) == {
        "status": "blocked",
        "reason": (
            "Trading session is not active. "
            "Daily drawdown limit reached (5.00%). "
            "Maximum drawdown limit reached (10.00%). "
            "An order or position already exists for EURUSD."
        ),
    }
