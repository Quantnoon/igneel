<p align="center">
  <img src="docs/assets/Igneel.webp" alt="Igneel, a red fire dragon" width="220">
</p>

# Igneel

Igneel is an algorithmic trading engine for market analysis, order execution, trade management, live trading, backtesting, and strategy visualization.

## Project folders

- `agent/` - AI-powered trading agent for market analysis, trade decisions, and execution.
- `backtest/` - Strategy backtesting engine for evaluating trading strategies against historical data.
- `live_bot/` - Bot for automated live-market trading.
- `webview/` - Project frontend for viewing trading and backtesting data.

## Main entry points

- `python -m agent.agent` (preferred) or `python agent/agent.py` - autonomous AI agent that analyzes the market, places orders, and manages open trades. Its skills, logs, and large tool results are stored under `agent/`.
- `python -m live_bot.live_bot` (preferred) or `python live_bot/live_bot.py` - live-trading pipeline configured through `live_bot/live_config.py`.
- `python -m backtest.backtest` (preferred) or `python backtest/backtest.py` - strategy backtesting system configured through `backtest/backtest_config.py`.
- `webview/` - web interface for viewing market charts, strategies, and backtest results.

The DeepAgents filesystem backend is rooted at `agent/`. Agent prompts therefore
use virtual paths such as `/skills/...` and `/large_tool_results/...`; these map
to `agent/skills/...` and `agent/large_tool_results/...` at runtime.

## Risk warning

Live trading carries significant financial risk. Test strategies and configuration with a demo account before using Igneel with real funds.
