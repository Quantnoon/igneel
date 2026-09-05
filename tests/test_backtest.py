import importlib
import sys


def test_importing_backtest_does_not_import_runtime_modules():
    for name in ("backtest", "collection", "connection", "live_config", "MetaTrader5"):
        sys.modules.pop(name, None)

    module = importlib.import_module("backtest")

    assert hasattr(module, "main")
    for name in ("collection", "connection", "live_config", "MetaTrader5"):
        assert name not in sys.modules


def test_chart_indicators_groups_by_type_with_first_appearance_order():
    backtest = importlib.import_module("backtest")

    entries = [
        {"indicator": "BBANDS", "timeframe": "H1"},
        {"indicator": "EMA", "timeframe": "H1", "params": {"timeperiod": 12}, "outputs": ["ema_12"]},
        {"indicator": "EMA", "timeframe": "H1", "params": {"timeperiod": 50}, "outputs": ["ema_50"]},
        {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 12}, "outputs": ["sma_12"]},
        {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 50}, "outputs": ["sma_50"]},
    ]

    assert backtest._chart_indicators(entries) == [
        {"type": "BBANDS", "columns": ["bbands_upper_H1", "bbands_middle_H1", "bbands_lower_H1"]},
        {"type": "EMA", "columns": ["ema_12_H1", "ema_50_H1"]},
        {"type": "SMA", "columns": ["sma_12_H1", "sma_50_H1"]},
    ]
    assert backtest._chart_indicators([]) == []


def test_chart_indicators_uses_registry_default_outputs_when_missing():
    backtest = importlib.import_module("backtest")

    entries = [
        {"indicator": "SMA", "timeframe": "M15"},
        {"indicator": "EMA", "timeframe": "M15", "params": {"timeperiod": 21}},
    ]

    assert backtest._chart_indicators(entries) == [
        {"type": "SMA", "columns": ["sma_M15"]},
        {"type": "EMA", "columns": ["ema_M15"]},
    ]


def test_chart_indicators_resolves_zone_bounds():
    backtest = importlib.import_module("backtest")

    entries = [
        {"indicator": "SUPPLY_ZONE", "timeframe": "H1"},
        {"indicator": "DEMAND_ZONE", "timeframe": "H1"},
        {"indicator": "SUPPORT_ZONE", "timeframe": "H1"},
        {"indicator": "RESISTANCE_ZONE", "timeframe": "H1"},
        {"indicator": "BULLISH_FVG", "timeframe": "H1"},
        {"indicator": "BEARISH_FVG", "timeframe": "H1"},
    ]

    assert backtest._chart_indicators(entries) == [
        {"type": "SUPPLY_ZONE", "columns": ["supply_low_H1", "supply_high_H1"]},
        {"type": "DEMAND_ZONE", "columns": ["demand_low_H1", "demand_high_H1"]},
        {"type": "SUPPORT_ZONE", "columns": ["support_low_H1", "support_high_H1"]},
        {"type": "RESISTANCE_ZONE", "columns": ["resistance_low_H1", "resistance_high_H1"]},
        {"type": "BULLISH_FVG", "columns": ["bullish_fvg_low_H1", "bullish_fvg_high_H1"]},
        {"type": "BEARISH_FVG", "columns": ["bearish_fvg_low_H1", "bearish_fvg_high_H1"]},
    ]


def test_chart_indicators_resolves_candlestick_pattern_outputs():
    backtest = importlib.import_module("backtest")

    entries = [
        {"indicator": "CDLHAMMER", "timeframe": "H1"},
        {"indicator": "CDLENGULFING", "timeframe": "H1"},
        {"indicator": "CDLDOJI", "timeframe": "H1"},
    ]

    assert backtest._chart_indicators(entries) == [
        {"type": "CDLHAMMER", "columns": ["cdlhammer_H1"]},
        {"type": "CDLENGULFING", "columns": ["cdlengulfing_H1"]},
        {"type": "CDLDOJI", "columns": ["cdldoji_H1"]},
    ]
