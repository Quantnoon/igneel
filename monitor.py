"""Evaluate whether the bot may open a trade."""

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Tuple
import MetaTrader5 as mt5

from account import Account
from order import close_all_order, open_orders


SESSION_WINDOWS = {
    "asia": (0, 9),
    "london": (8, 17),
    "new_york": (13, 22),
    "london_new_york_overlap": (13, 17),
}
_REQUIRED_CONFIG = {
    "symbol",
    "trading_sessions",
    "daily_dd",
    "maximum_dd",
    "allow_many_trades",
}


def _blocked(reasons: List[str]) -> Dict[str, str]:
    return {"status": "blocked", "reason": " ".join(reasons)}


def _normalize_session(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip().lower())


def _threshold(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _validate_config(bot_config: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(bot_config, dict):
        return None, "bot_config must be a dictionary."

    missing = sorted(_REQUIRED_CONFIG - set(bot_config))
    if missing:
        return None, "Missing required bot configuration field: %s." % missing[0]

    symbol = bot_config["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        return None, "symbol must be a non-empty string."

    sessions = bot_config["trading_sessions"]
    if not isinstance(sessions, list):
        return None, "trading_sessions must be a list."
    normalized_sessions = []
    for session in sessions:
        if not isinstance(session, str):
            return None, "trading_sessions must contain only session names."
        normalized = _normalize_session(session)
        if normalized not in SESSION_WINDOWS:
            return None, "Unknown trading session: %s." % session
        if normalized not in normalized_sessions:
            normalized_sessions.append(normalized)

    for field in ("daily_dd", "maximum_dd"):
        if not _threshold(bot_config[field]):
            return None, "%s must be a non-negative finite number." % field

    if not isinstance(bot_config["allow_many_trades"], bool):
        return None, "allow_many_trades must be a boolean."

    return {
        "symbol": symbol.strip(),
        "trading_sessions": normalized_sessions,
        "daily_dd": float(bot_config["daily_dd"]),
        "maximum_dd": float(bot_config["maximum_dd"]),
        "allow_many_trades": bot_config["allow_many_trades"],
    }, None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session_active(sessions: List[str], current: datetime) -> bool:
    if not sessions:
        return True
    hour = current.hour + current.minute / 60.0 + current.second / 3600.0
    return any(SESSION_WINDOWS[session][0] <= hour < SESSION_WINDOWS[session][1] for session in sessions)


def _account_values(account_info: Any) -> Tuple[Optional[Tuple[float, float]], Optional[str]]:
    if not isinstance(account_info, dict):
        return None, "Account state is unavailable."
    if any(isinstance(account_info.get(field), bool) for field in ("starting_balance", "current_balance")):
        return None, "Account balances are missing or non-numeric."
    try:
        starting_balance = float(account_info["starting_balance"])
        current_balance = float(account_info["current_balance"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "Account balances are missing or non-numeric."
    if not math.isfinite(starting_balance) or not math.isfinite(current_balance):
        return None, "Account balances must be finite numbers."
    if starting_balance <= 0:
        return None, "Starting balance must be greater than zero."
    return (starting_balance, current_balance), None


def _load_account() -> Tuple[Optional[Tuple[float, float]], Optional[str]]:
    account = None
    try:
        account = Account()
        return _account_values(account.get_account_info())
    except Exception:
        return None, "Account state could not be loaded."
    finally:
        if account is not None:
            database = getattr(account, "_db", None)
            close = getattr(database, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass


def _entry_symbol(entry: Any) -> Any:
    if isinstance(entry, dict):
        return entry.get("symbol")
    return getattr(entry, "symbol", None)


def _open_trade_reason(symbol: str) -> Optional[str]:
    try:
        result = open_orders(symbol=symbol)
    except Exception:
        return "Unable to check open orders and positions."
    if not isinstance(result, dict) or result.get("success") is not True:
        return "Unable to check open orders and positions."
    entries = result.get("data")
    if not isinstance(entries, list):
        return "Unable to check open orders and positions."
    if any(_entry_symbol(entry) == symbol for entry in entries):
        return "An order or position already exists for %s." % symbol
    return None


def can_trade(bot_config: dict) -> Dict[str, str]:
    """Return whether a trade may be opened under the supplied configuration."""
    config, error = _validate_config(bot_config)
    if error:
        return _blocked(["Invalid bot configuration: %s" % error])

    account = Account()
    account_info_dict = mt5.account_info()._asdict()

    if account_info_dict["balance"] > account.get_account_info()["current_balance"]:
        account.update_balance(account_info_dict["balance"])

    if account_info_dict["balance"] < account.get_account_info()["current_balance"] or account_info_dict["equity"] < account.get_account_info()["current_balance"]:
        account.update_balance(account_info_dict["balance"])

    reasons = []
    balances, account_error = _load_account()
    if account_error:
        reasons.append(account_error)

    if not _session_active(config["trading_sessions"], _utc_now()):
        reasons.append("Trading session is not active.")

    # if balances is not None:
    #     starting_balance, current_balance = balances
    #     drawdown = (starting_balance - current_balance) / starting_balance
    #     daily_limit_reached = drawdown >= config["daily_dd"]
    #     maximum_limit_reached = drawdown >= config["maximum_dd"]
    #     if daily_limit_reached:
    #         reasons.append("Daily drawdown limit reached (%.2f%%)." % (config["daily_dd"] * 100))
    #     if maximum_limit_reached:
    #         reasons.append("Maximum drawdown limit reached (%.2f%%)." % (config["maximum_dd"] * 100))
    #     if daily_limit_reached or maximum_limit_reached:
    #         try:
    #             close_result = close_all_order()
    #         except Exception:
    #             close_result = None
    #         if not isinstance(close_result, dict) or close_result.get("success") is not True:
    #             reasons.append("Unable to close all orders and positions after drawdown limit reached.")

    if not config["allow_many_trades"]:
        order_reason = _open_trade_reason(config["symbol"])
        if order_reason:
            reasons.append(order_reason)

    if reasons:
        return _blocked(reasons)
    return {"status": "can_trade", "reason": "Trading is allowed."}
