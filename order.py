"""Standalone MetaTrader 5 order operations.

The module deliberately does not initialize or shut down the terminal.  This
makes request construction testable with a small fake MetaTrader5 module.
"""

from datetime import datetime, timezone, timedelta
import math
from typing import Any, Dict, Optional
import re
import MetaTrader5 as mt5
import pandas as pd


def _ok(data: Any) -> Dict[str, Any]:
    return {"success": True, "data": _plain(data), "error": None}


def _fail(message: str, code: Optional[int] = None, data: Any = None) -> Dict[str, Any]:
    return {"success": False, "data": _plain(data), "error": {"code": code, "message": message}}


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        return {str(k): _plain(v) for k, v in as_dict().items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _last_error(default: str) -> Dict[str, Any]:
    try:
        diagnostic = mt5.last_error()
        if isinstance(diagnostic, (tuple, list)) and len(diagnostic) >= 2:
            code = diagnostic[0] if isinstance(diagnostic[0], int) and not isinstance(diagnostic[0], bool) else None
            message = diagnostic[1] if isinstance(diagnostic[1], str) and diagnostic[1] else default
            return {"code": code, "message": message}
    except Exception:
        pass
    return {"code": None, "message": default}


def _retcode(result: Any) -> Any:
    return getattr(result, "retcode", result.get("retcode") if isinstance(result, dict) else None)


def _comment(result: Any) -> str:
    value = getattr(result, "comment", result.get("comment") if isinstance(result, dict) else "")
    return value if isinstance(value, str) else ""


def _successful(retcode: Any) -> bool:
    return retcode in {getattr(mt5, name, object()) for name in
                       ("TRADE_RETCODE_PLACED", "TRADE_RETCODE_DONE", "TRADE_RETCODE_DONE_PARTIAL")}


def _send(request: Dict[str, Any], data: Any = None) -> Dict[str, Any]:
    try:
        result = mt5.order_send(request)
    except Exception:
        return _fail("MetaTrader 5 operation failed unexpectedly.", data=data)
    if result is None:
        error = _last_error("MetaTrader 5 order operation failed.")
        return _fail(error["message"], error["code"], data)
    code = _retcode(result)
    if not _successful(code):
        message = _comment(result) or _last_error("MetaTrader 5 order operation was rejected.")["message"]
        return _fail(message, code, data)
    return _ok(result if data is None else {"request": request, "result": result})


def _number(value: Any, name: str, positive: bool = False, integer: bool = False) -> Optional[Dict[str, Any]]:
    if integer:
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if valid and positive:
        valid = value > 0
    if valid and not positive and integer:
        valid = value >= 0
    return None if valid else _fail("%s must be %s." % (name, "a positive integer" if integer and positive else "a non-negative integer" if integer else "a positive finite number" if positive else "a finite number"))


_ORDER_TYPES = {"buy": "ORDER_TYPE_BUY", "sell": "ORDER_TYPE_SELL", "buy_limit": "ORDER_TYPE_BUY_LIMIT", "sell_limit": "ORDER_TYPE_SELL_LIMIT", "buy_stop": "ORDER_TYPE_BUY_STOP", "sell_stop": "ORDER_TYPE_SELL_STOP"}
_PENDING = {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}


def _mapped(value: str, mapping: Dict[str, str], name: str):
    if not isinstance(value, str) or value not in mapping:
        return None, _fail("Invalid %s." % name)
    constant = getattr(mt5, mapping[value], None)
    return (constant, None) if constant is not None else (None, _fail("MetaTrader 5 does not provide %s." % mapping[value]))


def _policy(value: Optional[str], kind: str, default: str):
    maps = {"time": {"gtc": "ORDER_TIME_GTC", "day": "ORDER_TIME_DAY", "specified": "ORDER_TIME_SPECIFIED", "specified_day": "ORDER_TIME_SPECIFIED_DAY"}, "filling": {"fok": "ORDER_FILLING_FOK", "ioc": "ORDER_FILLING_IOC", "return": "ORDER_FILLING_RETURN"}}
    selected = default if value is None else value
    return _mapped(selected, maps[kind], kind)


def _expiration(value: Any):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None, _fail("expiration must be timezone-aware when supplied.")
        return int(value.timestamp()), None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value, None
    return None, _fail("expiration must be a datetime or positive integer.")


def _tick(symbol: str):
    try:
        value = mt5.symbol_info_tick(symbol)
    except Exception:
        return None, _fail("MetaTrader 5 operation failed unexpectedly.")
    return (value, None) if value is not None else (None, _fail("Current tick is unavailable."))


def _lookup(method: str, ticket: int, label: str):
    try:
        values = getattr(mt5, method)(ticket=ticket)
    except Exception:
        return None, _fail("MetaTrader 5 operation failed unexpectedly.")
    if not values or len(values) != 1:
        return None, _fail("%s was not found." % label)
    return values[0], None


def place_order(symbol, order_type, volume, price=None, sl=None, tp=None, deviation=20, magic=0, comment="", type_time=None, expiration=None, type_filling="return"):
    if not isinstance(symbol, str) or not symbol:
        return _fail("symbol must be a non-empty string.")
    for value, name, positive in ((volume, "volume", True), (price, "price", True), (sl, "sl", True), (tp, "tp", True)):
        if value is not None and _number(value, name, positive): return _number(value, name, positive)
    for value, name in ((deviation, "deviation"), (magic, "magic")):
        error = _number(value, name, integer=True)
        if error: return error
    if not isinstance(comment, str): return _fail("comment must be a string.")
    mt_type, error = _mapped(order_type, _ORDER_TYPES, "order_type")
    if error: return error
    pending = order_type in _PENDING
    if pending and price is None: return _fail("price is required for pending orders.")
    if not pending and expiration is not None: return _fail("expiration is not valid for instant orders.")
    if not pending:
        if type_time is not None and type_time != "gtc": return _fail("Instant market orders always use gtc.")
        time_name = "gtc"
    else: time_name = "gtc" if type_time is None else type_time
    time_type, error = _policy(time_name, "time", "gtc")
    if error: return error
    if expiration is not None and time_name not in ("specified", "specified_day"): return _fail("expiration requires specified or specified_day.")
    if expiration is None and time_name in ("specified", "specified_day"): return _fail("expiration is required for specified time policies.")
    expiration_value = None
    if expiration is not None:
        expiration_value, error = _expiration(expiration)
        if error: return error
    filling, error = _policy(type_filling, "filling", "return")
    if error: return error
    if price is None:
        tick, error = _tick(symbol)
        if error: return error
        price = getattr(tick, "ask" if order_type == "buy" else "bid")
        if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0: return _fail("Current tick price is unavailable.")
    request = {"action": getattr(mt5, "TRADE_ACTION_PENDING" if pending else "TRADE_ACTION_DEAL"), "symbol": symbol, "volume": volume, "type": mt_type, "price": price, "deviation": deviation, "magic": magic, "comment": comment, "type_time": time_type, "type_filling": 0}
    if sl is not None: request["sl"] = sl
    if tp is not None: request["tp"] = tp
    if expiration_value is not None: request["expiration"] = expiration_value
    try: check = mt5.order_check(request)
    except Exception: return _fail("MetaTrader 5 operation failed unexpectedly.")
    if check is None:
        diagnostic = _last_error("Order preflight check failed.")
        return _fail(diagnostic["message"], diagnostic["code"])
    check_code = _retcode(check)
    if check_code != 0:
        return _fail(_comment(check) or "Order preflight check was rejected.", check_code)
    try: result = mt5.order_send(request)
    except Exception: return _fail("MetaTrader 5 operation failed unexpectedly.")
    if result is None:
        diagnostic = _last_error("Order placement failed.")
        return _fail(diagnostic["message"], diagnostic["code"])
    if not _successful(_retcode(result)):
        message = _comment(result) or _last_error("Order placement was rejected.")["message"]
        return _fail(message, _retcode(result))
    return _ok({"check": check, "result": result})


def _ticket(ticket):
    return _number(ticket, "ticket", True, True)


def modify_order(ticket, target="position", symbol=None, price=None, sl=None, tp=None, expiration=None, type_time=None, comment=None):
    error = _ticket(ticket)
    if error: return error
    if target not in ("pending", "position"): return _fail("target must be pending or position.")
    if symbol is not None and (not isinstance(symbol, str) or not symbol): return _fail("symbol must be a non-empty string.")
    if comment is not None and not isinstance(comment, str): return _fail("comment must be a string.")
    for value, name in ((price, "price"), (sl, "sl"), (tp, "tp")):
        if value is not None and (_number(value, name, True) or value == 0): return _number(value, name, True) or _fail("%s cannot be zero." % name)
    if target == "position":
        if any(v is not None for v in (price, expiration, type_time, comment)): return _fail("Fields are not valid for position modification.")
        if sl is None and tp is None: return _fail("At least one of sl or tp is required.")
        item, error = _lookup("positions_get", ticket, "Position")
        if error: return error
        action = getattr(mt5, "TRADE_ACTION_SLTP")
        request = {"action": action, "position": ticket, "symbol": getattr(item, "symbol"), "sl": getattr(item, "sl") if sl is None else sl, "tp": getattr(item, "tp") if tp is None else tp}
    else:
        if all(v is None for v in (price, sl, tp, expiration, type_time, comment)): return _fail("At least one order change is required.")
        item, error = _lookup("orders_get", ticket, "Pending order")
        if error: return error
        if type_time is None:
            time_type = getattr(item, "type_time")
            selected = None
        else:
            selected = type_time
            time_type, error = _policy(selected, "time", "gtc")
            if error: return error
        if expiration is None:
            exp = getattr(item, "time_expiration")
        else:
            if selected not in ("specified", "specified_day"):
                return _fail("expiration requires specified or specified_day.")
            exp, error = _expiration(expiration)
            if error: return error
        request = {"action": getattr(mt5, "TRADE_ACTION_MODIFY"), "order": ticket, "symbol": symbol or getattr(item, "symbol"), "price": getattr(item, "price_open") if price is None else price, "sl": getattr(item, "sl") if sl is None else sl, "tp": getattr(item, "tp") if tp is None else tp, "type_time": time_type, "expiration": exp}
        if comment is not None: request["comment"] = comment
    return _send(request)


def _close_request(item, ticket, deviation, magic, comment, filling):
    symbol, kind = getattr(item, "symbol"), getattr(item, "type")
    tick, error = _tick(symbol)
    if error: return None, error
    buy = kind == getattr(mt5, "POSITION_TYPE_BUY", getattr(mt5, "ORDER_TYPE_BUY"))
    request = {"action": getattr(mt5, "TRADE_ACTION_DEAL"), "symbol": symbol, "volume": getattr(item, "volume"), "type": getattr(mt5, "ORDER_TYPE_SELL" if buy else "ORDER_TYPE_BUY"), "position": ticket, "price": getattr(tick, "bid" if buy else "ask"), "deviation": deviation, "magic": magic, "comment": comment, "type_filling": filling}
    return request, None


def close_order(ticket, target="position", volume=None, deviation=20, magic=0, comment="", type_filling="return"):
    error = _ticket(ticket)
    if error: return error
    for value, name in ((deviation, "deviation"), (magic, "magic")):
        error = _number(value, name, integer=True)
        if error: return error
    if not isinstance(comment, str): return _fail("comment must be a string.")
    filling, error = _policy(type_filling, "filling", "return")
    if error: return error
    if target == "pending":
        if volume is not None: return _fail("volume is not valid for pending cancellation.")
        return _send({"action": getattr(mt5, "TRADE_ACTION_REMOVE"), "order": ticket})
    if target != "position": return _fail("target must be position or pending.")
    item, error = _lookup("positions_get", ticket, "Position")
    if error: return error
    current = getattr(item, "volume")
    if volume is not None:
        error = _number(volume, "volume", True)
        if error: return error
        if volume > current: return _fail("volume cannot exceed the position volume.")
    request, error = _close_request(item, ticket, deviation, magic, comment, 0)
    if error: return error
    if volume is not None: request["volume"] = volume
    return _send(request)


def close_all_order(symbol=None, magic=None, include_positions=True, include_pending=True, deviation=20, comment="", type_filling="return"):
    if not isinstance(include_positions, bool) or not isinstance(include_pending, bool): return _fail("include flags must be booleans.")
    if not include_positions and not include_pending: return _fail("At least one order category must be included.")
    if symbol is not None and (not isinstance(symbol, str) or not symbol): return _fail("symbol must be a non-empty string.")
    if magic is not None and _number(magic, "magic", integer=True): return _number(magic, "magic", integer=True)
    error = _number(deviation, "deviation", integer=True)
    if error: return error
    if not isinstance(comment, str): return _fail("comment must be a string.")
    filling, error = _policy(type_filling, "filling", "return")
    if error: return error
    entries = []
    query_failed = False
    for enabled, method, target in ((include_positions, "positions_get", "position"), (include_pending, "orders_get", "pending")):
        if not enabled: continue
        try: values = getattr(mt5, method)(**({"symbol": symbol} if symbol is not None else {}))
        except Exception: values = None
        if values is None:
            query_failed = True
            entries.append({"ticket": None, "target": target, "success": False, "result": None, "error": _last_error("Unable to query %s." % target)})
            continue
        for item in values:
            if magic is not None and getattr(item, "magic", None) != magic: continue
            ticket = getattr(item, "ticket")
            if target == "position":
                request, request_error = _close_request(item, ticket, deviation, 0 if magic is None else magic, comment, 0)
                outcome = request_error if request_error else _send(request)
            else: outcome = _send({"action": getattr(mt5, "TRADE_ACTION_REMOVE"), "order": ticket})
            entries.append({"ticket": ticket, "target": target, "success": outcome["success"], "result": outcome["data"], "error": outcome["error"]})
    if query_failed or any(not x["success"] for x in entries): return _fail("One or more orders could not be closed.", data=entries)
    return _ok(entries)


def order_profit(ticket):
    error = _ticket(ticket)
    if error: return error
    item, error = _lookup("positions_get", ticket, "Position")
    if error: return error
    tick, error = _tick(getattr(item, "symbol"))
    if error: return error
    buy = getattr(item, "type") == getattr(mt5, "POSITION_TYPE_BUY", getattr(mt5, "ORDER_TYPE_BUY"))
    close_price = getattr(tick, "bid" if buy else "ask")
    try: profit = mt5.order_calc_profit(getattr(mt5, "ORDER_TYPE_BUY" if buy else "ORDER_TYPE_SELL"), getattr(item, "symbol"), getattr(item, "volume"), getattr(item, "price_open"), close_price)
    except Exception: return _fail("MetaTrader 5 operation failed unexpectedly.")
    if profit is None:
        diagnostic = _last_error("Unable to calculate order profit.")
        return _fail(diagnostic["message"], diagnostic["code"])
    return _ok({"ticket": ticket, "symbol": getattr(item, "symbol"), "volume": getattr(item, "volume"), "price_open": getattr(item, "price_open"), "price_close": close_price, "profit": profit})


def open_orders(symbol=None, ticket=None, group=None):
    if sum(value is not None for value in (symbol, ticket, group)) > 1: return _fail("symbol, ticket, and group are mutually exclusive.")
    if symbol is not None and (not isinstance(symbol, str) or not symbol): return _fail("symbol must be a non-empty string.")
    if ticket is not None and _ticket(ticket): return _ticket(ticket)
    if group is not None and (not isinstance(group, str) or not group): return _fail("group must be a non-empty string.")
    args = {key: value for key, value in (("symbol", symbol), ("ticket", ticket), ("group", group)) if value is not None}
    entries = []
    for method, target, label in (("orders_get", "pending", "open orders"), ("positions_get", "position", "open positions")):
        try: result = getattr(mt5, method)(**args)
        except Exception: return _fail("MetaTrader 5 operation failed unexpectedly.")
        if result is None:
            diagnostic = _last_error("Unable to retrieve %s." % label)
            return _fail(diagnostic["message"], diagnostic["code"])
        for item in result:
            entry = _plain(item)
            if isinstance(entry, dict):
                entry["target"] = target
            entries.append(entry)
    return _ok(entries)

def order_history(date_range, symbol=None, ticket=None, group=None):
    if not isinstance(date_range, str):
        return _fail("date_range must be a string, e.g. 5D, 1W, 3M, 1Y.")

    match = re.fullmatch(r"(\d+)([DWMY])", date_range.upper())

    if not match:
        return _fail(
            "Invalid date_range. Use a format such as 5D, 2W, 3M, or 1Y."
        )

    value, unit = int(match.group(1)), match.group(2)

    if value <= 0:
        return _fail("date_range value must be greater than 0.")

    date_to = datetime.now(timezone.utc)

    if unit == "D":
        date_from = date_to - timedelta(days=value)
    elif unit == "W":
        date_from = date_to - timedelta(weeks=value)
    elif unit == "M":
        date_from = date_to - timedelta(days=value * 30)
    elif unit == "Y":
        date_from = date_to - timedelta(days=value * 365)

    if symbol is not None and group is not None:
        return _fail("symbol and group are mutually exclusive.")

    if symbol is not None:
        if not isinstance(symbol, str) or not symbol:
            return _fail("symbol must be a non-empty string.")
        group = symbol

    if group is not None and (not isinstance(group, str) or not group):
        return _fail("group must be a non-empty string.")

    if ticket is not None and _ticket(ticket):
        return _ticket(ticket)

    args = {"group": group} if group is not None else {}

    try:
        result = mt5.history_deals_get(date_from, date_to, **args)
    except Exception:
        return _fail("MetaTrader 5 operation failed unexpectedly.")

    if result is None:
        diagnostic = _last_error("Unable to retrieve order history.")
        return _fail(diagnostic["message"], diagnostic["code"])

    values = [_plain(x) for x in result]

    if ticket is not None:
        values = [x for x in values if x.get("order") == ticket]

    return _ok(values)


def atr_step_trailing(
    order,
    df,
    side,
    entry_tf,
    atr_period=14,
    atr_multiplier=1.5,
    step_multiplier=0.5,
    activation_multiplier=2.0,
):
    """
    ATR + step trailing stop for an MT5 position.

    Parameters
    ----------
    order : dict
        Position/order dictionary containing:
        ticket, time, price_open, price_current, sl, symbol

    df : pandas.DataFrame
        M1 price dataframe containing:
        time, high_M1, low_M1, close_M1

    side : str
        "buy" or "sell"

    atr_period : int
        ATR period.

    atr_multiplier : float
        Distance of trailing SL from highest/lowest favorable price.

    step_multiplier : float
        Minimum ATR step required before moving an existing SL.

    activation_multiplier : float
        Favorable ATR movement required before trailing starts.
    """

    side = side.lower()

    if side not in ("buy", "sell"):
        return {
            "modified": False,
            "reason": "invalid_side",
            "side": side,
        }

    # ---------------------------------------------------------
    # 1. Order information
    # ---------------------------------------------------------

    ticket = order["ticket"]
    symbol = order["symbol"]

    entry_price = float(order["price_open"])
    current_price = float(order["price_current"])
    current_sl = float(order.get("sl", 0.0) or 0.0)

    entry_time = pd.to_datetime(
        order["time"],
        unit="s",
        utc=True,
    )

    has_sl = current_sl > 0

    # ---------------------------------------------------------
    # 2. Get MT5 symbol/tick information
    # ---------------------------------------------------------

    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        return {
            "modified": False,
            "reason": "symbol_info_unavailable",
            "symbol": symbol,
        }

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        return {
            "modified": False,
            "reason": "tick_unavailable",
            "symbol": symbol,
        }

    digits = symbol_info.digits
    point = symbol_info.point

    current_bid = float(tick.bid)
    current_ask = float(tick.ask)

    # Minimum broker stop distance
    min_stop_distance = (
        symbol_info.trade_stops_level * point
    )

    # ---------------------------------------------------------
    # 3. Prepare dataframe
    # ---------------------------------------------------------

    df = df.copy()

    required_columns = {
        "time",
        f"high_{entry_tf}",
        f"low_{entry_tf}",
        f"close_{entry_tf}",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        return {
            "modified": False,
            "reason": "missing_columns",
            "columns": list(missing_columns),
        }

    df["time"] = pd.to_datetime(
        df["time"],
        utc=True,
        errors="coerce",
    )

    df = (
        df
        .dropna(
            subset=[
                "time",
                f"high_{entry_tf}",
                f"low_{entry_tf}",
                f"close_{entry_tf}",
            ]
        )
        .sort_values("time")
        .reset_index(drop=True)
    )

    if len(df) < atr_period + 1:
        return {
            "modified": False,
            "reason": "insufficient_atr_data",
            "rows": len(df),
        }

    # ---------------------------------------------------------
    # 4. Calculate True Range
    # ---------------------------------------------------------

    previous_close = df[f"close_{entry_tf}"].shift(1)

    high_low = (
        df[f"high_{entry_tf}"] -
        df[f"low_{entry_tf}"]
    )

    high_previous_close = (
        df[f"high_{entry_tf}"] -
        previous_close
    ).abs()

    low_previous_close = (
        df[f"low_{entry_tf}"] -
        previous_close
    ).abs()

    df["true_range"] = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close,
        ],
        axis=1,
    ).max(axis=1)

    # ---------------------------------------------------------
    # 5. Wilder ATR
    # ---------------------------------------------------------

    df["atr"] = df["true_range"].ewm(
        alpha=1 / atr_period,
        adjust=False,
    ).mean()

    atr = float(df["atr"].iloc[-1])

    if pd.isna(atr) or atr <= 0:
        return {
            "modified": False,
            "reason": "invalid_atr",
            "atr": atr,
        }

    # ---------------------------------------------------------
    # 6. Price movement since trade entry
    # ---------------------------------------------------------

    trade_df = df[
        df["time"] >= entry_time.floor("min")
    ]

    if trade_df.empty:
        highest_price = entry_price
        lowest_price = entry_price

    else:
        highest_price = max(
            entry_price,
            float(trade_df[f"high_{entry_tf}"].max()),
        )

        lowest_price = min(
            entry_price,
            float(trade_df[f"low_{entry_tf}"].min()),
        )

    # Include current live prices
    #
    # For BUY:
    # position effectively exits using BID.
    #
    # For SELL:
    # position effectively exits using ASK.
    #
    highest_price = max(
        highest_price,
        current_bid,
    )

    lowest_price = min(
        lowest_price,
        current_ask,
    )

    # ---------------------------------------------------------
    # 7. ATR distances
    # ---------------------------------------------------------

    trail_distance = (
        atr * atr_multiplier
    )

    step_distance = (
        atr * step_multiplier
    )

    activation_distance = (
        atr * activation_multiplier
    )

    # ---------------------------------------------------------
    # Common result information
    # ---------------------------------------------------------

    debug_data = {
        "ticket": ticket,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "current_price": current_price,
        "current_bid": current_bid,
        "current_ask": current_ask,
        "current_sl": current_sl,
        "highest_price": highest_price,
        "lowest_price": lowest_price,
        "atr": atr,
        "atr_multiplier": atr_multiplier,
        "step_multiplier": step_multiplier,
        "activation_multiplier": activation_multiplier,
        "trail_distance": trail_distance,
        "step_distance": step_distance,
        "activation_distance": activation_distance,
        "min_stop_distance": min_stop_distance,
    }

    # =========================================================
    # BUY
    # =========================================================

    if side == "buy":

        favorable_move = (
            highest_price -
            entry_price
        )

        # -----------------------------------------------------
        # Wait until activation threshold
        # -----------------------------------------------------

        if favorable_move < activation_distance:

            return {
                "modified": False,
                "reason": "activation_not_reached",
                "favorable_move": favorable_move,
                **debug_data,
            }

        # -----------------------------------------------------
        # Calculate theoretical ATR trailing SL
        # -----------------------------------------------------

        candidate_sl = (
            highest_price -
            trail_distance
        )

        candidate_sl = round(
            candidate_sl,
            digits,
        )

        # -----------------------------------------------------
        # Broker valid stop limit
        #
        # BUY SL must be BELOW current BID
        # -----------------------------------------------------

        maximum_valid_sl = (
            current_bid -
            min_stop_distance
        )

        maximum_valid_sl = round(
            maximum_valid_sl,
            digits,
        )

        # ATR SL already crossed / too close
        if candidate_sl >= maximum_valid_sl:

            return {
                "modified": False,
                "reason": "trailing_level_already_crossed",
                "candidate_sl": candidate_sl,
                "maximum_valid_sl": maximum_valid_sl,
                "favorable_move": favorable_move,
                **debug_data,
            }

        # -----------------------------------------------------
        # First SL
        # -----------------------------------------------------

        if not has_sl:

            result = modify_order(
                ticket,
                sl=candidate_sl,
            )

            success = bool(
                result.get("success", False)
            )

            if success:
                print(f"modified order - {ticket}")

            return {
                "modified": success,
                "reason": (
                    "initial_trailing_sl"
                    if success
                    else "modify_failed"
                ),
                "previous_sl": current_sl,
                "new_sl": candidate_sl,
                "favorable_move": favorable_move,
                "modify_result": result,
                **debug_data,
            }

        # -----------------------------------------------------
        # Existing SL
        #
        # Only move after another ATR step
        # -----------------------------------------------------

        required_sl = (
            current_sl +
            step_distance
        )

        if candidate_sl < required_sl:

            return {
                "modified": False,
                "reason": "step_not_reached",
                "candidate_sl": candidate_sl,
                "required_sl": required_sl,
                "favorable_move": favorable_move,
                **debug_data,
            }

        # -----------------------------------------------------
        # Modify existing SL
        # -----------------------------------------------------

        result = modify_order(
            ticket,
            sl=candidate_sl,
        )

        success = bool(
            result.get("success", False)
        )

        if success:
            print(f"modified order - {ticket}")

        return {
            "modified": success,
            "reason": (
                "trailing_step"
                if success
                else "modify_failed"
            ),
            "previous_sl": current_sl,
            "new_sl": candidate_sl,
            "favorable_move": favorable_move,
            "modify_result": result,
            **debug_data,
        }

    # =========================================================
    # SELL
    # =========================================================

    favorable_move = (
        entry_price -
        lowest_price
    )

    # ---------------------------------------------------------
    # Wait until activation threshold
    # ---------------------------------------------------------

    if favorable_move < activation_distance:

        return {
            "modified": False,
            "reason": "activation_not_reached",
            "favorable_move": favorable_move,
            **debug_data,
        }

    # ---------------------------------------------------------
    # ATR trailing SL
    # ---------------------------------------------------------

    candidate_sl = (
        lowest_price +
        trail_distance
    )

    candidate_sl = round(
        candidate_sl,
        digits,
    )

    # ---------------------------------------------------------
    # SELL SL must be ABOVE current ASK
    # ---------------------------------------------------------

    minimum_valid_sl = (
        current_ask +
        min_stop_distance
    )

    minimum_valid_sl = round(
        minimum_valid_sl,
        digits,
    )

    # ATR trailing level has already been crossed
    # or is inside broker stop distance.
    if candidate_sl <= minimum_valid_sl:

        return {
            "modified": False,
            "reason": "trailing_level_already_crossed",
            "candidate_sl": candidate_sl,
            "minimum_valid_sl": minimum_valid_sl,
            "favorable_move": favorable_move,
            **debug_data,
        }

    # ---------------------------------------------------------
    # First SL
    # ---------------------------------------------------------

    if not has_sl:

        result = modify_order(
            ticket,
            sl=candidate_sl,
        )

        success = bool(
            result.get("success", False)
        )

        return {
            "modified": success,
            "reason": (
                "initial_trailing_sl"
                if success
                else "modify_failed"
            ),
            "previous_sl": current_sl,
            "new_sl": candidate_sl,
            "favorable_move": favorable_move,
            "modify_result": result,
            **debug_data,
        }

    # ---------------------------------------------------------
    # Existing SL
    #
    # SELL SL moves downward.
    # ---------------------------------------------------------

    required_sl = (
        current_sl -
        step_distance
    )

    if candidate_sl > required_sl:

        return {
            "modified": False,
            "reason": "step_not_reached",
            "candidate_sl": candidate_sl,
            "required_sl": required_sl,
            "favorable_move": favorable_move,
            **debug_data,
        }

    # ---------------------------------------------------------
    # Modify existing SL
    # ---------------------------------------------------------

    result = modify_order(
        ticket,
        sl=candidate_sl,
    )

    success = bool(
        result.get("success", False)
    )

    return {
        "modified": success,
        "reason": (
            "trailing_step"
            if success
            else "modify_failed"
        ),
        "previous_sl": current_sl,
        "new_sl": candidate_sl,
        "favorable_move": favorable_move,
        "modify_result": result,
        **debug_data,
    }