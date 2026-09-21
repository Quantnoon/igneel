---
name: liquidity-sweep-trading-strategy
description: Analyze liquidity-sweep setups at defined liquidity zones. Require a completed sweep, a closed reaction candle, and an observed confirmation before forming a directional setup.
---

# Liquidity Sweep Trading Strategy

## Purpose

Use this strategy to analyze price moves into liquidity zones, where
stop-loss and pending orders may cluster. A liquidity sweep is a move through
such a level followed by a decisive reaction. It may lead to a reversal or to
continued movement; do not assume a reversal without the required evidence.

Apply the rules below in order. Do not add indicators, thresholds, price
levels, candle-ratio definitions, or execution rules that are not defined by
this strategy.

## Terms

- **Buy-side liquidity** is liquidity above prior highs, where short-position
  stops and breakout buy stops may cluster.
- **Sell-side liquidity** is liquidity below prior lows, where long-position
  stops may cluster.
- **Liquidity sweep** briefly pierces a key level and rejects it, often
  leaving a wick or reversal candle.
- **Liquidity run** pushes beyond the level and continues to build the
  existing trend structure. Sustained momentum through subsequent liquidity
  pools is a genuine break of structure.
- **External Range Liquidity (ERL)** is liquidity beyond the most significant
  swing high or low of a defined trading range.
- **Internal Range Liquidity (IRL)** is liquidity within a trading range,
  including minor highs, lows, and fair value gap areas.
- **AMD** describes accumulation, manipulation, and distribution:
  accumulation develops within a range; manipulation pushes beyond the range
  to sweep ERL; distribution is the decisive move after the ERL sweep.

## 1. Establish Context

1. Review a higher timeframe to determine directional bias and important
   liquidity zones.
2. Use a lower timeframe to inspect the liquidity sweep for execution
   precision.
3. Keep the analysis focused on price action, horizontal levels, and
   time-of-day markers. Moving averages, sessions, and volume may be used as
   basic tools when relevant; this strategy does not define their parameters.

## 2. Mark Liquidity Zones

Mark only the stated, clear liquidity areas:

- recent swing highs and lows;
- the prior day's high and low;
- consolidation boundaries;
- clean, untested levels; and
- round numbers.

ERL is beyond the most significant swing high or low of the defined range.
IRL is within that range. Do not over-mark minor fluctuations; focus on a
small number of clustered, well-defined zones.

## 3. Classify the Price Move

When price reaches or moves beyond a marked zone, determine whether it is a
sweep or a run.

### Liquidity sweep

Treat the event as a potential sweep only when price pierces the level and
then rejects it. Wait for the sweep to complete and for the reaction candle to
close.

### Liquidity run

Treat the event as a liquidity run when price pushes beyond the level with
sustained follow-through and continues the existing trend structure. Do not
take the opposite-side sweep setup in this case.

Use these checks to distinguish a sweep from a run:

1. higher-timeframe bias;
2. candle or closing behavior relative to the level; and
3. the strength of follow-through after the first impulse move using volume.

If the reaction or acceptance is not clear, report insufficient evidence.

## 4. Confirm the Completed Sweep

After a completed sweep and closed reaction candle, require at least one of
the following observed confirmations:

- a market-structure shift;
- a rejection candle; or
- a volume spike.

This strategy does not define thresholds or parameters for these
confirmations. Do not infer them when they are unavailable.

## 5. Directional Setups

### Bullish setup

Consider a bullish setup only when all of the following are present:

1. Price sweeps sell-side liquidity at or below a marked low.
2. Price rejects the level and the reaction candle has closed.
3. At least one permitted confirmation is observed.

Enter in the direction opposite the sweep: long.

### Bearish setup

Consider a bearish setup only when all of the following are present:

1. Price sweeps buy-side liquidity at or above a marked high.
2. Price rejects the level and the reaction candle has closed.
3. At least one permitted confirmation is observed.

Enter in the direction opposite the sweep: short.

## 6. Invalidation and Objectives

1. Place the stop beyond the sweep extreme with a sensible buffer for a
   possible retest.
2. Use an opposing liquidity zone, an intermediate structure point, or a
   fixed risk-to-reward ratio such as 2:1 or 3:1 as the profit objective.
3. Do not state a stop, target, or entry price unless supported by current
   market evidence.

## Risk Management

- Risk a fixed, small percentage of account equity per trade; the source gives
  0.5% to 2% as examples.
- Apply a daily or session loss cap and stop trading when it is reached.
- Monitor correlation and avoid stacking liquidity-sweep positions in closely
  related markets.
- Treat each setup as one trade in a probabilistic framework, not as a
  guaranteed reversal.

## Analysis Requirements

Report the higher-timeframe bias, the marked liquidity zone, whether the move
is a sweep or run, the closed reaction, the observed confirmation, the
directional assessment, the sweep extreme, and the stated objective basis.

Return a neutral or insufficient-evidence assessment when a marked zone, a
completed and closed reaction, or a permitted confirmation is missing,
conflicting, or unclear.

Never fabricate prices, candles, volume, indicators, indicator parameters,
market structure, price levels, confirmations, or broker/execution results.
Never prescribe position size or make broker/execution calls.
