"""Telegram notifications for the live trading bot."""

from datetime import datetime, time, timedelta, timezone
import html
import logging
import os
import re
import time as monotonic_time
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5
import requests

from order import open_orders, order_history


logger = logging.getLogger(__name__)
_LAGOS = ZoneInfo("Africa/Lagos")
_REQUEST_TIMEOUT_SECONDS = 8
_MESSAGE_LIMIT = 4096
_ALERT_COOLDOWN_SECONDS = 5 * 60
_REPORT_TABLE = "telegram_daily_report"
_missing_config_warned = False
_recent_alerts = {}
_delivery_retry_after = 0.0
_last_delivery_failure_logged = None


def initialize_telegram():
    """Check Telegram configuration and warn once if notifications are off."""
    global _missing_config_warned

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        return True

    if not _missing_config_warned:
        logger.warning(
            "Telegram notifications are disabled; set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID to enable them."
        )
        _missing_config_warned = True
    return False


def _safe_text(value):
    text = str(value)
    secret_names = (
        "TELEGRAM_BOT_TOKEN",
        "PASSWORD",
        "DERIV_PASSWORD",
        "EXNESS_PASSWORD",
        "OPENAI_API_KEY",
        "AGENTROUTER_API_KEY",
    )
    for name in secret_names:
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def _split_message(text, limit=_MESSAGE_LIMIT):
    """Split a plain-text report at blank lines, then at line boundaries."""
    sections = text.split("\n\n")
    chunks = []
    current = ""

    def append_section(section):
        nonlocal current
        if len(section) <= limit:
            candidate = section if not current else current + "\n\n" + section
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = section
            return

        if current:
            chunks.append(current)
            current = ""
        lines = section.splitlines() or [section]
        for line in lines:
            if len(line) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                for offset in range(0, len(line), limit):
                    piece = line[offset:offset + limit]
                    if len(piece) == limit:
                        chunks.append(piece)
                    else:
                        current = piece
            else:
                candidate = line if not current else current + "\n" + line
                if len(candidate) <= limit:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = line

    for section in sections:
        append_section(section)
    if current:
        chunks.append(current)
    return chunks or [""]


def _split_html_tokens(section, limit=_MESSAGE_LIMIT):
    """Split an HTML report section without cutting tags or entities."""
    token_pattern = re.compile(
        r"</?b>|&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);|.",
        re.DOTALL,
    )
    chunks = []
    current = ""
    visible_length = 0
    open_bold = 0

    for token in token_pattern.findall(section):
        if token == "<b>":
            current += token
            open_bold += 1
            continue
        if token == "</b>":
            current += token
            open_bold = max(0, open_bold - 1)
            continue

        token_length = 1 if token.startswith("&") and token.endswith(";") else len(token)
        if visible_length + token_length > limit and current:
            chunks.append(current + "</b>" * open_bold)
            current = "<b>" * open_bold
            visible_length = 0
        current += token
        visible_length += token_length

    if current:
        chunks.append(current + "</b>" * open_bold)
    return chunks or [""]


def _split_html_message(text, limit=_MESSAGE_LIMIT):
    """Split HTML reports at section boundaries while keeping tags balanced."""
    chunks = []
    current = ""

    for section in text.split("\n\n"):
        candidate = section if not current else current + "\n\n" + section
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""
        if len(section) <= limit:
            current = section
            continue
        section_chunks = _split_html_tokens(section, limit)
        chunks.extend(section_chunks[:-1])
        current = section_chunks[-1]

    if current:
        chunks.append(current)
    return chunks or [""]


def send_message(text, parse_mode=None):
    """Send a Telegram Bot API message; failures never escape."""
    global _delivery_retry_after, _last_delivery_failure_logged

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        initialize_telegram()
        return False
    if monotonic_time.monotonic() < _delivery_retry_after:
        return False

    url = "https://api.telegram.org/bot%s/sendMessage" % token
    safe_text = _safe_text(text)
    chunks = _split_html_message(safe_text) if parse_mode == "HTML" else _split_message(safe_text)
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            if not 200 <= response.status_code < 300:
                _note_delivery_failure(
                    "Telegram sendMessage failed with HTTP status %s.",
                    response.status_code,
                )
                return False
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                _note_delivery_failure("Telegram sendMessage was rejected by the Bot API.")
                return False
        except requests.RequestException as exc:
            # Do not log the exception text: request errors can include the URL,
            # which contains the bot token.
            _note_delivery_failure(
                "Telegram delivery failed (%s).",
                type(exc).__name__,
            )
            return False
        except (TypeError, ValueError) as exc:
            _note_delivery_failure(
                "Telegram returned an invalid response (%s).",
                type(exc).__name__,
            )
            return False
    _delivery_retry_after = 0.0
    _last_delivery_failure_logged = None
    return True


