from connection import connect
from collection import PriceDataCollection
from order import place_order, close_order, open_orders, atr_step_trailing
from account import Account
from monitor import can_trade
import time
from database import Database
from live_config import active_config

result = connect(active_config["auth"])

account = Account()

_db = Database()

account.set_account_info()
print(account.get_account_info())

symbols = active_config["symbols"]
date_range = active_config["date_range"]
timeframes = active_config["timeframes"]
indicators = active_config["indicators"]
entry_tf = active_config["entry_tf"]

signals = active_config["signals"]

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
            pos, sl = trade_signal(df, len(df) - 1)
            status = can_trade({
                "symbol": symbol,
                "trading_sessions": signal["trading_sessions"],
                "daily_dd": 0.1,
                "maximum_dd": 0.65,
                "allow_many_trades": signal["allow_many_trades"]
            })
            if pos is None and status["status"] == "can_trade":
                print(f"{signal["name"]} signal: {symbol} has no signal")
            #print(status)
            if status["status"] == "can_trade" and pos is not None:
                if signal["sl_type"] == "custom":
                    order_result = place_order(
                        symbol=symbol,
                        order_type=pos,
                        volume=signal["lot_size"],
                        magic=signal["magic"],
                        price=df[f"close_{entry_tf}"].iloc[-1],
                        sl=sl,
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
                        result = {
                            "reason": "trailing sl not enabled"
                        }
                        if active_config["use_trailing_sl"]:
                            result = atr_step_trailing(order, df, row["pos"], entry_tf)
                        print(f"{signal["name"]} signal: Tracking order {row.get("id")} for {symbol} | signal trailing SL status: {result["reason"]}")
                        if signal["sl_type"] == "custom":
                            exit_signal = signal["custom_sl"]

                            if exit_signal(df, len(df) - 1, row.get("pos")):
                                close_order(row.get("id"))
    time.sleep(active_config["sleep_time"])
