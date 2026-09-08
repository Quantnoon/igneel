<p align="center">
  <img src="docs/assets/igneel-logo.png" alt="Igneel, a red fire dragon" width="220">
</p>

# Igneel

Igneel is an algorithmic trading engine for market analysis, order execution, trade management, live trading, backtesting, and strategy visualization.

## Main entry points

- `agent.py` - autonomous AI agent that analyzes the market, places orders, and manages open trades.
- `live_bot.py` - live-trading pipeline configured through `live_config.py`.
- `backtest.py` - strategy backtesting system configured through `backtest_config.py`.
- `webview/` - web interface for viewing market charts, strategies, and backtest results.

## Risk warning

Live trading carries significant financial risk. Test strategies and configuration with a demo account before using Igneel with real funds.
