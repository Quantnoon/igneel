from connection import connect
from collection import PriceDataCollection
from order import place_order, modify_order, close_order, open_orders, atr_step_trailing
from datetime import datetime
from account import Account
from monitor import can_trade
import time
from database import Database
from signals import get_test_signal, exit_test_signal

result = connect({
    "login": 41180154,
    "password": "Money_135795",
    "server": "Deriv-Demo",
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
})

account = Account()

_db = Database()

account.set_account_info()
print(account.get_account_info())

symbols = ["XAUUSD", "GBPUSD"]
date_range = "1W"
timeframes = ["M1"]
indicators = [
    {
        "name": "SMA",
        "indicator": "SMA",
        "timeframe": "M1",
        "params": {
            "timeperiod": 20
        }
    }
]
entry_tf = "M1"

signals = [
    {
        "name": "gold",
        "lot_size": 1.0,
        "magic": 123456,
        "sl_type": "custom",
        "custom_sl": exit_test_signal,
        "signal": get_test_signal,
        "allowed_symbols": ["XAUUSD"],
        "trading_sessions": [],
        "allow_many_trades": False
    },
    {
        "name": "pound",
        "lot_size": 1.0,
        "magic": 123457,
        "sl_type": "custom",
        "custom_sl": exit_test_signal,
        "signal": get_test_signal,
        "allowed_symbols": ["GBPUSD"],
        "trading_sessions": [],
        "allow_many_trades": False
    }
]

while True:
    price_data = PriceDataCollection(
        symbols=symbols,
        timeframes=timeframes,
        date_range=date_range,
        indicators=indicators
    )
    for signal in signals:
        print(f"------ Passing through {signal["name"]} signal --------")
        for symbol in signal["allowed_symbols"]:
            df = price_data.get_price_data(symbol)
            trade_signal = signal["signal"]
            pos = trade_signal(df, len(df) - 1)
            status = can_trade({
                "symbol": symbol,
                "trading_sessions": signal["trading_sessions"],
                "daily_dd": 0.1,
                "maximum_dd": 0.65,
                "allow_many_trades": signal["allow_many_trades"]
            })
            print(status)
            if status["status"] == "can_trade":
                if signal["sl_type"] == "custom":
                    order_result = place_order(
                        symbol=symbol,
                        order_type=pos,
                        volume=signal["lot_size"],
                        magic=signal["magic"],
                        price=df[f"close_{entry_tf}"].iloc[-1],
                    )
                    if order_result["success"]:
                        order = {
                            "id": order_result["data"]["result"]["order"],
                            "pos": pos
                        }
                        _db.create_table(signal["name"], order)
                        _db.add_to_table(signal["name"], order)

                        print(f"{signal["name"]} signal: {pos} order placed")
            else:
                orders = open_orders(symbol=symbol)["data"]
                for order in orders:
                    row = _db.get_row(signal["name"], "id", order["ticket"])["data"]
                    if row is not None and row.get("id"):
                        print(f"{signal["name"]} signal: Tracking order {row.get("id")}")
                        result = atr_step_trailing(order, df, row["pos"], entry_tf)
                        print(f"{signal["name"]} signal trailing SL status: {result["reason"]}")
                        if signal["sl_type"] == "custom":
                            exit_signal = signal["custom_sl"]

                            if exit_signal(df, len(df) - 1, row.get("pos")):
                                close_order(row.get("id"))
    time.sleep(30)
