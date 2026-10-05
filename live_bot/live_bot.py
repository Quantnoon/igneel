import re
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

import MetaTrader5 as mt5

from collection import PriceDataCollection
from connection import connect
from database import Database
from live_bot.account import Account
from live_bot.live_config import active_config
from live_bot.monitor import can_trade, quantnoon_signal_provider
from live_bot.telegram import (
    clear_alert,
    configure_notification_state,
    daily_log,
    initialize_telegram,
    log_error,
    log_event,
    startup_report,
    startup_report_enabled,
)
from order import atr_step_trailing, close_order, open_orders, place_order


_TRAILING_FAILURES = {
    "invalid_side",
    "symbol_info_unavailable",
    "tick_unavailable",
    "missing_columns",
    "insufficient_atr_data",
    "invalid_atr",
    "modify_failed",
}

_DRAWDOWN_STATUS_PATTERNS = (
    re.compile(
        r"(?:account\s+has\s+reached\s+)?daily\s+drawdown"
        r"(?:\s+limit\s+reached)?(?:\s*\([^)]*\))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:account\s+has\s+reached\s+)?maximum\s+drawdown"
        r"(?:\s+limit\s+reached)?(?:\s*\([^)]*\))?",
        re.IGNORECASE,
    ),
)


def _drawdown_status_reasons(reason):
    """Return only daily or maximum drawdown clauses from a blocked status."""
    text = str(reason or "")
    matches = [
        match
        for pattern in _DRAWDOWN_STATUS_PATTERNS
        for match in pattern.finditer(text)
    ]
    matches.sort(key=lambda match: match.start())
    return [match.group(0).rstrip(".") + "." for match in matches]


def _allow_quantnoon_signal(status):
    """Allow fresh Quantnoon entries unless a drawdown limit blocks trading."""
    return not bool(_drawdown_status_reasons(status.get("reason")))


def _report_drawdown_status(signal, symbol, status):
    reasons = _drawdown_status_reasons(status.get("reason"))
    active_types = set()
    for reason in reasons:
        lower_reason = reason.lower()
        if "daily drawdown" in lower_reason:
            active_types.add("daily")
        if "maximum drawdown" in lower_reason:
            active_types.add("maximum")

    if "maximum" in active_types:
        drawdown_types = ("maximum",)
    elif "daily" in active_types:
        drawdown_types = ("daily",)
    else:
        drawdown_types = ()
    for drawdown_type in ("daily", "maximum"):
        event_key = "trading_drawdown:%s:%s:%s" % (
            drawdown_type,
            signal["magic"],
            symbol,
        )
        if drawdown_type not in drawdown_types:
            clear_alert(event_key)
            continue
        matching_reasons = [
            reason
            for reason in reasons
            if drawdown_type + " drawdown" in reason.lower()
        ]
        log_error(
            "Trading blocked for %s on %s: %s"
            % (
                signal.get("name", "Signal"),
                symbol,
                " ".join(matching_reasons),
            ),
            event_key=event_key,
            severity="warning",
            notification_type=drawdown_type + "_drawdown",
        )

    if reasons:
        print(
            "STATUS: Trading blocked for %s on %s: %s"
            % (signal.get("name", "Signal"), symbol, " ".join(reasons))
        )


def process_signal_symbol(
    price_data,
    signal,
    symbol,
    db,
    daily_dd,
    max_dd,
    entry_tf,
):
    """Process one symbol and report operational/trade events to Telegram."""
    processing_key = "signal_processing:%s:%s" % (signal["magic"], symbol)
    try:
        _process_signal_symbol(
            price_data,
            signal,
            symbol,
            db,
            daily_dd,
            max_dd,
            entry_tf,
        )
    except Exception as exc:
        log_error(
            "Error processing %s for %s: %s"
            % (signal.get("name", "signal"), symbol, exc),
            event_key=processing_key,
        )
        return False
    clear_alert(processing_key)
    return True


