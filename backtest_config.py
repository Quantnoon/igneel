from backtest_strategies import sr_entry, sr_exit, session_breakout_entry, session_breakout_exit

_indicators = [
    #     {
    #     "indicator": "SUPPLY_ZONE",
    #     "timeframe": "H1",
    #     "params": {
    #         "sd_lookback_hours": 5,
    #     }
    # },
    # {
    #     "indicator": "DEMAND_ZONE",
    #     "timeframe": "H1",
    #     "params": {
    #         "sd_lookback_hours": 5,
    #     }
    # },
    {
        "indicator": "RESISTANCE_ZONE",
        "timeframe": "H4",
        "params": {
            "sr_lookback_hours": 5,
        }
    },
    {
        "indicator": "SUPPORT_ZONE",
        "timeframe": "H4",
        "params": {
            "sr_lookback_hours": 5,
        }
    },
    # {
    # "indicator": "VOLATILITY_REGIME",
    # "timeframe": "H1",
    # "params": {
    #         "regime_lookback": 5
    #     }
    # },
    # {
    #      "indicator": "BULLISH_FVG",
    #      "timeframe": "H1",
    # },
    # {
    #      "indicator": "BEARISH_FVG",
    #      "timeframe": "H1",
    # },
    # {"indicator": "BBANDS", "timeframe": "H1"},
    # {"indicator": "EMA", "timeframe": "H1", "params": {"timeperiod": 14}, "outputs": ["ema_14"]},
    # {"indicator": "EMA", "timeframe": "H1", "params": {"timeperiod": 50}, "outputs": ["ema_50"]},
    # {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 12}, "outputs": ["sma_12"]},
    # {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 50}, "outputs": ["sma_50"]},
    # ─────────────────────────────────────────────
    # CANDLESTICK PATTERNS
    # ─────────────────────────────────────────────,
]

strategies = [
    # {
    #     "symbols": ["EURUSDm", "BTCUSDm", "GBPUSDm", "USDJPYm", "USDCADm", "AUDUSDm"],
    #     "name": "support_resistance",
    #     "indicators": _indicators,
    #     "timeframes": ["H4", "M15"],
    #     "date_range": "4M",
    #     "strategy": ("support_resistance", sr_entry, sr_exit),
    #     "config": {
    #         "default_config": {
    #             "sl_type": "custom",
    #             "atr_multiplier": 1.5,
    #             "rrr": 3,
    #             "entry_tf": "M15",
    #             "slippage": 2.5
    #         },
    #         "risk_config": {
    #             "starting_balance":      100,
    #             "currency":              "USD",   # or "NGN"
    #             "ngn_conversion_rate":   1450,
    #             "lot_size":              0.01,
    #             "allow_trading_session": [],  # ["asian", "newyork", "london_newyork_overlap", "london"] = all sessions,
    #             "daily_dd": 0.05, # in percentage
    #             "maximum_dd": 0.7, # in percentage
    #             "trading_days": [], # [] = all trading days
    #         }
    #     }
    # },
    {
        "symbols": ["EURUSDc", "BTCUSDc", "GBPUSDc", "USDJPYc", "USDCADc", "AUDUSDc"],
        "name": "sessions_breakout",
        "indicators": [
            # {"indicator": "EMA", "timeframe": "H4", "params": {"timeperiod": 50}, "outputs": ["ema_50"]},
            # {"indicator": "CDLENGULFING", "timeframe": "M15"},
            # {"indicator": "CDLHAMMER", "timeframe": "M15"},
            # {"indicator": "CDLINVERTEDHAMMER", "timeframe": "M15"},
            # {"indicator": "CDLMORNINGSTAR", "timeframe": "M15"},
            # {"indicator": "CDLEVENINGSTAR", "timeframe": "M15"},
            {"indicator": "LONDON_HIGH", "timeframe": "M15"},
            {"indicator": "LONDON_LOW", "timeframe": "M15"},
            {"indicator": "NEWYORK_HIGH", "timeframe": "M15"},
            {"indicator": "NEWYORK_LOW", "timeframe": "M15"},
            {"indicator": "ASIAN_HIGH", "timeframe": "M15"},
            {"indicator": "ASIAN_LOW", "timeframe": "M15"},
        ],
        "timeframes": ["M15"],
        "date_range": "1M",
        "strategy": ("sessions_breakout", session_breakout_entry, session_breakout_exit),
        "config": {
            "default_config": {
                "sl_type": "custom",
                "atr_multiplier": 1.5,
                "rrr": 3,
                "entry_tf": "M15",
                "slippage": 2.5
            },
            "risk_config": {
                "starting_balance":      100,
                "currency":              "USD",   # or "NGN"
                "ngn_conversion_rate":   1450,
                "lot_size":              0.01,
                "allow_trading_session": [],  # ["asian", "newyork", "london_newyork_overlap", "london"] = all sessions,
                "daily_dd": 0.05, # in percentage
                "maximum_dd": 0.7, # in percentage
                "trading_days": [], # [] = all trading days
            }
        }
    }
]