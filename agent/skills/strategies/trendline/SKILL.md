---
name: trendline-trading-strategy
summary: Rule-based trendline strategy covering trendline construction, trend direction, trendline bounce entries, trendline break entries, and trendline-based trailing exits.
---

# Trendline Trading Strategy

## Purpose

Use trendlines to:

- identify trend direction,
- locate potential areas of buying or selling pressure,
- trade trendline bounces,
- trade trendline breaks during retracements in healthy trends,
- trail open trades and exit when the active trendline is broken.

Apply the rules below in order. Do not add extra trendlines, indicators, entry filters, or stop rules that are not defined here.

---

## 1. Build the Trendline Structure

### Step 1 — Zoom out

1. Open the trading timeframe being analyzed.
2. Zoom out so a large and consistent amount of price history is visible.
3. Use roughly 450 candles when possible.
4. Keep the amount of visible history reasonably consistent when comparing or redrawing trendlines.

### Step 2 — Select only obvious levels

1. Identify only the most obvious swing-high and swing-low structures.
2. Do not draw every minor, intermediate, and major trendline.
3. Ignore a potential trendline if it is not visually obvious from the zoomed-out chart.

### Step 3 — Draw and adjust for maximum touches

1. Draw the trendline through the selected swing structure.
2. Adjust the line so it touches as many significant swing points as possible.
3. A touch can occur on either the candle wick or candle body.
4. Prefer a trendline with more meaningful touches over one drawn only through the absolute extremes.
5. Do not require the line to touch every candle.
6. Treat the trendline as an area rather than an exact price.
7. If the area is wide, two parallel lines may be used to represent the zone.
8. If the area is already tight, do not add extra lines that make the chart unnecessarily congested.

---

## 2. Determine Trend Direction

Use the direction of the established trendline as the trend filter.

### Bullish trend

A trendline pointing higher defines a bullish directional bias.

Rule:

- Look for long opportunities.
- Avoid prioritizing counter-trend shorts.

### Bearish trend

A trendline pointing lower defines a bearish directional bias.

Rule:

- Look for short opportunities.
- Avoid prioritizing counter-trend longs.

---

# Strategy A — Trendline Bounce

## Objective

Enter in the direction of the prevailing trend when price returns to the trendline area and additional confluence is present.

## Long Setup

### Conditions

All of the following must be present:

1. The established trendline is pointing higher.
2. Price has moved into or near the rising trendline area.
3. A previous resistance area is now acting as support at or near the trendline.
4. A bullish reversal candlestick pattern forms at the area.
5. The source example uses a bullish hammer as the bullish reversal signal.

### Entry

1. Wait for price to reach the trendline/support area.
2. Wait for the bullish reversal candlestick pattern.
3. Enter long after the bullish reversal setup is confirmed.

### Stop Loss

The source does not provide a specific long-side stop-loss rule for this trendline-bounce example.

Do not invent one.

### Exit / Profit Handling

The source does not define a fixed take-profit rule for the trendline-bounce setup.

A trendline trailing exit may be used if the intention is to ride the trend. See the trailing-stop section below.

---

## Short Setup

### Conditions

All of the following must be present:

1. The established trendline is pointing lower.
2. Price has moved into or near the falling trendline area.
3. A previous swing-low/support area is now acting as resistance at or near the trendline.
4. A bearish reversal candlestick pattern forms at the area.
5. The source example uses a bearish engulfing pattern as the bearish reversal signal.

### Entry

1. Wait for price to reach the trendline/resistance area.
2. Wait for the bearish reversal candlestick pattern.
3. Enter short after the bearish reversal setup is confirmed.

### Stop Loss

1. Calculate ATR.
2. Place the stop loss 1 ATR above the relevant high.

### Exit / Profit Handling

The source does not define a fixed take-profit rule for the trendline-bounce setup.

A trendline trailing exit may be used if the intention is to ride the trend.

---

# Strategy B — Trendline Break During a Retracement