def _note_delivery_failure(message, *args):
    global _delivery_retry_after, _last_delivery_failure_logged

    now = monotonic_time.monotonic()
    _delivery_retry_after = now + 30
    if (
        _last_delivery_failure_logged is None
        or now - _last_delivery_failure_logged >= _ALERT_COOLDOWN_SECONDS
    ):
        logger.error(message, *args)
        _last_delivery_failure_logged = now


def _alert_key(message, event_key):
    return str(event_key) if event_key is not None else "%s:%s" % (message[:100], message)


def clear_alert(event_key):
    """Clear a repeated-alert cooldown after its condition recovers."""
    _recent_alerts.pop(str(event_key), None)


def log_event(message, severity="info"):
    """Send a non-repeating informational event such as an order open/close."""
    safe_message = _safe_text(message)
    level = getattr(logging, str(severity).upper(), logging.INFO)
    logger.log(level, safe_message)
    return send_message(safe_message)


def log_error(error, event_key=None, severity="error"):
    """Send an operational alert, suppressing repeats for five minutes."""
    safe_message = _safe_text(error)
    level = getattr(logging, str(severity).upper(), logging.ERROR)
    logger.log(level, safe_message)

    key = _alert_key(safe_message, event_key)
    now = monotonic_time.monotonic()
    previous = _recent_alerts.get(key)
    if previous is not None and now - previous < _ALERT_COOLDOWN_SECONDS:
        return False
    _recent_alerts[key] = now
    return send_message(safe_message)


def _as_float(value):
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return result if result == result and abs(result) != float("inf") else 0.0


def _summarize_signal(signal, deals, positions):
    entry_in = getattr(mt5, "DEAL_ENTRY_IN", 0)
    reversal_entry = getattr(mt5, "DEAL_ENTRY_INOUT", 2)
    closing_entries = {
        getattr(mt5, "DEAL_ENTRY_OUT", 1),
        reversal_entry,
        getattr(mt5, "DEAL_ENTRY_OUT_BY", 3),
    }
    opened_positions = set()
    closed_positions = set()
    symbols = set()
    realized_net = 0.0

    for deal in deals:
        if deal.get("magic") != signal["magic"]:
            continue
        position_id = deal.get("position_id", deal.get("order", deal.get("ticket")))
        entry = deal.get("entry")
        if entry in {entry_in, reversal_entry}:
            opened_positions.add(position_id)
        if entry in closing_entries:
            closed_positions.add(position_id)
        symbol = deal.get("symbol")
        if symbol:
            symbols.add(str(symbol))
        realized_net += sum(
            _as_float(deal.get(field))
            for field in ("profit", "commission", "swap", "fee")
        )

    signal_positions = [
        position
        for position in positions
        if position.get("target") == "position"
        and position.get("magic") == signal["magic"]
    ]
    for position in signal_positions:
        if position.get("symbol"):
            symbols.add(str(position["symbol"]))

    floating = sum(
        _as_float(position.get("profit")) + _as_float(position.get("swap"))
        for position in signal_positions
    )
    return {
        "name": signal.get("name", "Signal"),
        "opened": len(opened_positions - {None}),
        "closed": len(closed_positions - {None}),
        "symbols": sorted(symbols),
        "realized_net": realized_net,
        "open_count": len(signal_positions),
        "floating": floating,
    }


