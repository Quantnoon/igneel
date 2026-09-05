import importlib
import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def order(monkeypatch):
    class FakeMT5:
        TRADE_ACTION_DEAL = 1
        TRADE_ACTION_PENDING = 2
        TRADE_ACTION_MODIFY = 3
        TRADE_ACTION_SLTP = 4
        TRADE_ACTION_REMOVE = 5
        ORDER_TYPE_BUY = 10
        ORDER_TYPE_SELL = 11
        ORDER_TYPE_BUY_LIMIT = 12
        ORDER_TYPE_SELL_LIMIT = 13
        ORDER_TYPE_BUY_STOP = 14
        ORDER_TYPE_SELL_STOP = 15
        POSITION_TYPE_BUY = 10
        POSITION_TYPE_SELL = 11
        ORDER_TIME_GTC = 20
        ORDER_TIME_DAY = 21
        ORDER_TIME_SPECIFIED = 22
        ORDER_TIME_SPECIFIED_DAY = 23
        ORDER_FILLING_FOK = 30
        ORDER_FILLING_IOC = 31
        ORDER_FILLING_RETURN = 32
        TRADE_RETCODE_PLACED = 100
        TRADE_RETCODE_DONE = 101
        TRADE_RETCODE_DONE_PARTIAL = 102

        def __init__(self):
            self.tick = Tick(1.1, 1.2)
            self.orders = ()
            self.positions = ()
            self.deals = ()
            self.check = Check(0, "ok", {"nested": [Request("EURUSD")]})
            self.send = Result(self.TRADE_RETCODE_DONE, "done", Request("EURUSD"))
            self.diagnostic = (500, "terminal error")
            self.check_calls = []
            self.send_calls = []
            self.orders_calls = []
            self.positions_calls = []
            self.history_calls = []
            self.profit_calls = []
            self.raise_on = None

        def symbol_info_tick(self, symbol):
            if self.raise_on == "tick": raise RuntimeError("boom")
            return self.tick

        def order_check(self, request):
            self.check_calls.append(request)
            if self.raise_on == "check": raise RuntimeError("boom")
            return self.check

        def order_send(self, request):
            self.send_calls.append(request)
            if self.raise_on == "send": raise RuntimeError("boom")
            return self.send

        def orders_get(self, **kwargs):
            self.orders_calls.append(kwargs)
            if self.raise_on == "orders": raise RuntimeError("boom")
            return self.orders

        def positions_get(self, **kwargs):
            self.positions_calls.append(kwargs)
            if self.raise_on == "positions": raise RuntimeError("boom")
            return self.positions

        def history_deals_get(self, *args, **kwargs):
            self.history_calls.append((args, kwargs))
            if self.raise_on == "history": raise RuntimeError("boom")
            return self.deals

        def order_calc_profit(self, *args):
            self.profit_calls.append(args)
            return None if self.raise_on == "profit_none" else 42.5

        def last_error(self):
            return self.diagnostic

    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    sys.modules.pop("order", None)
    return importlib.import_module("order"), fake


Tick = namedtuple("Tick", "bid ask")
Request = namedtuple("Request", "symbol")
Check = namedtuple("Check", "retcode comment request")
Result = namedtuple("Result", "retcode comment request")
Position = namedtuple("Position", "ticket symbol type volume price_open sl tp magic")
Pending = namedtuple("Pending", "ticket symbol price_open sl tp type_time time_expiration magic")
Deal = namedtuple("Deal", "ticket order symbol request")


@pytest.mark.parametrize("kind,expected_type,expected_price", [("buy", 10, 1.2), ("sell", 11, 1.1)])
def test_place_instant_uses_current_side_quote(order, kind, expected_type, expected_price):
    module, fake = order
    result = module.place_order("EURUSD", kind, 0.1)
    request = fake.check_calls[0]
    assert result["success"] is True
    assert request == fake.send_calls[0]
    assert request["action"] == fake.TRADE_ACTION_DEAL
    assert request["type"] == expected_type
    assert request["price"] == expected_price
    assert request["type_time"] == fake.ORDER_TIME_GTC
    assert request["type_filling"] == fake.ORDER_FILLING_RETURN
    assert result["data"]["check"]["request"]["nested"][0] == {"symbol": "EURUSD"}


@pytest.mark.parametrize("kind,constant", [("buy_limit", 12), ("sell_limit", 13), ("buy_stop", 14), ("sell_stop", 15)])
def test_place_pending_maps_all_supported_types(order, kind, constant):
    module, fake = order
    result = module.place_order("EURUSD", kind, 1, price=1.15, sl=1.0, tp=1.3,
                                type_time="day", type_filling="ioc", deviation=3,
                                magic=9, comment="test")
    request = fake.send_calls[0]
    assert result["success"] is True
    assert request["action"] == fake.TRADE_ACTION_PENDING
    assert request["type"] == constant
    assert request["type_time"] == fake.ORDER_TIME_DAY
    assert request["type_filling"] == fake.ORDER_FILLING_IOC
    assert request["sl"] == 1.0 and request["tp"] == 1.3


