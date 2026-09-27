import importlib
import html
import logging
import re
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import requests
import pandas as pd

from database import Database
from live_bot import telegram


@pytest.fixture(autouse=True)
def reset_telegram_state(monkeypatch):
    telegram._recent_alerts.clear()
    telegram._delivery_retry_after = 0.0
    telegram._last_delivery_failure_logged = None
    monkeypatch.setattr(telegram, "_missing_config_warned", False)


def _success_response():
    return SimpleNamespace(status_code=200, json=lambda: {"ok": True})


def test_send_message_posts_bot_api_payload(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-value")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-123")
    calls = []
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, **kwargs: calls.append((url, kwargs)) or _success_response(),
    )

    assert telegram.send_message("trade opened") is True
    url, kwargs = calls[0]
    assert url == "https://api.telegram.org/bottoken-value/sendMessage"
    assert kwargs["json"] == {"chat_id": "chat-123", "text": "trade opened"}
    assert kwargs["timeout"] == telegram._REQUEST_TIMEOUT_SECONDS


def test_send_message_adds_html_parse_mode_when_requested(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    calls = []
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, **kwargs: calls.append(kwargs) or _success_response(),
    )

    assert telegram.send_message("<b>report</b>", parse_mode="HTML") is True
    assert calls[0]["json"] == {
        "chat_id": "chat",
        "text": "<b>report</b>",
        "parse_mode": "HTML",
    }


def test_send_message_rejects_http_and_bot_api_failures(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(status_code=401, json=lambda: {"ok": False}),
    )
    assert telegram.send_message("report") is False
    telegram._delivery_retry_after = 0.0

    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"ok": False}),
    )
    assert telegram.send_message("report") is False


@pytest.mark.parametrize("failure", [requests.ConnectionError, requests.Timeout])
def test_send_message_handles_network_errors_without_logging_token(
    monkeypatch, caplog, failure
):
    token = "secret-token"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, **kwargs: (_ for _ in ()).throw(failure("failed at " + url)),
    )

    with caplog.at_level(logging.ERROR):
        assert telegram.send_message("report") is False
    assert token not in caplog.text


