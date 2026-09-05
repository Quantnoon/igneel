---
name: trendline-trading-strategy
description: Trade confirmed trendline bounces and pullback-trendline breaks with H1 context, M15 structure, and price-action confluence.
---

# Trendline Trading Strategy

Use this strategy only when it is selected for the cycle. It is the sole source of truth for this cycle's analysis, entry, exit, and management decisions. Do not combine its rules with Pinbar or Moving Average strategy rules.

## Market data analysis

Retrieve the configured symbol with `H1` and `M15` candles. Use the latest completed `M15` candle for an entry or management decision; if no completed M15 candle is available, report no signal and wait for one. Derive primary and pullback trendlines from returned OHLC data; there is no native trendline indicator. Use the most relevant recent swing points while maximizing valid body and wick touches. Treat every trendline as an area, not an exact price.

Call `get_compact_price_data` using only registry-valid indicator objects:

```python
indicators = [
    {"indicator": "SUPPORT_ZONE", "timeframe": "H1", "params": {"sr_hours": 24}},
    {"indicator": "RESISTANCE_ZONE", "timeframe": "H1", "params": {"sr_hours": 24}},
    {"indicator": "ATR", "timeframe": "M15", "params": {"timeperiod": 14}},
    {"indicator": "CDLENGULFING", "timeframe": "M15"},
    {"indicator": "CDLHAMMER", "timeframe": "M15"},
    {"indicator": "CDLINVERTEDHAMMER", "timeframe": "M15"},
    {"indicator": "CDLSHOOTINGSTAR", "timeframe": "M15"},
]
```

Confirm a trendline only after at least two completed touches. The first two touches establish the area; evaluate entries only on a later interaction. Describe H1 direction from the returned swing structure, and use returned H1 support/resistance zones as confluence when they overlap the trendline area.

## Entry rules

For a trendline bounce, require a confirmed H1 trendline area, price interacting with it, and returned M15 bullish rejection for a buy or bearish rejection for a sell. Require M15 break-of-structure in the trade direction: a buy needs a close above the relevant pullback swing high; a sell needs a close below the relevant pullback swing low.

For a pullback-trendline break, draw the M15 pullback trendline from returned swing points. Enter only after a completed M15 candle closes through that pullback line in the H1 trend direction. Reject a break that occurs too far from the confirmed H1 trendline/value or support/resistance confluence area.

## No-signal reporting

For `Decision: no signal`, state one primary failed condition from returned OHLC or indicator data and the specific price action required before reconsidering. Do not use generic indicator-pattern absence, unspecified later-interaction wording, or a combined list of unverified failures.

Use the first applicable failed condition:

1. Fewer than two completed H1 trendline touches: state the returned touch count and wait for the next completed touch to confirm the area.
2. A confirmed H1 trendline exists but current price is not interacting with its area: state that location and wait for price to return to the area.
3. Price is interacting with the confirmed area but there is no bullish/bearish M15 rejection: state the returned candle evidence and wait for a rejection in the H1 trend direction.
4. Rejection exists but M15 structure has not broken in the trade direction: state the relevant pullback swing and wait for a completed M15 close through it.
5. A pullback-trendline break setup exists but no M15 candle has closed through the pullback line: state that and wait for the required close.
6. Entry conditions exist but the returned ATR invalidation swing or H1 swing target is unavailable: state the unavailable item and do not place a trade.

Examples:

- `H1 trendline has one completed touch; wait for a second confirmed touch before evaluating a later interaction.`
- `Price is at the confirmed H1 trendline area, but the latest completed M15 candle shows no bearish rejection; wait for bearish rejection followed by an M15 close below the pullback swing low.`

## Exit and trade management

Set stop loss one M15 ATR(14) beyond the rejection or structure-invalidating swing: below it for buys and above it for sells. Set take profit at the next relevant H1 swing point in the trade direction. Do not place a trade without a valid returned ATR value, invalidation swing, and target.

Manage only trades opened by this strategy. Hold while its H1 trendline and M15 structure remain valid. Close on a confirmed H1 trendline/structure invalidation or a confirmed stop/target outcome. This strategy does not use a trailing stop. Never claim an order action succeeded unless its tool result confirms it.
