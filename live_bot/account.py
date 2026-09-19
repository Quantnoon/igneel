from database import Database
import MetaTrader5 as mt5
import datetime

class Account:
    _db = None
    def __init__(self):
        self._db = Database()

    def __exit__(self, exc_type, exc, tb):
        self._db.close()

    def set_account_info(self, daily_dd, max_dd):
        account_info_dict = mt5.account_info()._asdict()
        account = {
            "id": 1,
            "starting_balance": account_info_dict["balance"],
            "current_balance": account_info_dict["balance"],
            "sever": account_info_dict["balance"],
            "currency": account_info_dict["currency"],
            "company": account_info_dict["company"],
            "name": account_info_dict["name"],
            "profit": account_info_dict["profit"],
            "equity": account_info_dict["equity"],
            "leverage": account_info_dict["leverage"],
            "assets": account_info_dict["assets"],
            "today_drawdown": account_info_dict["balance"] - (account_info_dict["balance"] * daily_dd),
            "maximum_drawdown":  account_info_dict["balance"] - (account_info_dict["balance"] * max_dd),
            "date": datetime.datetime.now().strftime('%d/%m/%Y')
        }
        if (len([] if self._db.get_rows("account")["data"] is None else self._db.get_rows("account")["data"]) < 1 ):
            result = self._db.create_table("account", account)
            if result:
                result = self._db.add_to_table("account", account)
            return result

    def get_account_info(self):
        return self._db.get_row("account", "id", 1)["data"]

    def update_account(self, new_bal, daily_dd, max_dd):
        account_info_dict = mt5.account_info()._asdict()
        self._db.update_row(
            "account", 
            {
                "id": 1, 
                "current_balance": new_bal, 
                "equity": new_bal,
                "today_drawdown": account_info_dict["balance"] - (account_info_dict["balance"] * daily_dd),
                "date": datetime.datetime.now().strftime('%d/%m/%Y')
            }
        )

    def update_balance(self, new_balance, daily_dd, max_dd):
        account_info_dict = mt5.account_info()._asdict()
        self._db.update_row(
            "account", 
            {
                "id": 1,
                "current_balance": new_balance,
                "equity": new_balance,
                "today_drawdown": account_info_dict["balance"] - (account_info_dict["balance"] * daily_dd),
                "maximum_drawdown":  account_info_dict["balance"] - (account_info_dict["balance"] * max_dd),
            }
        )
