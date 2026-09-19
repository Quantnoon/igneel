import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from backtest_engine.main import Engine
from backtest.backtest_tools import write_webview_resources
from collection import PriceDataCollection
from connection import connect
from backtest.backtest_config import strategies, backtest_auth

conn = connect(backtest_auth)

if __name__ == "__main__":
    for strategy in strategies:
        symbols = strategy["symbols"]
        entry_tf = strategy["config"]["default_config"]["entry_tf"]
        indicators = strategy["indicators"]
        timeframes = strategy["timeframes"]
        date_range = strategy["date_range"]

        price_data = PriceDataCollection(
            symbols=symbols,
            timeframes=timeframes,
            date_range=date_range,
            indicators=indicators,
        )

        engine = Engine(price_data, symbols)

        engine.set_config(strategy["config"], [strategy["strategy"]])

        result = engine.run_backtest()

        df = {}
        for symbol in symbols:
            df[symbol] = price_data.get_price_data(symbol)

        webview_dir = Path(__file__).resolve().parent.parent / "webview" / "strategies"
        write_webview_resources(webview_dir, symbols, strategy["strategy"], result, df, entry_tf, indicators)
        print(f"WebView resources written to {webview_dir}")
