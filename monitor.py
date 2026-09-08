"""Evaluate whether the bot may open a trade."""

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Tuple
import MetaTrader5 as mt5
import pandas as pd

from account import Account
from order import close_all_order, open_orders
from database import Database
from quantnoon_signal import SignalSender, SignalRecorder
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

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

    date_str = account.get_account_info()["date"]

    date_obj = datetime.strptime(date_str, "%d/%m/%Y").date()
    today = datetime.now().date()

    if today > date_obj:
        account.update_account(
            account_info_dict["balance"],
            bot_config["daily_dd"],
            bot_config["maximum_dd"]
        )

    if account_info_dict["balance"] > account.get_account_info()["current_balance"]:
        account.update_balance(
            account_info_dict["balance"],
            bot_config["daily_dd"],
            bot_config["maximum_dd"]
        )

    reasons = []
    if  account_info_dict["equity"] <= account.get_account_info()["maximum_drawdown"]:
        reasons.append("Account has reached maximum drawdown")
        close_all_order()

    if account_info_dict["equity"] <= account.get_account_info()["maximum_drawdown"]:
        reasons.append("Account has reached daily drawdown")
        # close_all_order()

    if not _session_active(config["trading_sessions"], _utc_now()):
        reasons.append("Trading session is not active.")

    dt = datetime.now()

    if not bot_config["is_weekend_trading"] and (dt.weekday() == 5 or dt.weekday() == 6):
        reasons.append("Weekend trading is not allowed.")

    if not config["allow_many_trades"]:
        order_reason = _open_trade_reason(config["symbol"])
        if order_reason:
            reasons.append(order_reason)

    if reasons:
        return _blocked(reasons)
    return {"status": "can_trade", "reason": "Trading is allowed."}

_db = Database()

def quantnoon_signal_provider(
    signal: dict,
    symbol: str,
    identifier: str,
    signal_name: str,
    trade_date: datetime,
    df: pd.DataFrame,
    entry_tf: str,
    exit_signal: function,
):
    if os.environ["QUANTNOON_SIGNAL"] == "true":
        _Qsender = SignalSender()
        _Qrecord = SignalRecorder()
        sent_signal = _db.get_row(f"{identifier}", "symbol", symbol)["data"]

        if sent_signal is None:
            if signal["pos"] is not None:
                _Qsender.send_signal_webhook(
                    identifier=identifier,
                    signal_name=signal_name,
                    signal_type=signal["pos"],
                    sl=signal["sl"],
                    tps=[signal["tp"] if signal["tp"] else "custom"],
                    symbol=symbol,
                )

                record_signal = {
                    "id": identifier,
                    "algo_name": identifier,
                    "trade_date": trade_date.strftime('%d/%m/%Y, %H:%M:%S'),
                    "sl": signal["sl"],
                    "op": signal["open_price"],
                    "tp": signal["tp"],
                    "position": signal["pos"],
                    "exit_date": None,
                    "gain": 0,
                    "symbol": symbol
                }

                _db.create_table(f"{identifier}", record_signal)
                _db.add_to_table(f"{identifier}", record_signal)
        else:
            target_time = pd.to_datetime(sent_signal["trade_date"], utc=True, format="%d/%m/%Y, %H:%M:%S")
            start_index = df.index[df["time"] >= target_time][0]
            update_record = sent_signal

            for i in range(start_index, len(df)):
                row = df.iloc[i]
                if sent_signal["sl"] is not None:
                    has_hit_sl = sent_signal["sl"] >= row[f"low_{entry_tf}"] if sent_signal["position"] == "buy" else sent_signal["sl"] <= row[f"high_{entry_tf}"]

                    if has_hit_sl:    
                        update_record["exit_date"] = row["time"].strftime('%d/%m/%Y, %H:%M:%S')
                        update_record["gain"] = update_record["sl"] - update_record["op"] if update_record["position"] == "buy" else update_record["op"] - update_record["sl"]
                        break

                if sent_signal["tp"] is not None:
                    has_hit_tp = sent_signal["tp"] <= row[f"high_{entry_tf}"] if sent_signal["position"] == "buy" else sent_signal["tp"] >= row[f"low_{entry_tf}"]

                    if has_hit_tp:
                        update_record["exit_date"] = row["time"].strftime('%d/%m/%Y, %H:%M:%S')
                        update_record["gain"] = update_record["tp"] - update_record["op"] if update_record["position"] == "buy" else update_record["op"] - update_record["tp"]
                        break

                else:
                    if exit_signal is not None:
                        has_exit_trade = exit_signal(df, i, update_record["position"])
                        if has_exit_trade:
                            update_record["exit_date"] = row["time"].strftime('%d/%m/%Y, %H:%M:%S')
                            update_record["gain"] = row[f"close_{entry_tf}"] - update_record["op"] if update_record["position"] == "buy" else update_record["op"] - row[f"close_{entry_tf}"]
                            update_record["sl"] = 0
                            update_record["tp"] = 0

            if update_record["exit_date"] is not None:
                _Qrecord.send_record_webhook(
                    algo_name=update_record["algo_name"],
                    trade_date=update_record["trade_date"],
                    sl=update_record["sl"],
                    op=update_record["op"],
                    tp=update_record["tp"],
                    position=update_record["position"],
                    exit_date=update_record["exit_date"],
                    gain=update_record["gain"]
                )
                _db.delete_row(f"{identifier}", "id", f"{identifier}")

            

        