def test_place_expiration_and_validation(order):
    module, fake = order
    expires = datetime(2030, 1, 1, tzinfo=timezone.utc)
    result = module.place_order("EURUSD", "buy_limit", 1, price=1.1,
                                type_time="specified", expiration=expires)
    assert result["success"] is True
    assert fake.send_calls[0]["expiration"] == int(expires.timestamp())
    assert module.place_order("EURUSD", "buy_limit", 1)["success"] is False
    assert module.place_order("EURUSD", "buy", True)["success"] is False
    assert module.place_order("EURUSD", "buy", 1, expiration=2)["success"] is False
    assert module.place_order("EURUSD", "buy_limit", 1, price=1, type_time="specified")["success"] is False


def test_place_preflight_and_send_failures(order):
    module, fake = order
    fake.check = Check(7, "bad check", {})
    result = module.place_order("EURUSD", "buy", 1)
    assert result == {"success": False, "data": None, "error": {"code": 7, "message": "bad check"}}
    assert fake.send_calls == []
    fake.check = Check(0, "ok", {})
    fake.send = Result(999, "bad send", {})
    result = module.place_order("EURUSD", "buy", 1)
    assert result["error"] == {"code": 999, "message": "bad send"}
    fake.raise_on = "check"
    assert module.place_order("EURUSD", "buy", 1)["error"]["code"] is None


def test_modify_pending_preserves_unsupplied_fields(order):
    module, fake = order
    fake.orders = (Pending(7, "EURUSD", 1.2, 1.0, 1.4, fake.ORDER_TIME_DAY, 12345, 8),)
    result = module.modify_order(7, price=1.25, comment="changed")
    request = fake.send_calls[0]
    assert result["success"] is True
    assert request["action"] == fake.TRADE_ACTION_MODIFY
    assert request["price"] == 1.25
    assert request["sl"] == 1.0 and request["tp"] == 1.4
    assert request["type_time"] == fake.ORDER_TIME_DAY
    assert request["expiration"] == 12345
    assert request["comment"] == "changed"


def test_modify_position_preserves_counterpart_and_rejects_invalid_fields(order):
    module, fake = order
    fake.positions = (Position(8, "GBPUSD", fake.POSITION_TYPE_BUY, 2, 1.3, 1.1, 1.5, 4),)
    result = module.modify_order(8, target="position", sl=1.2)
    assert result["success"] is True
    assert fake.send_calls[0] == {"action": fake.TRADE_ACTION_SLTP, "position": 8,
                                  "symbol": "GBPUSD", "sl": 1.2, "tp": 1.5}
    assert module.modify_order(8, target="position")["success"] is False
    assert module.modify_order(8, target="position", sl=0)["success"] is False
    assert module.modify_order(8, target="position", sl=1.2, price=1.4)["success"] is False


@pytest.mark.parametrize("kind,quote,close_type", [(10, 1.1, 11), (11, 1.2, 10)])
def test_close_position_full_and_partial(order, kind, quote, close_type):
    module, fake = order
    fake.positions = (Position(9, "EURUSD", kind, 2.0, 1.0, 0, 0, 3),)
    result = module.close_order(9, volume=1.0, deviation=2, magic=5, comment="close", type_filling="fok")
    request = fake.send_calls[0]
    assert result["success"] is True
    assert request["type"] == close_type and request["price"] == quote
    assert request["position"] == 9 and request["volume"] == 1.0
    assert request["type_filling"] == fake.ORDER_FILLING_FOK
    assert module.close_order(9, volume=3)["success"] is False


def test_cancel_pending_and_reject_volume(order):
    module, fake = order
    result = module.close_order(20, target="pending")
    assert result["success"] is True
    assert fake.send_calls[0] == {"action": fake.TRADE_ACTION_REMOVE, "order": 20}
    assert module.close_order(20, target="pending", volume=1)["success"] is False