## Objective

Use a trendline drawn across the retracement to enter back in the direction of a healthy underlying trend when price does not provide the desired entry directly at the 50-period moving average.

## Preconditions

Before drawing and trading the retracement trendline:

1. Confirm that the market is in a healthy trend.
2. The market should show an obvious trend with pullbacks.
3. Use the 50-period moving average as the moving-average reference described in the source.
4. Do not draw the retracement trendline too early.

---

## Retracement Timing Rule

1. Review previous retracements in the same trend.
2. Count how many candles those retracements typically lasted.
3. Use that historical retracement length as a guide for the current retracement.
4. Example from the source:
   - if previous retracements lasted about 15 candles,
   - expect the current retracement to be roughly 10 to 20 candles.
5. If only 3 or 4 retracement candles have formed when historical retracements are much longer, do not draw and trade the trendline break yet.
6. In the example above, wait until at least about 10 retracement candles have formed before creating the trendline-break setup.

---

## Moving-Average Proximity Rule

Before taking the trendline-break entry:

1. Price should have approached near the 50-period moving average.
2. Do not take the trendline-break setup while price is still far from the 50-period moving average.

---

## Long Trendline-Break Setup

### Conditions

1. The underlying market trend is bullish.
2. Price is retracing lower within that bullish trend.
3. The retracement has matured based on the historical retracement-candle count.
4. Price has approached near the 50-period moving average.
5. Draw a descending trendline across the retracement move.

### Entry

1. Wait for price to break the descending retracement trendline.
2. Require a candle to close above the trendline.
3. Enter long after the break-and-close-above condition is satisfied.

### Stop Loss

1. Identify the retracement swing low.
2. Place the stop loss below the swing low.
3. Give the stop some additional room below the swing low rather than placing it directly on the low.

### Exit

The source does not define a fixed take-profit target for this setup.

The trendline trailing-stop method may be used to ride the trend.

---

## Short Trendline-Break Setup

### Conditions

1. The underlying market trend is bearish.
2. Price is retracing higher within that bearish trend.
3. The retracement has matured based on the historical retracement-candle count.
4. Price has approached near the 50-period moving average.
5. Draw an ascending trendline across the retracement move.

### Entry

1. Wait for price to break the ascending retracement trendline.
2. Require a candle to close below the trendline.
3. Enter short after the break-and-close-below condition is satisfied.

### Stop Loss

1. Identify the retracement swing high.
2. Place the stop loss above the swing high.
3. Give the stop some additional room above the swing high rather than placing it directly on the high.

### Exit

The source does not define a fixed take-profit target for this setup.

The trendline trailing-stop method may be used to ride the trend.

---

# Strategy C — Trendline Trailing Stop

## Objective

Remain in a trending trade until price breaks and closes through the active trendline against the trade direction.

## Short Position

1. Maintain the relevant falling trendline while the downtrend remains active.
2. Stay in the short trade while price remains below the trendline.
3. Exit the short only when price breaks above the trendline and closes above it.

## Long Position

1. Maintain the relevant rising trendline while the uptrend remains active.
2. Stay in the long trade while price remains above the trendline.
3. Exit the long only when price breaks below the trendline and closes below it.

---

# Parabolic Trend Protection

Use this rule when an existing trend becomes increasingly aggressive.

## Detection Clues

Treat the move as potentially parabolic when either of the following develops:

1. Successive trendlines become steeper and steeper.
2. Candle ranges become larger and larger.

## Management Rule

1. Continue holding the existing trend-following position.
2. Draw a new trendline that follows the newer, steeper market structure.
3. Continue updating the trendline as new swings form.
4. Use the most recent valid trendline as the active trailing line.
5. For a long trade, stay in the trade while price remains above the active trendline.
6. Exit the long when price breaks and closes below the active trendline.
7. Apply the inverse logic to a short trade.

Note: the source explicitly states that consistently updating these trendlines contains an element of subjectivity.

---
