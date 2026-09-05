import json

import pandas as pd
import pytest

from backtest_tools import _webview_strategies, write_webview_resources


def frame():
    return pd.DataFrame({
        "time": ["2026-08-25T12:00:00Z", "2026-08-25T12:15:00Z"],
        "open_M15": [1.0, 1.5], "high_M15": [2.0, 2.5],
        "low_M15": [0.5, 1.0], "close_M15": [1.5, 2.0], "volume_M15": [10, 20],
    })


def report():
    return {
        "profit_factor": float("inf"),
        "trade_log": pd.DataFrame([{
            "position": "buy", "entry": 1.5, "exit": 2.0,
            "open_time": "2026-08-25T12:00:00Z", "close_time": "2026-08-25T12:15:00Z",
            "result": "win", "pnl": 0.5, "pnl_dollar": 2.5, "pnl_currency": 2.5,
            "balance_before": 100.0, "balance_after": 102.5, "session": "asian",
            "day": "Monday", "skipped": False, "skip_reason": None,
        }]),
    }


def test_writes_one_multi_symbol_resource_set_per_strategy(tmp_path):
    symbols = ["EURUSD", "GBPUSD"]
    strategy_name = "support_resistance"
    webview_dir = tmp_path / "webview" / "strategies"
    webview_dir.parent.mkdir()
    result = {
        symbol: [{"name": strategy_name, "report": report()}]
        for symbol in symbols
    }

    write_webview_resources(
        webview_dir, symbols, (strategy_name, lambda _df, _index: None), result,
        {symbol: frame() for symbol in symbols}, "M15",
        [{"indicator": "SUPPORT_ZONE", "timeframe": "H4"}],
    )

    strategy_dir = webview_dir / strategy_name
    config = json.loads((strategy_dir / "config.json").read_text(encoding="utf-8"))
    assert config == {
        "symbols": symbols,
        "entry_tf": "M15",
        "indicators": [{"type": "SUPPORT_ZONE", "columns": ["support_low_H4", "support_high_H4"]}],
    }
    manifest = json.loads((webview_dir / "strategies.json").read_text(encoding="utf-8"))
    assert manifest == [{
        "name": "strategies/support_resistance",
        "env": {"development": {
            "df": [
                {"name": "EURUSD", "path": "strategies/support_resistance/EURUSD_df.csv"},
                {"name": "GBPUSD", "path": "strategies/support_resistance/GBPUSD_df.csv"},
            ],
            "config": "strategies/support_resistance/config.json",
            "result": "strategies/support_resistance/result.json",
        }, "production": {}},
    }]
    assert (strategy_dir / "EURUSD_df.csv").is_file()
    assert (strategy_dir / "GBPUSD_df.csv").is_file()
    payload = json.loads((strategy_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["EURUSD"]["name"] == strategy_name
    assert payload["EURUSD"]["report"]["profit_factor"] == "Infinity"


def test_webview_strategy_slug_validation():
    with pytest.raises(ValueError, match="duplicate"):
        _webview_strategies([("Mean Reversion", lambda: None), ("mean_reversion", lambda: None)])
    with pytest.raises(ValueError, match="non-empty"):
        _webview_strategies([("---", lambda: None)])


def test_session_indicator_configs_use_timeframe_suffixed_columns(tmp_path):
    indicators = [
        {"indicator": indicator, "timeframe": "H4"}
        for indicator in (
            "LONDON_HIGH", "LONDON_LOW", "NEWYORK_HIGH", "NEWYORK_LOW", "ASIAN_HIGH", "ASIAN_LOW",
        )
    ]
    webview_dir = tmp_path / "strategies"
    webview_dir.mkdir()
    write_webview_resources(
        webview_dir, ["EURUSD"], ("sessions", lambda _df, _index: None),
        {"EURUSD": [{"name": "sessions", "report": report()}]},
        {"EURUSD": frame()}, "M15", indicators,
    )
    config = json.loads((webview_dir / "sessions" / "config.json").read_text(encoding="utf-8"))
    assert config["indicators"] == [
        {"type": indicator, "columns": [f"{stem}_H4"]}
        for indicator, stem in (
            ("LONDON_HIGH", "london_high"), ("LONDON_LOW", "london_low"),
            ("NEWYORK_HIGH", "newyork_high"), ("NEWYORK_LOW", "newyork_low"),
            ("ASIAN_HIGH", "asian_high"), ("ASIAN_LOW", "asian_low"),
        )
    ]
