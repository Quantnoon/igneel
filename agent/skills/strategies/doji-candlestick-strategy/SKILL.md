---
name: doji-candlestick-strategy
description: Analyze Doji candlestick setups in price-action context, using rejection patterns at support, resistance, or a 50-period moving-average value area. Do not use a Doji as a standalone reversal signal.
---

# Doji Candlestick Strategy

## Purpose

Use this strategy to analyze Doji-family price-action setups. A Doji represents
temporary indecision: it is not, by itself, evidence that an established trend
will reverse. Evaluate the candle's rejection and its market location together.

## Required evidence

Retrieve raw OHLC candles for every timeframe used in the analysis. Request
only the following technical evidence when applicable:

- `CDLDOJI`, `CDLDRAGONFLYDOJI`, `CDLGRAVESTONEDOJI`, `CDLHAMMER`, and
  `CDLSHOOTINGSTAR` for the relevant candle patterns;
- `SMA` with `{"timeperiod": 50}` only when evaluating a moving-average
  value area.

Use support, resistance, swing points, and trend context derived from the
retrieved OHLC data. Do not add momentum, volatility, or volume indicators.

## Pattern meaning

- A Doji has an open and close at, or materially near, the same level. Treat
  small-body variations according to their rejection meaning rather than
  rejecting them solely because they are not visually exact.
- A Dragonfly Doji, or hammer variation, has lower-price rejection. It is
  bullish evidence only in an appropriate location.
- A Gravestone Doji, or shooting-star variation, has higher-price rejection.
  It is bearish evidence only in an appropriate location.
- A Long-legged Doji has substantial movement in both directions and signals
  heightened indecision. Establish it from OHLC geometry; no numeric wick or
  body threshold is defined by this strategy.

If OHLC data and the applicable pattern output do not support the claimed
pattern, report insufficient evidence. Do not invent candle-ratio thresholds.

## Bullish setup

Consider a bullish setup only when a Dragonfly Doji or hammer variation shows
rejection of lower prices at one of these locations:

- a support area; or
- an uptrend's 50-period SMA value area, where price has pulled back to the
  moving average.

The entry trigger is confirmation on the following candle. The price-action
invalidation is a move below the rejection candle or relevant swing low. A
nearby swing high or resistance area is the initial objective; trend-following
management may instead follow the continuing market structure.

Do not call a Dragonfly Doji bullish when it appears without support or
uptrend/value-area context.

## Bearish setup

Consider a bearish setup only when a Gravestone Doji or shooting-star
variation shows rejection of higher prices at one of these locations:

- a resistance area; or
- a downtrend's 50-period SMA value area, where price has pulled back to the
  moving average.

The entry trigger is confirmation on the following candle. The price-action
invalidation is a move above the rejection candle or relevant swing high. A
nearby swing low or support area is the initial objective; trend-following
management may instead follow the continuing market structure.

Do not call a Gravestone Doji bearish when it appears without resistance or
downtrend/value-area context.

## Long-legged Doji range

Do not trade a Long-legged Doji directly on the timeframe where its range
makes the invalidation impractically broad. Instead, use its high and low as
reference resistance and support on a lower timeframe.

At either boundary, require a separate, supported rejection or breakout
confirmation before forming a directional view. Repeated tests of a boundary
over a short period can support a breakout scenario, but a repeated test alone
is not an entry signal.

## Analysis requirements

Report the pattern detected, its timeframe, the supporting market location,
the confirmation still required or observed, the relevant invalidation level,
and the nearest price-action objective. When the pattern, location, or
confirmation is missing or contradictory, return a neutral or mixed assessment
and state the exact condition that failed.

Never treat a Doji in isolation as a reversal signal, fabricate levels or
candles, prescribe position size, or make broker/execution calls.
