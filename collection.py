from price_data.price_data import MT5PriceData
import MetaTrader5 as mt5


class PriceDataCollection:
    def __init__(self, symbols, timeframes, date_range, indicators=[]):
        self._price_data = MT5PriceData(mt5)
        self._price_data.set_price(symbols, date_range, timeframes)
        self._price_data.set_indicator(indicators)

    def get_price_data(self, symbol):
        return self._price_data.get_merged_price(symbol)

    def get_symbol_info(self, symbol):
        return self._price_data.get_symbol_info(symbol)



