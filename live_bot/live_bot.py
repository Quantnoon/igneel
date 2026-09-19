import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from connection import connect
from collection import PriceDataCollection
from order import place_order, close_order, open_orders, atr_step_trailing
from live_bot.account import Account
from live_bot.monitor import can_trade, quantnoon_signal_provider
import time
from database import Database
from live_bot.live_config import active_config
import MetaTrader5 as mt5

result = connect(active_config["auth"])

account = Account()

_db = Database()

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

while True:
    price_data = PriceDataCollection(
        symbols=symbols,
        timeframes=timeframes,
        date_range=date_range,
        indicators=indicators
    )
    print(f"Daily drawdown at: {account.get_account_info()["today_drawdown"]}")
    print(f"Maximum drawdown at: {account.get_account_info()["maximum_drawdown"]}")
    for signal in signals:
        print(f"------ Passing through {signal["name"]} signal --------")
        for symbol in signal["allowed_symbols"]:
            df = price_data.get_price_data(symbol)
            trade_signal = signal["signal"]
            pos, sl = trade_signal(df, len(df) - 1)
            tp = None
            open_price = df[f"close_{entry_tf}"].iloc[-1]
            status = can_trade({
                "symbol": symbol,
                "trading_sessions": signal["trading_sessions"],
                "daily_dd": daily_dd,
                "maximum_dd": max_dd,
                "allow_many_trades": signal["allow_many_trades"],
                "is_weekend_trading": signal["is_weekend_trading"]
            })
            if signal["sl_type"] == "atr":
                info = mt5.symbol_info(symbol)
                atr = df[f"atr_{signal["entry_tf"]}"].values[-1]
                entry_price = df[f"close_{signal["entry_tf"]}"].values[-1]
                sl = entry_price - (atr * signal["atr_multiplier"]) if pos == "buy" else entry_price + (atr * signal["atr_multiplier"])
                risk = abs(entry_price - sl)
                tp = entry_price + (risk * signal["rrr"]) if pos == "buy" else entry_price - (risk * signal["rrr"])
                if info is not None:
                    sl = round(sl, info.digits)
                    tp = round(tp, info.digits)

            quantnoon_signal_provider(
                signal={
                    "sl": sl,
                    "tp": tp,
                    "pos": pos,
                    "open_price": open_price
                },
                symbol=symbol,
                identifier="support_resistance",
                signal_name="Ranger",
                df=df,
                trade_date=df["time"].iloc[-1],
                entry_tf=signal["entry_tf"],
                exit_signal=signal.get("custom_sl", None)
            )
            if pos is None:
                print(f"STATUS: {status["reason"]}")
            if pos is None and status["status"] == "can_trade":
                print(f"{symbol}: has no signal")
            if status["status"] == "can_trade" and pos is not None:
                order_result = place_order(
                    symbol=symbol,
                    order_type=pos,
                    volume=signal["lot_size"],
                    magic=signal["magic"],
                    price=open_price,
                    sl=sl,
                    tp=tp
                )
                if order_result["success"]:
                    order = {
                        "id": order_result["data"]["result"]["order"],
                        "pos": pos
                    }
                    _db.create_table(signal["name"], order)
                    _db.add_to_table(signal["name"], order)

                    print(f"{symbol}: {pos} order placed")
            else:
                orders = open_orders(symbol=symbol)["data"]
                for order in orders:
                    row = _db.get_row(signal["name"], "id", order["ticket"])["data"]
                    if row is not None and row.get("id"):
                        result = {
                            "reason": "trailing sl not enabled"
                        }
                        if signal["use_trailing_sl"]:
                            result = atr_step_trailing(order, df, row["pos"], entry_tf)
                        print(f"{symbol}: Tracking order {row.get("id")} | trailing SL status: {result["reason"]}")
                        if signal["sl_type"] == "custom":
                            exit_signal = signal["custom_sl"]

                            if exit_signal(df, len(df) - 1, row.get("pos")):
                                close_order(row.get("id"))
    time.sleep(active_config["sleep_time"])