def test_missing_configuration_warns_once(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with caplog.at_level(logging.WARNING):
        assert telegram.initialize_telegram() is False
        assert telegram.initialize_telegram() is False
    assert caplog.text.count("Telegram notifications are disabled") == 1


def test_message_chunks_stay_within_telegram_limit(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    chunks = []
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, **kwargs: chunks.append(kwargs["json"]["text"]) or _success_response(),
    )

    assert telegram.send_message("A" * 9000) is True
    assert len(chunks) == 3
    assert all(len(chunk) <= 4096 for chunk in chunks)


def test_html_report_chunks_remain_valid_and_within_text_limit():
    report = "<b>" + ("A &amp; B " * 20) + "</b>\n\n" + ("<b>Signal</b>\n" * 12)
    chunks = telegram._split_html_message(report, limit=40)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(html.unescape(re.sub(r"</?b>", "", chunk))) <= 40
        assert chunk.count("<b>") == chunk.count("</b>")


def test_report_html_escapes_signal_names_and_symbols():
    signal = {"name": "<Ranger & Friends>", "magic": 77}
    report = telegram._build_daily_report(
        datetime(2026, 5, 1).date(),
        [signal],
        {77: [{"magic": 77, "symbol": "EUR<USD", "entry": 0, "position_id": 1}]},
        [],
    )

    assert "&lt;Ranger &amp; Friends&gt;" in report
    assert "EUR&lt;USD" in report
    assert "<Ranger & Friends>" not in report


def test_error_alert_is_rate_limited_and_recovery_clears_it(monkeypatch):
    sent = []
    clock = [100.0]
    monkeypatch.setattr(telegram, "send_message", lambda text: sent.append(text) or True)
    monkeypatch.setattr(telegram.monotonic_time, "monotonic", lambda: clock[0])

    assert telegram.log_error("fetch failed", event_key="fetch:X") is True
    assert telegram.log_error("fetch failed again", event_key="fetch:X") is False
    assert len(sent) == 1
    clock[0] += telegram._ALERT_COOLDOWN_SECONDS
    assert telegram.log_error("fetch failed", event_key="fetch:X") is True
    telegram.clear_alert("fetch:X")
    clock[0] += 1
    assert telegram.log_error("fetch failed", event_key="fetch:X") is True
    assert len(sent) == 3


def test_summary_aggregates_distinct_trades_net_costs_and_filtered_positions(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "mt5",
        SimpleNamespace(
            DEAL_ENTRY_IN=0,
            DEAL_ENTRY_OUT=1,
            DEAL_ENTRY_INOUT=2,
            DEAL_ENTRY_OUT_BY=3,
        ),
    )
    signal = {"name": "Ranger", "magic": 77}
    deals = [
        {"magic": 77, "entry": 0, "position_id": 10, "symbol": "EURUSD", "commission": -0.3},
        {"magic": 77, "entry": 0, "position_id": 10, "symbol": "EURUSD", "commission": -0.2},
        {"magic": 77, "entry": 1, "position_id": 10, "symbol": "EURUSD", "profit": 12, "commission": -0.1, "swap": 0.4, "fee": -0.1},
        {"magic": 77, "entry": 0, "position_id": 11, "symbol": "GBPUSD", "commission": -0.2},
        {"magic": 88, "entry": 1, "position_id": 90, "symbol": "USDJPY", "profit": 900},
    ]
    positions = [
        {"target": "position", "magic": 77, "ticket": 30, "symbol": "USDJPY", "profit": 3, "swap": -0.5},
        {"target": "position", "magic": 88, "ticket": 31, "symbol": "AUDUSD", "profit": 90},
        {"target": "pending", "magic": 77, "ticket": 32, "symbol": "NZDUSD", "profit": 50},
    ]

    result = telegram._summarize_signal(signal, deals, positions)
    assert result == {
        "name": "Ranger",
        "opened": 2,
        "closed": 1,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
        "realized_net": pytest.approx(11.5),
        "open_count": 1,
        "floating": pytest.approx(2.5),
    }


def test_deals_by_signal_maps_zero_magic_close_to_prior_open_and_excludes_manual(
    monkeypatch,
):
    monkeypatch.setattr(
        telegram,
        "mt5",
        SimpleNamespace(
            DEAL_ENTRY_IN=0,
            DEAL_ENTRY_OUT=1,
            DEAL_ENTRY_INOUT=2,
            DEAL_ENTRY_OUT_BY=3,
        ),
    )
    period_start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 2, tzinfo=timezone.utc)
    period_deals = [
        {
            "magic": 0,
            "entry": 1,
            "position_id": 700,
            "symbol": "EURUSD",
            "profit": 12,
            "commission": -0.5,
            "swap": 0.2,
            "fee": -0.1,
        },
        {
            "magic": 0,
            "entry": 1,
            "position_id": 800,
            "symbol": "GBPUSD",
            "profit": 90,
        },
    ]
    history_calls = []

    def order_history(**kwargs):
        history_calls.append(kwargs)
        if "position" not in kwargs:
            return {"success": True, "data": period_deals}
        if kwargs["position"] == 700:
            return {
                "success": True,
                "data": [
                    {
                        "magic": 77,
                        "entry": 0,
                        "position_id": 700,
                        "symbol": "EURUSD",
                        "profit": 0,
                    },
                    period_deals[0],
                ],
            }
        return {
            "success": True,
            "data": [
                {"magic": 0, "entry": 0, "position_id": 800, "symbol": "GBPUSD"},
                period_deals[1],
            ],
        }

    monkeypatch.setattr(telegram, "order_history", order_history)
    grouped, error = telegram._deals_by_signal(
        [{"name": "Ranger", "magic": 77}], period_start, period_end
    )

    assert error is None
    assert history_calls[0] == {"date_from": period_start, "date_to": period_end}
    assert {call.get("position") for call in history_calls[1:]} == {700, 800}
    assert len(grouped[77]) == 1
    assert grouped[77][0]["magic"] == 77
    summary = telegram._summarize_signal(
        {"name": "Ranger", "magic": 77}, grouped[77], []
    )
    assert summary["realized_net"] == pytest.approx(11.6)
    assert summary["closed"] == 1


