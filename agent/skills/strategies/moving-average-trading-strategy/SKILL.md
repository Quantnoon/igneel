---
name: moving-average-trading-strategy
description: Trade trending forex markets from 50/200 SMA value areas with price rejection and lower-timeframe structure confirmation.
---

# Moving Average Trading Strategy

Use this strategy only when it is selected for the cycle. Do not combine its rules with the Pinbar strategy's support/resistance or minimum-risk-reward rules.

## Market data analysis

Retrieve at least `10D` of the configured symbol's data; if the configured range is shorter, call `get_price_data` with `date_range: "10D"`. Use exactly these indicators:

- `SMA` on `H1` with `timeperiod: 50` and `outputs: ["sma_50"]`.
- `SMA` on `H1` with `timeperiod: 200` and `outputs: ["sma_200"]`.
- `ATR` on `M15` with `timeperiod: 14`.
- `CDLENGULFING`, `CDLHAMMER`, `CDLINVERTEDHAMMER`, and `CDLSHOOTINGSTAR` on `M15`.

Call `get_compact_price_data` with this exact indicator schema. Use `indicator`, not `name`; put each period inside `params`, not at the top level:

```python
indicators = [
    {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 50}, "outputs": ["sma_50"]},
    {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 200}, "outputs": ["sma_200"]},
    {"indicator": "ATR", "timeframe": "M15", "params": {"timeperiod": 14}},
    {"indicator": "CDLENGULFING", "timeframe": "M15"},
    {"indicator": "CDLHAMMER", "timeframe": "M15"},
    {"indicator": "CDLINVERTEDHAMMER", "timeframe": "M15"},
    {"indicator": "CDLSHOOTINGSTAR", "timeframe": "M15"},
]
```

The H1 close above SMA(200) permits buy analysis only; below SMA(200) permits sell analysis only. Do not trade a range market, a market without a sustained H1 direction, or data that does not return the required H1/M15 columns.

Use the latest completed M15 candle for an entry or management decision. If no completed M15 candle is available, report no signal and wait for one.

Treat moving averages as value areas, not exact lines. In a healthy trend, evaluate SMA(50) as the value area; in a weak/deeper-pullback trend, evaluate SMA(200). Validate an area only after at least two separate tests: after a test, price must move away and break the intervening swing in the trend direction before a later return can count as the next test.

## Entry and exit rules

For a buy, require a valid H1 uptrend, a two-test H1 SMA(50) or SMA(200) value area, bullish M15 rejection at that area, and an M15 close above the most recent pullback swing high. For a sell, require the mirrored H1 downtrend, value area, bearish M15 rejection, and an M15 close below the most recent pullback swing low. Enter only after that completed M15 confirmation.

Set the stop loss one M15 ATR(14) beyond the relevant M15 rejection/structure extreme: below it for buys and above it for sells. Set take profit at the relevant major H1 swing point in the trade direction. A tighter M15 structure stop is allowed only when it remains beyond the invalidation point and improves the resulting reward-to-risk. Do not set a target, risk/reward threshold, or trailing-stop rule from another strategy.

For no signal, identify this strategy by name and state which required condition failed: H1 direction, non-ranging market, validated value area, M15 rejection, M15 structure break, valid ATR stop, or major-swing target. State the exact price action required before reconsidering.

If `get_price_data` returns `success: false`, quote its returned error stage and message. Do not describe it as a candle-retrieval failure unless the returned error says the candle data is unavailable.

## Continuous trade management

Manage only trades opened by this strategy. Hold a position while its H1 trend, M15 structure, stop, and major-swing target remain valid. Close it when returned H1/M15 data invalidates the entry direction or when its stop/target outcome is confirmed. This strategy does not use a trailing stop. Never claim an action succeeded unless the order tool result confirms it.