def _process_signal_symbol(
    price_data,
    signal,
    symbol,
    db,
    daily_dd,
    max_dd,
    entry_tf,
):
    data_key = "price_data:%s" % symbol
    try:
        df = price_data.get_price_data(symbol)
    except Exception as exc:
        log_error(
            "Price data fetch failed for %s: %s" % (symbol, exc),
            event_key=data_key,
        )
        return
    if df is None or getattr(df, "empty", False):
        log_error(
            "Price data fetch returned no rows for %s." % symbol,
            event_key=data_key,
        )
        return
    clear_alert(data_key)

    trade_signal = signal["signal"]
    pos, sl = trade_signal(df, len(df) - 1)
    tp = None
    open_price = df["close_%s" % entry_tf].iloc[-1]
    status = can_trade(
        {
            "symbol": symbol,
            "trading_sessions": signal["trading_sessions"],
            "daily_dd": daily_dd,
            "maximum_dd": max_dd,
            "allow_many_trades": signal["allow_many_trades"],
            "is_weekend_trading": signal["is_weekend_trading"],
        }
    )

    _report_drawdown_status(signal, symbol, status)

    if signal["sl_type"] == "atr":
        info = mt5.symbol_info(symbol)
        atr = df["atr_%s" % signal["entry_tf"]].values[-1]
        entry_price = df["close_%s" % signal["entry_tf"]].values[-1]
        sl = (
            entry_price - (atr * signal["atr_multiplier"])
            if pos == "buy"
            else entry_price + (atr * signal["atr_multiplier"])
        )
        risk = abs(entry_price - sl)
        tp = (
            entry_price + (risk * signal["rrr"])
            if pos == "buy"
            else entry_price - (risk * signal["rrr"])
        )
        if info is not None:
            sl = round(sl, info.digits)
            tp = round(tp, info.digits)

    quantnoon_signal_provider(
        signal={"sl": sl, "tp": tp, "pos": pos, "open_price": open_price},
        symbol=symbol,
        identifier="support_resistance",
        signal_name="Ranger",
        df=df,
        trade_date=df["time"].iloc[-1],
        entry_tf=signal["entry_tf"],
        exit_signal=signal.get("custom_sl"),
        allow_new_signal=_allow_quantnoon_signal(status),
    )

    if pos is None and status.get("status") == "can_trade":
        print("%s: has no signal" % symbol)

    if status.get("status") == "can_trade" and pos is not None:
        result = place_order(
            symbol=symbol,
            order_type=pos,
            volume=signal["lot_size"],
            magic=signal["magic"],
            price=open_price,
            sl=sl,
            tp=tp,
        )
        order_key = "place_order:%s:%s" % (signal["magic"], symbol)
        if not result.get("success"):
            log_error(
                "Order placement failed for %s (%s): %s"
                % (symbol, signal.get("name", "signal"), result.get("error")),
                event_key=order_key,
            )
            return

        clear_alert(order_key)
        order_id = result["data"]["result"]["order"]
        stored = {"id": order_id, "pos": pos}
        create_result = db.create_table(signal["name"], stored)
        if not create_result.get("success"):
            log_error(
                "Order %s opened, but local tracking table failed: %s"
                % (order_id, create_result.get("error")),
                event_key="order_storage:%s" % signal["name"],
            )
        else:
            add_result = db.add_to_table(signal["name"], stored)
            if not add_result.get("success"):
                log_error(
                    "Order %s opened, but local tracking row failed: %s"
                    % (order_id, add_result.get("error")),
                    event_key="order_storage:%s" % signal["name"],
                )
            else:
                clear_alert("order_storage:%s" % signal["name"])

        message = "Opened %s %s trade %s at %s." % (
            signal.get("name", "Signal"),
            pos.upper(),
            order_id,
            symbol,
        )
        log_event(message, notification_type="trade_opened")
        print("%s: %s order placed" % (symbol, pos))
        return

    orders_result = open_orders(symbol=symbol)
    if not orders_result.get("success"):
        log_error(
            "Open-order lookup failed for %s: %s" % (symbol, orders_result.get("error")),
            event_key="open_orders:%s" % symbol,
        )
        return
    clear_alert("open_orders:%s" % symbol)

    for order in orders_result.get("data") or []:
        if order.get("target") != "position":
            continue
        row_result = db.get_row(signal["name"], "id", order["ticket"])
        row = row_result.get("data") if row_result.get("success") else None
        if not row or not row.get("id"):
            continue

        trailing_key = "trailing:%s" % order["ticket"]
        trailing = {"reason": "trailing sl not enabled"}
        if signal["use_trailing_sl"]:
            trailing = atr_step_trailing(order, df, row["pos"], entry_tf)
            reason = trailing.get("reason")
            if reason in _TRAILING_FAILURES:
                log_error(
                    "Stop-loss update failed for %s position %s: %s"
                    % (symbol, order["ticket"], trailing.get("modify_result", reason)),
                    event_key=trailing_key,
                )
            else:
                clear_alert(trailing_key)
        print(
            "%s: Tracking order %s | trailing SL status: %s"
            % (symbol, row.get("id"), trailing.get("reason", "unknown"))
        )

        if signal["sl_type"] == "custom":
            exit_signal = signal["custom_sl"]
            if exit_signal(df, len(df) - 1, row.get("pos")):
                close_result = close_order(row.get("id"), magic=signal["magic"])
                close_key = "close_order:%s" % row.get("id")
                if close_result.get("success"):
                    clear_alert(close_key)
                    log_event(
                        "Closed %s trade %s on %s."
                        % (signal.get("name", "Signal"), row.get("id"), symbol),
                        notification_type="trade_closed",
                    )
                else:
                    log_error(
                        "Failed to close %s trade %s on %s: %s"
                        % (
                            signal.get("name", "Signal"),
                            row.get("id"),
                            symbol,
                            close_result.get("error"),
                        ),
                        event_key=close_key,
                    )