def test_deals_by_signal_uses_same_period_open_without_position_lookup(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "mt5",
        SimpleNamespace(
            DEAL_ENTRY_IN=0,
            DEAL_ENTRY_OUT=1,
            DEAL_ENTRY_INOUT=2,
            DEAL_ENTRY_OUT_BY=3,
        ),
    )
    history_calls = []
    monkeypatch.setattr(
        telegram,
        "order_history",
        lambda **kwargs: history_calls.append(kwargs)
        or {
            "success": True,
            "data": [
                {"magic": 77, "entry": 0, "position_id": 700, "profit": 0},
                {"magic": 0, "entry": 1, "position_id": 700, "profit": 15},
            ],
        },
    )

    grouped, error = telegram._deals_by_signal(
        [{"name": "Ranger", "magic": 77}],
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 2, tzinfo=timezone.utc),
    )

    assert error is None
    assert len(history_calls) == 1
    assert [deal["magic"] for deal in grouped[77]] == [77, 77]
    assert telegram._summarize_signal(
        {"name": "Ranger", "magic": 77}, grouped[77], []
    )["realized_net"] == 15


def test_reversal_deal_counts_as_both_open_and_close(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "mt5",
        SimpleNamespace(
            DEAL_ENTRY_IN=0,
            DEAL_ENTRY_OUT=1,
            DEAL_ENTRY_INOUT=2,
            DEAL_ENTRY_OUT_BY=3,
        ),
    )
    summary = telegram._summarize_signal(
        {"name": "Ranger", "magic": 77},
        [{"magic": 77, "entry": 2, "position_id": 9, "symbol": "EURUSD"}],
        [],
    )
    assert summary["opened"] == 1
    assert summary["closed"] == 1


def test_lagos_bounds_cover_previous_local_calendar_day():
    local_midnight = datetime(2026, 5, 2, 0, 0, tzinfo=ZoneInfo("Africa/Lagos"))
    report_date, start, end = telegram._lagos_day_bounds(local_midnight)
    assert report_date.isoformat() == "2026-05-01"
    assert start == datetime(2026, 4, 30, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 1, 23, 0, tzinfo=timezone.utc)


def test_lagos_today_bounds_cover_midnight_through_now():
    now = datetime(2026, 5, 2, 14, 30, tzinfo=ZoneInfo("Africa/Lagos"))
    report_date, start, end = telegram._lagos_today_bounds(now)
    assert report_date.isoformat() == "2026-05-02"
    assert start == datetime(2026, 5, 1, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 2, 13, 30, tzinfo=timezone.utc)


def test_startup_report_sends_today_so_far_each_call_without_scheduled_state(
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    now = datetime(2026, 5, 2, 14, 30, tzinfo=ZoneInfo("Africa/Lagos"))
    history_calls = []
    messages = []
    monkeypatch.setattr(
        telegram,
        "order_history",
        lambda **kwargs: history_calls.append(kwargs)
        or {"success": True, "data": []},
    )
    monkeypatch.setattr(
        telegram,
        "open_orders",
        lambda **kwargs: {"success": True, "data": []},
    )
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda message, **kwargs: messages.append((message, kwargs)) or True,
    )
    signals = [{"name": "Ranger", "magic": 77}]

    assert telegram.startup_report(signals, now=now) is True
    assert telegram.startup_report(signals, now=now) is True
    assert len(messages) == 2
    assert all("Today so far trading report" in message for message, _ in messages)
    assert all("2026-05-02" in message for message, _ in messages)
    assert all(options == {"parse_mode": "HTML"} for _, options in messages)
    assert len(history_calls) == 2
    for history_call in history_calls:
        assert history_call["date_from"] == datetime(
            2026, 5, 1, 23, 0, tzinfo=timezone.utc
        )
        assert history_call["date_to"] == datetime(
            2026, 5, 2, 13, 30, tzinfo=timezone.utc
        )
        assert "magic" not in history_call


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " TRUE "])
def test_startup_report_setting_accepts_truthy_values(monkeypatch, value):
    monkeypatch.setenv("TELEGRAM_REPORT_ON_START", value)
    assert telegram.startup_report_enabled() is True


