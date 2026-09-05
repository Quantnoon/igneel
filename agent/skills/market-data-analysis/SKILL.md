---
name: market-data-analysis
description: Retrieve MT5 price data and analyze current forex market conditions using supported timeframes and the technical-indicators skill. Use for price, timeframe, trend analysis, evidence-based entries, and trade management.
---

# Market Data Analysis

Use this skill to retrieve and inspect market data. Before any market analysis, trade decision, or order-management decision, read `/skills/strategies/SKILL.md` and the single strategy mapped from the cycle context's `strategy` value. Runtime context supplies no market-analysis assumptions: the configured strategy is the sole source of truth for price-data tool choice, lookback, timeframes, indicators, freshness, report fields, and every trade decision.

## Tool contract

For autonomous cycles, call `get_compact_price_data` with:

- `symbols`: symbols to load. For a single-symbol analysis, use `[symbol]`.
- `symbol`: the requested target symbol; it must be included in `symbols`.
- `timeframes`: one or more of `M1`, `M5`, `M15`, `H1`, `H4`, `D1`, or `W1`.
- `date_range`: a relative lookback in `N[DWMY]`, such as `3D`, `2W`, `5M`, or `1Y`.
- `indicators`: a list using the exact schema and supported identifiers from the technical-indicators skill.

The compact tool returns JSON-safe columns, recent rows, and latest indicator values. Use its `recent_rows` limit to avoid loading unnecessary history. `get_price_data` returns the complete Markdown table and is reserved for an explicit user request for raw prices. The selected strategy skill contains its complete indicator configurations; do not read the full technical-indicators registry during a live cycle.

## Continuous trade-management cycles

When the cycle prompt includes open trades, retrieve fresh market data and use `get_open_trades` to verify live trade state before any strategy-directed order action. The selected strategy skill determines whether to place, modify, hold, or close trades.

## Cycle decision report

After the tool calls for every autonomous cycle, return only this compact format:

```text
MARKET ANALYSIS
Indicators: <indicators used>
Timeframes: <timeframes used>
Market: <what the market is saying>

SIGNAL
Decision: <buy / sell / no signal>
Reason: <for no signal: timeframe + indicators/values or pattern + failed condition + condition to wait for; for a signal: qualifying evidence>
SL / TP / Exit: <chosen levels and exit logic, or N/A>

TRADE MANAGEMENT
Open trades: <count>
Conditions: <current trade conditions>
Action: <holding / trailing SL / closing / placing trade / no action>
```

Do not add other sections. Treat supplied account and open-trade values as factual context, keep them separate from interpretation, and never invent tool outcomes.

For a no-signal report, do not use vague wording such as `clear entry`, `risk structure`, `insufficient setup`, or `conflicting evidence` on its own. State the actual trend, support/resistance or rejection condition that is missing, and what price action is required before reconsidering an entry.