def test_close_all_filters_magic_attempts_every_item_and_retains_failures(order):
    module, fake = order
    fake.positions = (Position(1, "EURUSD", 10, 1, 1, 0, 0, 7),
                      Position(2, "EURUSD", 10, 1, 1, 0, 0, 8))
    fake.orders = (Pending(3, "EURUSD", 1, 0, 0, 20, 0, 7),)
    calls = 0
    original = fake.order_send

    def mixed(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Result(999, "rejected", {})
        return original(request)

    fake.order_send = mixed
    result = module.close_all_order(symbol="EURUSD", magic=7)
    assert result["success"] is False
    assert [entry["ticket"] for entry in result["data"]] == [1, 3]
    assert result["data"][0]["error"]["code"] == 999
    assert result["data"][1]["success"] is True
    assert result["error"]["message"] == "One or more orders could not be closed."


def test_close_all_empty_is_success(order):
    module, _ = order
    assert module.close_all_order() == {"success": True, "data": [], "error": None}


@pytest.mark.parametrize("kind,close_price,action", [(10, 1.1, 10), (11, 1.2, 11)])
def test_order_profit_uses_position_and_current_quote(order, kind, close_price, action):
    module, fake = order
    fake.positions = (Position(6, "EURUSD", kind, 2, 1.0, 0, 0, 1),)
    result = module.order_profit(6)
    assert result["data"]["profit"] == 42.5
    assert result["data"]["price_close"] == close_price
    assert fake.profit_calls == [(action, "EURUSD", 2, 1.0, close_price)]


def test_order_profit_missing_values_fail_stably(order):
    module, fake = order
    assert module.order_profit(4)["success"] is False
    fake.positions = (Position(4, "EURUSD", 10, 1, 1, 0, 0, 0),)
    fake.tick = None
    assert module.order_profit(4)["success"] is False
    fake.tick = Tick(1, 2)
    fake.raise_on = "profit_none"
    assert module.order_profit(4)["error"]["code"] == 500


def test_open_orders_returns_pending_orders_and_positions_with_targets(order):
    module, fake = order
    fake.orders = (Pending(1, "EURUSD", 1, 0, 0, 20, 0, 0),)
    fake.positions = (Position(2, "EURUSD", fake.POSITION_TYPE_BUY, 1, 1.1, 0, 0, 0),)
    result = module.open_orders(symbol="EURUSD")
    assert result["data"] == [
        {"ticket": 1, "symbol": "EURUSD", "price_open": 1, "sl": 0, "tp": 0,
         "type_time": 20, "time_expiration": 0, "magic": 0, "target": "pending"},
        {"ticket": 2, "symbol": "EURUSD", "type": 10, "volume": 1, "price_open": 1.1,
         "sl": 0, "tp": 0, "magic": 0, "target": "position"},
    ]
    assert fake.orders_calls == [{"symbol": "EURUSD"}]
    assert fake.positions_calls == [{"symbol": "EURUSD"}]


def test_open_orders_forwards_ticket_and_handles_empty_results(order):
    module, fake = order
    result = module.open_orders(ticket=1)
    assert result["data"] == []
    assert fake.orders_calls == [{"ticket": 1}]
    assert fake.positions_calls == [{"ticket": 1}]
    assert module.open_orders(symbol="x", group="x")["success"] is False
    assert module.open_orders(ticket=True)["success"] is False


@pytest.mark.parametrize("failure", ["orders", "positions"])
def test_open_orders_fails_when_either_query_fails(order, failure):
    module, fake = order
    fake.raise_on = failure
    assert module.open_orders()["success"] is False


@pytest.mark.parametrize("failure", ["orders", "positions"])
def test_open_orders_fails_when_either_query_returns_none(order, failure):
    module, fake = order
    if failure == "orders":
        fake.orders = None
    else:
        fake.positions = None
    assert module.open_orders()["success"] is False


def test_history_normalizes_utc_translates_symbol_and_filters_ticket(order):
    module, fake = order
    fake.deals = (Deal(1, 20, "EURUSD", Request("EURUSD")), Deal(2, 21, "EURUSD", Request("EURUSD")))
    local = timezone(timedelta(hours=2))
    start = datetime(2025, 1, 1, 2, tzinfo=local)
    end = datetime(2025, 1, 2, 2, tzinfo=local)
    result = module.order_history(start, end, symbol="EURUSD", ticket=21)
    assert [deal["ticket"] for deal in result["data"]] == [2]
    args, kwargs = fake.history_calls[0]
    assert args == (start.astimezone(timezone.utc), end.astimezone(timezone.utc))
    assert kwargs == {"group": "EURUSD"}
    assert result["data"][0]["request"] == {"symbol": "EURUSD"}


def test_history_validation_empty_and_failures(order):
    module, fake = order
    aware = datetime.now(timezone.utc)
    assert module.order_history(aware.replace(tzinfo=None), aware)["success"] is False
    assert module.order_history(aware, aware - timedelta(seconds=1))["success"] is False
    assert module.order_history(aware, aware, symbol="x", group="x")["success"] is False
    assert module.order_history(aware, aware)["data"] == []
    fake.deals = None
    assert module.order_history(aware, aware)["success"] is False


def test_failures_have_serializable_stable_shape_and_do_not_echo_values(order):
    module, fake = order
    secret = "password-secret"
    fake.diagnostic = (500, "generic terminal error")
    result = module.place_order("", "buy", 1, comment=secret)
    assert set(result) == {"success", "data", "error"}
    assert result["data"] is None
    assert secret not in str(result)