@pytest.mark.parametrize("value", [None, "", "false", "0", "off"])
def test_startup_report_setting_is_off_by_default(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("TELEGRAM_REPORT_ON_START", raising=False)
    else:
        monkeypatch.setenv("TELEGRAM_REPORT_ON_START", value)
    assert telegram.startup_report_enabled() is False


def test_daily_report_sends_once_and_persists_success(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    calls = []
    monkeypatch.setattr(
        telegram,
        "order_history",
        lambda **kwargs: calls.append(("history", kwargs)) or {"success": True, "data": []},
    )
    monkeypatch.setattr(
        telegram,
        "open_orders",
        lambda **kwargs: calls.append(("positions", kwargs)) or {"success": True, "data": []},
    )
    messages = []
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda text, **kwargs: messages.append((text, kwargs)) or True,
    )
    db_path = tmp_path / "bot.sqlite3"
    db = Database(str(db_path))
    now = datetime(2026, 5, 2, 0, 0, tzinfo=ZoneInfo("Africa/Lagos"))
    signals = [{"name": "Ranger", "magic": 77}]
    try:
        assert telegram.daily_log(signals, db, now=now) is True
        assert telegram.daily_log(signals, db, now=now) is False
        assert len(messages) == 1
        assert "2026-05-01" in messages[0][0]
        assert messages[0][1] == {"parse_mode": "HTML"}
        history_args = next(args for kind, args in calls if kind == "history")
        assert history_args["date_from"] == datetime(2026, 4, 30, 23, 0, tzinfo=timezone.utc)
        assert history_args["date_to"] == datetime(2026, 5, 1, 23, 0, tzinfo=timezone.utc)
        assert "magic" not in history_args
        db.close()
        db = Database(str(db_path))
        assert telegram.daily_log(signals, db, now=now) is False
        assert len(messages) == 1
    finally:
        db.close()


def test_failed_daily_delivery_is_retried(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(
        telegram,
        "order_history",
        lambda **kwargs: {"success": True, "data": []},
    )
    monkeypatch.setattr(
        telegram,
        "open_orders",
        lambda **kwargs: {"success": True, "data": []},
    )
    sends = iter((False, True))
    monkeypatch.setattr(telegram, "send_message", lambda text, **kwargs: next(sends))
    db = Database(":memory:")
    now = datetime(2026, 5, 2, 0, 0, tzinfo=ZoneInfo("Africa/Lagos"))
    try:
        assert telegram.daily_log([{"name": "Ranger", "magic": 77}], db, now=now) is False
        assert telegram.daily_log([{"name": "Ranger", "magic": 77}], db, now=now) is True
    finally:
        db.close()


def test_failed_position_attribution_does_not_send_or_mark_report_sent(
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(
        telegram,
        "order_history",
        lambda **kwargs: (
            {"success": True, "data": [{"magic": 0, "entry": 1, "position_id": 700}]}
            if "position" not in kwargs
            else {"success": False, "data": None, "error": {"message": "unavailable"}}
        ),
    )
    monkeypatch.setattr(
        telegram,
        "log_error",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        telegram,
        "open_orders",
        lambda **kwargs: pytest.fail("open positions should not be read"),
    )
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda *args, **kwargs: pytest.fail("incomplete report must not be sent"),
    )
    db = Database(":memory:")
    now = datetime(2026, 5, 2, 0, 0, tzinfo=ZoneInfo("Africa/Lagos"))

    try:
        assert telegram.daily_log([{"name": "Ranger", "magic": 77}], db, now=now) is False
        assert telegram._report_state(db)[0] == ""
    finally:
        db.close()


def test_live_loop_reports_price_data_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or True,
    )

    class BrokenPriceData:
        def get_price_data(self, symbol):
            raise RuntimeError("no candles")

    signal = {
        "name": "Ranger",
        "magic": 77,
    }
    assert live_bot.process_signal_symbol(
        BrokenPriceData(), signal, "EURUSD", None, 0.2, 0.8, "M15"
    ) is True
    assert events[0][1]["event_key"] == "price_data:EURUSD"


def test_live_loop_alerts_on_mt5_connection_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    monkeypatch.setattr(live_bot, "initialize_telegram", lambda: False)
    monkeypatch.setattr(
        live_bot,
        "connect",
        lambda auth: {"success": False, "error": {"message": "terminal unavailable"}},
    )
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or False,
    )

    with pytest.raises(SystemExit):
        live_bot.run_bot()
    assert events[0][1]["event_key"] == "mt5_connection"