def _deals_by_signal(signals, date_from, date_to):
    """Load period deals and attribute untagged exits by their position owner."""
    signals_by_magic = {signal["magic"]: signal for signal in signals}
    history = order_history(date_from=date_from, date_to=date_to)
    if not history.get("success"):
        return None, history.get("error")

    deals = history.get("data") or []
    opening_entries = {
        getattr(mt5, "DEAL_ENTRY_IN", 0),
        getattr(mt5, "DEAL_ENTRY_INOUT", 2),
    }
    closing_entries = {
        getattr(mt5, "DEAL_ENTRY_OUT", 1),
        getattr(mt5, "DEAL_ENTRY_INOUT", 2),
        getattr(mt5, "DEAL_ENTRY_OUT_BY", 3),
    }
    position_magic = {}

    # Deals opened during this report period already carry the strategy magic.
    for deal in deals:
        magic = deal.get("magic")
        position_id = deal.get("position_id")
        if (
            magic in signals_by_magic
            and deal.get("entry") in opening_entries
            and position_id not in (None, 0)
        ):
            position_magic[position_id] = magic

    # Exit orders may have magic=0 (for example, older bot closes). Resolve
    # their owner from the complete history for that position, including opens
    # before the report interval.
    unresolved_positions = {
        deal.get("position_id")
        for deal in deals
        if deal.get("magic") not in signals_by_magic
        and deal.get("entry") in closing_entries
        and deal.get("position_id") not in (None, 0)
        and deal.get("position_id") not in position_magic
    }
    for position_id in unresolved_positions:
        position_history = order_history(position=position_id)
        if not position_history.get("success"):
            return None, "position %s: %s" % (
                position_id,
                position_history.get("error"),
            )
        owners = {
            deal.get("magic")
            for deal in (position_history.get("data") or [])
            if deal.get("entry") in opening_entries
            and deal.get("magic") in signals_by_magic
        }
        if len(owners) > 1:
            return None, "position %s has conflicting signal magic numbers." % position_id
        if owners:
            position_magic[position_id] = next(iter(owners))

    deals_by_magic = {magic: [] for magic in signals_by_magic}
    for deal in deals:
        magic = deal.get("magic")
        owner_magic = (
            magic
            if magic in signals_by_magic
            else position_magic.get(deal.get("position_id"))
        )
        if owner_magic is None:
            continue
        attributed_deal = dict(deal)
        attributed_deal["magic"] = owner_magic
        deals_by_magic[owner_magic].append(attributed_deal)
    return deals_by_magic, None


def _build_daily_report(
    report_date,
    signals,
    deals_by_magic,
    positions,
    title="Daily trading report",
    period_label="Date",
):
    sections = [
        "📊 <b>%s</b>\n📅 <b>%s:</b> %s (Africa/Lagos)"
        % (html.escape(title), html.escape(period_label), report_date.isoformat())
    ]
    for signal in signals:
        summary = _summarize_signal(
            signal,
            deals_by_magic.get(signal["magic"], []),
            positions,
        )
        name = str(summary["name"])
        name_parts = [name[index:index + 400] for index in range(0, len(name), 400)] or [""]
        signal_lines = ["🧭 <b>Signal: %s</b>" % html.escape(name_parts[0])]
        signal_lines.extend(
            "   <b>%s</b>" % html.escape(part) for part in name_parts[1:]
        )
        signal_lines.append(
            "🔄 <b>Trades:</b> Opened %s · Closed %s"
            % (summary["opened"], summary["closed"])
        )

        symbol_text = ", ".join(summary["symbols"]) or "None"
        symbol_parts = [
            symbol_text[index:index + 400]
            for index in range(0, len(symbol_text), 400)
        ] or [""]
        signal_lines.append("🔎 <b>Symbols:</b> %s" % html.escape(symbol_parts[0]))
        signal_lines.extend("   %s" % html.escape(part) for part in symbol_parts[1:])

        realized_emoji = "🟢" if summary["realized_net"] >= 0 else "🔴"
        floating_emoji = "🟢" if summary["floating"] >= 0 else "🔴"
        signal_lines.extend(
            [
                "%s <b>Realized net P&amp;L:</b> <b>%.2f</b>"
                % (realized_emoji, summary["realized_net"]),
                "📂 <b>Open positions:</b> %s" % summary["open_count"],
                "%s <b>Floating P&amp;L:</b> <b>%.2f</b>"
                % (floating_emoji, summary["floating"]),
            ]
        )
        sections.append("\n".join(signal_lines))
    return "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(sections)


