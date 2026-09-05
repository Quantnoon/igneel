---
name: simple-moving-average
description: Trade the configured symbol from completed H1 closes relative to SMA(20), with ATR-based 1:3 risk and trailing-stop management.
---

# Simple Moving Average

Use this strategy only when `strategy=simple-moving-average` is selected for the cycle. It is the sole source of truth for analysis, entry, exit, and management decisions.

## Market data

Retrieve at least `3D` of the configured symbol using only `H1`. If the configured range is shorter, use `date_range: "3D"`. Call `get_compact_price_data` with this exact indicator schema:

```python
indicators = [
    {"indicator": "SMA", "timeframe": "H1", "params": {"timeperiod": 20}, "outputs": ["sma_20"]},
    {"indicator": "ATR", "timeframe": "H1", "params": {"timeperiod": 14}, "outputs": ["atr_14"]},
]
```

Use the latest completed H1 candle and its returned close, `sma_20`, and `atr_14` values. Also retain the returned `symbol_info` fields `pip_size`, `pip_value`, `tick_size`, and `tick_value`. Do not use an in-progress candle. If retrieval fails, no completed H1 candle exists, or any required candle, indicator, or symbol-info value is missing, non-finite, or non-positive where positivity is required, return `Decision: no signal` and do not place, modify, or close a trade from unavailable data.

## Entry and initial risk

Permit at most one open position owned by this strategy. When one exists, do not place another position; evaluate only its exit and trailing rules. A fresh crossover is not required after the prior position has closed.

- If the completed H1 close is above SMA(20), buy.
- If the completed H1 close is below SMA(20), sell.
- If the close equals SMA(20), return no signal.

Treat H1 ATR(14) as a pip count. The requested unit of risk (`1R`) in price terms is `atr_14 * pip_size`. Call `place_trade` with `risk_pips=atr_14` and the exact returned `pip_size` and `tick_size`; the tool reads the live executable ask or bid, accounts for the live spread and broker `trade_stops_level`, expands 1R when the requested distance is too small, calculates the absolute stop and target, and aligns them to the broker tick size. For a buy, the stop is one effective risk unit below entry and the target is three effective risk units above entry. For a sell, the stop is one effective risk unit above entry and the target is three effective risk units below entry. This preserves a fixed 1:3 risk/reward ratio before broker tick-size alignment. Report any broker-distance adjustment returned by the tool. Do not place the trade unless the tool confirms that the proposed stop and target are valid and the broker accepts the order preflight.

## Exit and trailing stop

Manage only positions owned by this strategy. Evaluate the SMA exit before any trailing adjustment:

- Close a buy when the latest completed H1 close is below SMA(20).
- Close a sell when the latest completed H1 close is above SMA(20).
- Equality does not close a position.

If no SMA exit applies, calculate `2R = atr_14 * pip_size` and activate trailing only after price has moved at least `+1R` from entry in the trade direction. For a buy, the candidate stop is the latest completed H1 close minus `2R`, rounded down to `tick_size`. For a sell, it is the close plus `2R`, rounded up to `tick_size`. Call `modify_trade` only when the candidate tightens the existing stop and remains on the valid side of the current market price. Never loosen or remove a stop, and preserve the existing take profit.

Never claim that placement, modification, or closure succeeded unless the corresponding tool result confirms it.