def test_live_loop_alerts_when_connection_metadata_is_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    monkeypatch.setattr(live_bot, "initialize_telegram", lambda: False)
    monkeypatch.setattr(
        live_bot,
        "connect",
        lambda auth: {
            "success": True,
            "account_info": None,
            "terminal_info": None,
            "error": {"message": "metadata unavailable"},
        },
    )
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or False,
    )

    with pytest.raises(SystemExit):
        live_bot.run_bot()
    assert events[0][1]["event_key"] == "mt5_connection"


@pytest.mark.parametrize(
    "reason",
    [
        "Trading session is not active.",
        "Weekend trading is not allowed.",
        "An order or position already exists for EURUSD.",
        "No signal.",
    ],
)
def test_non_drawdown_trading_status_is_not_logged(monkeypatch, capsys, reason):
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    cleared = []
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or True,
    )
    monkeypatch.setattr(live_bot, "clear_alert", lambda key: cleared.append(key))

    live_bot._report_drawdown_status(
        {"name": "Ranger", "magic": 77},
        "EURUSD",
        {"status": "blocked", "reason": reason},
    )

    assert events == []
    assert "STATUS:" not in capsys.readouterr().out
    assert cleared == [
        "trading_drawdown:daily:77:EURUSD",
        "trading_drawdown:maximum:77:EURUSD",
    ]


@pytest.mark.parametrize(
    "reason,expected_key,expected_phrase",
    [
        (
            "Daily drawdown limit reached (5.00%). Trading session is not active.",
            "trading_drawdown:daily:77:EURUSD",
            "Daily drawdown limit reached (5.00%).",
        ),
        (
            "Maximum drawdown limit reached (10.00%). Weekend trading is not allowed.",
            "trading_drawdown:maximum:77:EURUSD",
            "Maximum drawdown limit reached (10.00%).",
        ),
        (
            "Account has reached daily drawdown Trading session is not active. "
            "Account has reached maximum drawdown An order already exists.",
            None,
            "Account has reached",
        ),
    ],
)
def test_only_drawdown_reasons_are_logged_and_displayed(
    monkeypatch, capsys, reason, expected_key, expected_phrase
):
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or True,
    )
    monkeypatch.setattr(live_bot, "clear_alert", lambda key: None)

    live_bot._report_drawdown_status(
        {"name": "Ranger", "magic": 77},
        "EURUSD",
        {"status": "blocked", "reason": reason},
    )

    output = capsys.readouterr().out
    assert expected_phrase in output
    assert "Trading session" not in output
    assert "Weekend" not in output
    assert "existing" not in output
    if expected_key:
        assert len(events) == 1
        assert events[0][1]["event_key"] == expected_key
        assert expected_phrase in events[0][0]
        assert "Trading session" not in events[0][0]
        assert "Weekend" not in events[0][0]
    else:
        assert len(events) == 2
        assert all("Trading session" not in message for message, _ in events)
        assert all("An order" not in message for message, _ in events)


def test_drawdown_recovery_clears_independent_alert_cooldowns(monkeypatch):
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []
    cleared = []
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or True,
    )
    monkeypatch.setattr(live_bot, "clear_alert", lambda key: cleared.append(key))
    signal = {"name": "Ranger", "magic": 77}

    live_bot._report_drawdown_status(
        signal,
        "EURUSD",
        {
            "status": "blocked",
            "reason": "Daily drawdown limit reached (5.00%). Maximum drawdown limit reached (10.00%).",
        },
    )
    live_bot._report_drawdown_status(
        signal,
        "EURUSD",
        {"status": "blocked", "reason": "Daily drawdown limit reached (5.00%)."},
    )
    assert "trading_drawdown:maximum:77:EURUSD" in cleared
    live_bot._report_drawdown_status(
        signal,
        "EURUSD",
        {"status": "blocked", "reason": "Trading session is not active."},
    )
    assert "trading_drawdown:daily:77:EURUSD" in cleared


@pytest.mark.parametrize(
    "reason,allowed",
    [
        ("Daily drawdown limit reached (5.00%).", False),
        ("Account has reached maximum drawdown", False),
        (
            "Daily drawdown limit reached (5.00%). Maximum drawdown limit reached (10.00%).",
            False,
        ),
        ("Trading session is not active.", True),
        ("Weekend trading is not allowed.", True),
        ("Trading is allowed.", True),
    ],
)
def test_quantnoon_new_entries_are_suppressed_only_for_drawdown(reason, allowed):
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")

    assert live_bot._allow_quantnoon_signal({"status": "blocked", "reason": reason}) is allowed


