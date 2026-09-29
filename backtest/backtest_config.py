from backtest.backtest_strategies import sr_entry, sr_exit, consolidation_entry, consolidation_exit
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

backtest_auth = {
    "login": int(os.environ["EXNESS_LOGIN"]),
    "password": os.environ["EXNESS_PASSWORD"],
    "server": os.environ["EXNESS_SERVER"],
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
}

_indicators = [
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
]

strategies = [
    # {
    #     "symbols": ["EURUSDc", "GBPUSDc", "USDCADc", "USDJPYc"],
    #     "name": "support_resistance",
    #     "indicators": _indicators,
    #     "timeframes": ["H4", "M15"],
    #     "date_range": "3M",
    #     "strategy": ("support_resistance", sr_entry, sr_exit),
    #     "config": {
    #         "default_config": {
    #             "sl_type": "custom",
    #             "atr_multiplier": 4,
    #             "rrr": 3,
    #             "entry_tf": "M15",
    #             "slippage": 2.5
    #         },
    #         "risk_config": {
    #             "starting_balance":      30,
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
        "symbols": ["EURUSDc", "GBPUSDc", "USDJPYc", "USDCADc", "AUDUSDc"],
        "name": "market_consolidation",
        "indicators": [
            {
                "indicator": "CONSOLIDATION_HOTSPOT",
                "timeframe": "H1"
            },
            {
                "indicator": "COMBINED_TREND",
                "timeframe": "H1"
            }
        ],
        "timeframes": ["H1"],
        "date_range": "8M",
        "strategy": ("consolidation", consolidation_entry, consolidation_exit),
        "config": {
            "default_config": {
                "sl_type": "atr",
                "atr_multiplier": 2.5,
                "rrr": 3,
                "entry_tf": "H1",
                "slippage": 2.5
            },
            "risk_config": {
                "starting_balance":      100,
                "currency":              "USD",   # or "NGN"
                "ngn_conversion_rate":   1450,
                "lot_size":              0.02,
                "allow_trading_session": [],  # ["asian", "newyork", "london_newyork_overlap", "london"] = all sessions,
                "daily_dd": 0.05, # in percentage
                "maximum_dd": 0.7, # in percentage
                "trading_days": [], # [] = all trading days
            }
        }
    }
]
