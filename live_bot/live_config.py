from live_bot.signals import sd_entry, sd_exit, sr_entry, sr_exit, get_test_signal, get_test_exit_signal, consolidation_entry
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    load_dotenv(_exe_dir / ".env", interpolate=False)
    # In a checkout, dist/ is nested under live_bot/, while .env stays at the
    # project root and is deliberately not bundled into the executable.
    load_dotenv(_exe_dir.parent.parent / ".env", interpolate=False)
else:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", interpolate=False)

_deployments = {
    "sd_bot": {
        "name": "sd_bot",
        "auth": {
            "login": int(os.environ["LOGIN"]),
            "password": os.environ["PASSWORD"],
            "server": os.environ["SERVER"],
            "path": os.environ["TERMINAL_PATH"],
        },
        "sleep_time": 30,
        "symbols": ["Volatility 25 Index", "Volatility 10 Index"],
        "date_range": "2D",
        "timeframes": ["M15"],
        "daily_dd": 0.2,
        "maximum_dd": 0.8,
        "signals": [
            {
                "name": "xauusd_supply_demand",
                "lot_size": 3.0,
                "magic": 123456,
                "sl_type": "custom",
                "atr_multiplier": 0.5,
                "rrr": 3,
                "custom_sl": get_test_exit_signal,
                "signal": get_test_signal,
                "allowed_symbols": ["Volatility 25 Index", "Volatility 10 Index"],
                "trading_sessions": [],
                "allow_many_trades": False,
                "entry_tf": "M15",
                "is_weekend_trading": True,
                "use_trailing_sl": True,
            }
        ],
        "entry_tf": "M15",
        "indicators": [
            # {
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
            # {
            #     "indicator": "VOLATILITY_REGIME",
            #     "timeframe": "M5",
            #     "params": {
            #         "regime_lookback": 5
            #     }
            # },
            {
                "indicator": "ATR",
                "timeframe": "M15",
            }
        ]
    },
    "sr_bot": {
        "name": "support_resistance",
        "auth": {
            "login": int(os.environ["LOGIN"]),
            "password": os.environ["PASSWORD"],
            "server": os.environ["SERVER"],
            "path": os.environ["TERMINAL_PATH"],
        },
        "sleep_time": 30,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
        "date_range": "1W",
        "timeframes": ["H4", "M15"],
        "daily_dd": 0.2,
        "maximum_dd": 0.65,
        "signals": [
            {
                "name": "support_resistance",
                "lot_size": 0.01,
                "magic": 123456,
                "sl_type": "custom",
                "custom_sl": sr_exit,
                "signal": sr_entry,
                "allowed_symbols": ["EURUSD", "GBPUSD", "USDJPY"],
                "trading_sessions": [],
                "allow_many_trades": False,
                "use_trailing_sl": False,
                "entry_tf": "M15",
                "is_weekend_trading": False,
            }
        ],
        "entry_tf": "M15",
        "indicators": [
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
            {
            "indicator": "VOLATILITY_REGIME",
            "timeframe": "M15",
            "params": {
                    "regime_lookback": 5
                }
            },
            {
                "indicator": "ATR",
                "timeframe": "M15",
            }
        ]
    },
    "consolidation_bot": {
        "name": "consolidation_bot",
        "auth": {
            "login": int(os.environ["LOGIN"]),
            "password": os.environ["PASSWORD"],
            "server": os.environ["SERVER"],
            "path": os.environ["TERMINAL_PATH"],
        },
        "sleep_time": 60 * 30,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"],
        "date_range": "3D",
        "timeframes": ["H1"],
        "daily_dd": 0.15,
        "maximum_dd": 0.65,
        "signals": [
            {
                "name": "consolidation_bot",
                "lot_size": 0.02,
                "magic": 123456,
                "sl_type": "atr",
                "atr_multiplier": 2.0,
                "rrr": 2.5,
                "signal": consolidation_entry,
                "allowed_symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"],
                "trading_sessions": [],
                "allow_many_trades": False,
                "use_trailing_sl": True,
                "entry_tf": "H1",
                "is_weekend_trading": False,
            }
        ],
        "entry_tf": "H1",
        "indicators": [
            {
                "indicator": "CONSOLIDATION_HOTSPOT",
                "timeframe": "H1"
            },
            {
                "indicator": "COMBINED_TREND",
                "timeframe": "H1"
            },
            {
                "indicator": "ATR",
                "timeframe": "H1"
            }
        ]
    }
}

active_config = _deployments["consolidation_bot"]
