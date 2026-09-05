---
name: pinbar-trading-strategy
description: Analyze and trade price rejection with trend and support/resistance context. Use for Pinbar, engulfing, and rejection-based forex entries and trade management.
---

# Pinbar Trading Strategy

Use this strategy for price-rejection entries when it is the strategy selected for the cycle. A pin bar or engulfing pattern is evidence of rejection, not a trade signal in isolation. A multi-candle sequence that rejects higher or lower prices is equally valid evidence when the retrieved OHLC data supports that interpretation. Do not use Moving Average strategy rules in this strategy's final decision.

## Market data analysis

Retrieve the configured symbol with exactly these strategy inputs. Do not read the full technical-indicators skill during a live cycle:

- `EMA_TREND` on `H1`, with `fast_span: 9` and `slow_span: 50`, for higher-timeframe trend direction.
- `SUPPORT_ZONE` and `RESISTANCE_ZONE` on `H1`, each with `sr_hours: 24`, for the relevant price areas.
- `CDLENGULFING`, `CDLHAMMER`, `CDLINVERTEDHAMMER`, and `CDLSHOOTINGSTAR` on `M15`, for rejection confirmation.

Do not add ATR, M5, or other indicators/timeframes to this strategy. Establish the H1 trend and relevant H1 support/resistance from returned values. Look for lower-price rejection at support during an uptrend, or higher-price rejection at resistance during a downtrend. A bullish rejection supports a buy; a bearish rejection supports a sell. Do not trade a rejection that is counter to the H1 trend, is not at the relevant H1 support/resistance area, or is not supported by returned M15 price action.

Use the latest completed M15 candle for an entry or management decision. If no completed M15 candle is available, report no signal and wait for one.

If the retrieval fails, returns no candles, or does not return the required H1/M15 strategy columns, stop analysis. Do not name planned indicators or timeframes as used, do not describe a trend or setup, and do not place, modify, or close a trade from that missing data.

## Entry and exit rules

- For a buy, place the stop loss below the low of the bullish rejection candle or the low of its rejection structure.
- For a sell, place the stop loss above the high of the bearish rejection candle or the high of its rejection structure.
- Set take profit from the entry and stop distance at a minimum 1:2 risk/reward ratio. Do not place a trade when the retrieved data cannot support a valid stop and target.
- State the trend, support/resistance level, and rejection evidence for every signal. For no signal, name the missing or failed condition and the specific price action required before reconsidering.
- For a failed retrieval, report `Indicators: N/A — candle retrieval failed` and `Timeframes: N/A — no candle data returned`; the signal reason must say that the H1/M15 Pinbar conditions could not be evaluated and that a successful H1/M15 retrieval is required. Do not cite EMA, zone, pattern, ATR, or price values that were not returned.

## Continuous trade management

Before placing, modifying, or closing a trade, retrieve fresh price data and verify live orders with `get_open_trades`. Manage open trades only from current market evidence: hold, trail the stop with `modify_trade`, or close with `close_trade`/`close_all_trades`. Never claim an order action succeeded unless its tool result confirms it.