def _wait_for_stop(stop_event, seconds):
    """Wait for the next bot pass, returning early when shutdown is requested."""
    if stop_event is None:
        time.sleep(seconds)
        return False
    return stop_event.wait(seconds)


def run_bot(stop_event=None):
    """Run the live bot until stopped, finishing the current signal pass first."""
    db = Database(active_config["name"])
    connection = {}
    try:
        if initialize_telegram():
            configure_notification_state(db)
        connection = connect(active_config["auth"])
        if (
            not connection.get("success")
            or connection.get("error") is not None
            or connection.get("account_info") is None
            or connection.get("terminal_info") is None
        ):
            log_error(
                "MetaTrader 5 connection failed: %s" % connection.get("error"),
                event_key="mt5_connection",
            )
            raise SystemExit(1)
        clear_alert("mt5_connection")
        _run_connected_bot(stop_event, db)
    finally:
        if connection.get("success"):
            mt5.shutdown()
        close = getattr(db, "close", None)
        if callable(close):
            close()


def _run_connected_bot(stop_event, db=None):
    account = Account()
    if db is None:
        db = Database(active_config["name"])
        if initialize_telegram():
            configure_notification_state(db)
    symbols = active_config["symbols"]
    date_range = active_config["date_range"]
    timeframes = active_config["timeframes"]
    indicators = active_config["indicators"]
    entry_tf = active_config["entry_tf"]
    daily_dd = active_config["daily_dd"]
    max_dd = active_config["maximum_dd"]
    signals = active_config["signals"]

    account.set_account_info(daily_dd, max_dd)
    print(account.get_account_info())

    if startup_report_enabled():
        try:
            startup_report(signals, db=db)
        except Exception as exc:
            log_error(
                "Telegram startup report failed: %s" % exc,
                event_key="telegram_startup_report_runtime",
            )

    while stop_event is None or not stop_event.is_set():
        try:
            daily_log(signals, db)
        except Exception as exc:
            log_error(
                "Daily Telegram report failed: %s" % exc,
                event_key="telegram_daily_report_runtime",
            )

        try:
            price_data = PriceDataCollection(
                symbols=symbols,
                timeframes=timeframes,
                date_range=date_range,
                indicators=indicators,
            )
            clear_alert("price_data_collection")
        except Exception as exc:
            log_error(
                "Price data initialization failed: %s" % exc,
                event_key="price_data_collection",
            )
            if _wait_for_stop(stop_event, active_config["sleep_time"]):
                break
            continue

        account_info = account.get_account_info()
        for signal in signals:
            print("------ Passing through %s signal --------" % signal["name"])
            for symbol in price_data.get_symbols((signal["allowed_symbols"])):
                process_signal_symbol(
                    price_data,
                    signal,
                    symbol,
                    db,
                    daily_dd,
                    max_dd,
                    entry_tf,
                )
        if _wait_for_stop(stop_event, active_config["sleep_time"]):
            break

if __name__ == "__main__":
    run_bot()