def _lagos_day_bounds(now=None):
    if now is None:
        local_now = datetime.now(_LAGOS)
    elif now.tzinfo is None or now.utcoffset() is None:
        local_now = now.replace(tzinfo=_LAGOS)
    else:
        local_now = now.astimezone(_LAGOS)
    report_date = local_now.date() - timedelta(days=1)
    local_start = datetime.combine(report_date, time.min, tzinfo=_LAGOS)
    local_end = local_start + timedelta(days=1)
    return (
        report_date,
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


def _lagos_today_bounds(now=None):
    """Return today's Lagos date and the UTC interval from midnight to now."""
    if now is None:
        local_now = datetime.now(_LAGOS)
    elif now.tzinfo is None or now.utcoffset() is None:
        local_now = now.replace(tzinfo=_LAGOS)
    else:
        local_now = now.astimezone(_LAGOS)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=_LAGOS)
    return (
        local_now.date(),
        local_start.astimezone(timezone.utc),
        local_now.astimezone(timezone.utc),
    )


def startup_report_enabled():
    """Whether the temporary today-so-far startup report is enabled."""
    return os.getenv("TELEGRAM_REPORT_ON_START", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def startup_report(signals, now=None):
    """Send today's Lagos report through the current time without saved state."""
    if not signals or not initialize_telegram():
        return False

    report_date, date_from, date_to = _lagos_today_bounds(now)
    deals_by_magic, history_error = _deals_by_signal(signals, date_from, date_to)
    if history_error:
        log_error(
            "Unable to attribute trade history for the Telegram startup report: %s"
            % history_error,
            event_key="telegram_startup_history",
        )
        return False
    clear_alert("telegram_startup_history")

    open_result = open_orders()
    if not open_result.get("success"):
        log_error(
            "Unable to read open positions for the Telegram startup report: %s"
            % open_result.get("error"),
            event_key="telegram_startup_positions",
        )
        return False
    clear_alert("telegram_startup_positions")

    message = _build_daily_report(
        report_date,
        signals,
        deals_by_magic,
        open_result.get("data") or [],
        title="Today so far trading report",
        period_label="Date",
    )
    return send_message(message, parse_mode="HTML")


def _report_state(db):
    created = db.create_table(_REPORT_TABLE, {"id": 1, "report_date": ""})
    if not created.get("success"):
        return None, created.get("error")
    row = db.get_row(_REPORT_TABLE, "id", 1)
    if row.get("success"):
        return row["data"].get("report_date", ""), None
    inserted = db.add_to_table(_REPORT_TABLE, {"id": 1, "report_date": ""})
    if not inserted.get("success"):
        return None, inserted.get("error")
    return "", None


def daily_log(signals, db, now=None):
    """Send yesterday's Lagos-day report once, persisting successful sends."""
    if not signals or not initialize_telegram():
        return False

    report_date, date_from, date_to = _lagos_day_bounds(now)
    state_date, state_error = _report_state(db)
    if state_error:
        log_error(
            "Unable to read Telegram report state: %s" % state_error,
            event_key="telegram_report_state",
        )
        return False
    if state_date == report_date.isoformat():
        clear_alert("telegram_daily_report")
        return False

    deals_by_magic, history_error = _deals_by_signal(signals, date_from, date_to)
    if history_error:
        log_error(
            "Unable to attribute trade history for the Telegram report: %s"
            % history_error,
            event_key="telegram_daily_history",
        )
        return False
    clear_alert("telegram_daily_history")

    open_result = open_orders()
    if not open_result.get("success"):
        log_error(
            "Unable to read open positions for the Telegram report: %s"
            % open_result.get("error"),
            event_key="telegram_daily_positions",
        )
        return False
    clear_alert("telegram_daily_positions")

    message = _build_daily_report(
        report_date,
        signals,
        deals_by_magic,
        open_result.get("data") or [],
    )
    if not send_message(message, parse_mode="HTML"):
        # send_message already logs a token-safe local delivery error. Avoid
        # immediately retrying the same failed Telegram request as an alert.
        return False

    updated = db.update_row(
        _REPORT_TABLE,
        {"id": 1, "report_date": report_date.isoformat()},
    )
    if not updated.get("success"):
        log_error(
            "Telegram report sent, but its date could not be persisted: %s"
            % updated.get("error"),
            event_key="telegram_report_state",
        )
        return False
    clear_alert("telegram_daily_report")
    clear_alert("telegram_report_state")
    return True