def test_custom_close_request_uses_signal_magic(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    frame = pd.DataFrame({"close_M15": [1.25], "time": [datetime(2026, 5, 1)]})
    close_calls = []

    class FakePriceData:
        def get_price_data(self, symbol):
            return frame

    class FakeDatabase:
        def get_row(self, table, key, value):
            return {"success": True, "data": {"id": 700, "pos": "buy"}}

    signal = {
        "name": "Ranger",
        "magic": 77,
        "signal": lambda data, index: (None, None),
        "trading_sessions": [],
        "allow_many_trades": True,
        "is_weekend_trading": True,
        "sl_type": "custom",
        "entry_tf": "M15",
        "custom_sl": lambda data, index, position: True,
        "use_trailing_sl": False,
    }
    monkeypatch.setattr(
        live_bot,
        "can_trade",
        lambda config: {"status": "can_trade", "reason": "Trading is allowed."},
    )
    monkeypatch.setattr(live_bot, "quantnoon_signal_provider", lambda **kwargs: None)
    monkeypatch.setattr(
        live_bot,
        "open_orders",
        lambda **kwargs: {
            "success": True,
            "data": [{"target": "position", "ticket": 700, "symbol": "EURUSD"}],
        },
    )
    monkeypatch.setattr(
        live_bot,
        "close_order",
        lambda *args, **kwargs: close_calls.append((args, kwargs))
        or {"success": True},
    )
    monkeypatch.setattr(live_bot, "log_event", lambda *args, **kwargs: True)

    assert live_bot.process_signal_symbol(
        FakePriceData(), signal, "EURUSD", FakeDatabase(), 0.2, 0.8, "M15"
    ) is True
    assert close_calls == [((700,), {"magic": 77})]


def test_startup_report_failure_does_not_prevent_trading_loop_or_drawdown_spam(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("live_bot.live_bot", None)
    live_bot = importlib.import_module("live_bot.live_bot")
    events = []

    class StopLoop(Exception):
        pass

    class FakeAccount:
        def set_account_info(self, daily_dd, max_dd):
            pass

        def get_account_info(self):
            return {"today_drawdown": 0, "maximum_drawdown": 0}

    class FakePriceData:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(live_bot, "initialize_telegram", lambda: True)
    monkeypatch.setattr(
        live_bot,
        "connect",
        lambda auth: {
            "success": True,
            "error": None,
            "account_info": {},
            "terminal_info": {},
        },
    )
    monkeypatch.setattr(live_bot, "Account", FakeAccount)
    monkeypatch.setattr(live_bot, "Database", lambda name: object())
    monkeypatch.setattr(live_bot, "PriceDataCollection", FakePriceData)
    monkeypatch.setattr(live_bot, "daily_log", lambda *args: False)
    monkeypatch.setattr(live_bot, "startup_report_enabled", lambda: True)
    monkeypatch.setattr(
        live_bot,
        "startup_report",
        lambda signals: (_ for _ in ()).throw(RuntimeError("Telegram unavailable")),
    )
    monkeypatch.setattr(
        live_bot,
        "log_error",
        lambda message, **kwargs: events.append((message, kwargs)) or False,
    )
    monkeypatch.setattr(live_bot.time, "sleep", lambda seconds: (_ for _ in ()).throw(StopLoop()))
    monkeypatch.setattr(
        live_bot,
        "active_config",
        {
            "auth": {},
            "name": "test",
            "symbols": [],
            "date_range": 1,
            "timeframes": [],
            "indicators": [],
            "entry_tf": "M1",
            "daily_dd": 0.2,
            "maximum_dd": 0.8,
            "signals": [],
            "sleep_time": 1,
        },
    )

    with pytest.raises(StopLoop):
        live_bot.run_bot()
    assert events[0][1]["event_key"] == "telegram_startup_report_runtime"
    output = capsys.readouterr().out
    assert "Daily drawdown at:" not in output
    assert "Maximum drawdown at:" not in output
