---
name: technical-indicators
description: >
  Reference skill for selecting, configuring, and combining the technical indicators,
  price levels, zones, trend models, candlestick patterns, and fair value gaps supported
  by the trading agent. Use this skill whenever the agent needs to build an indicator
  configuration for market analysis, signal generation, strategy construction, or trade filtering.
---

# Technical Indicators Registry Skill

## Purpose

This skill tells the trading agent:

- which indicators are available;
- what each indicator is intended to measure;
- which parameters are valid;
- what outputs each indicator produces;
- how to choose an appropriate timeframe;
- how to combine indicators without inventing unsupported names or parameters;
- how to produce a valid `indicators` configuration.

The agent MUST use indicator names and parameter names exactly as documented here.

---

# 1. Output Contract

When indicators are requested, return a list in this structure:

```python
indicators = [
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {
            "timeperiod": 20
        }
    }
]
```

A minimal indicator may omit `params` when defaults are acceptable:

```python
{
    "indicator": "BBANDS",
    "timeframe": "H1"
}
```


## Output Naming and Aliasing

Every indicator output is converted to a final dataframe/feature name by appending the indicator timeframe:

```text
<output_name>_<TIMEFRAME>
```

Examples:

```python
{
    "indicator": "EMA",
    "timeframe": "H1",
    "params": {
        "timeperiod": 22
    }
}
```

Native output:

```text
ema_H1
```

To make the period explicit in the feature name:

```python
{
    "indicator": "EMA",
    "timeframe": "H1",
    "params": {
        "timeperiod": 22
    },
    "outputs": ["ema_22"]
}
```

Final output:

```text
ema_22_H1
```

This is especially useful when the same indicator is configured multiple times on the same timeframe:

```python
[
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {"timeperiod": 9},
        "outputs": ["ema_9"]
    },
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {"timeperiod": 50},
        "outputs": ["ema_50"]
    }
]
```

Final columns:

```text
ema_9_H1
ema_50_H1
```

For a multi-output indicator, rename every output in native output order.

Example:

```python
{
    "indicator": "MACD",
    "timeframe": "M15",
    "params": {
        "fastperiod": 12,
        "slowperiod": 26,
        "signalperiod": 9
    },
    "outputs": [
        "macd_12_26",
        "macd_signal_9",
        "macd_hist_12_26_9"
    ]
}
```

Final columns:

```text
macd_12_26_M15
macd_signal_9_M15
macd_hist_12_26_9_M15
```

For zone indicators, aliases also receive the timeframe suffix.

```python
{
    "indicator": "DEMAND_ZONE",
    "timeframe": "H1",
    "params": {
        "sd_lookback_hours": 24
    },
    "outputs": [
        "demand_24h_low",
        "demand_24h_high"
    ]
}
```

Final columns:

```text
demand_24h_low_H1
demand_24h_high_H1
```

### Output alias rules

- `outputs` is optional.
- If omitted, use the registry's native output names.
- If provided, use the supplied names as the base output names.
- Do NOT manually append the timeframe inside `outputs`.
- The runtime appends `_<TF>` automatically.
- Prefer descriptive aliases when multiple instances of the same indicator would otherwise collide.
- For period-based indicators, including the period in the alias is recommended, e.g. `ema_9`, `ema_50`, `rsi_14`.
- For lookback-based features, including the lookback may improve clarity, e.g. `rolling_high_4h`.
- For multi-output indicators, preserve the native output order.

## Rules

1. `indicator` MUST match one of the supported indicator identifiers in this skill.
2. `timeframe` is required by the trading-agent configuration even though timeframe is not defined inside the raw registry.
3. Only include parameters supported by that indicator.
4. Do not invent parameter names.
5. When a parameter is omitted, assume the registry default.
6. Prefer explicit parameters when the user's strategy depends on a specific period or lookback.
7. `outputs` MAY be supplied to rename/alias the indicator outputs.
8. Native outputs are listed for every indicator below and are used when `outputs` is omitted.
9. When `outputs` is supplied, each provided name replaces the corresponding native output name.
10. The execution layer appends the configured timeframe to every final output column using the form `<output>_<TF>`.
11. Therefore, `{"indicator": "EMA", "timeframe": "H1"}` produces `ema_H1`, while `{"indicator": "EMA", "timeframe": "H1", "outputs": ["ema_22"]}` produces `ema_22_H1`.
12. For multi-output indicators, the number and order of custom `outputs` MUST match the native outputs unless the runtime explicitly supports partial output selection.
13. Different indicators may use different timeframes in the same strategy.
14. Use higher timeframes for context and lower timeframes for execution when appropriate.
15. Avoid adding indicators that do not contribute to the trading hypothesis.

---

# 2. Typical Multi-Timeframe Usage

A common structure is:

- `D1` / `H4`: market structure, major trend, major levels.
- `H1`: directional bias, supply/demand, support/resistance.
- `M15`: setup confirmation.
- `M5` / `M1`: execution, volatility state, precise entry logic.

Example:

```python
indicators = [
    {
        "indicator": "COMBINED_TREND",
        "timeframe": "H4",
        "params": {
            "hours": 4,
            "fast_span": 9,
            "slow_span": 50
        }
    },
    {
        "indicator": "DEMAND_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 24
        }
    },
    {
        "indicator": "RSI",
        "timeframe": "M15",
        "params": {
            "timeperiod": 14
        }
    },
    {
        "indicator": "VOLATILITY_REGIME",
        "timeframe": "M5",
        "params": {
            "regime_lookback": 100
        }
    }
]
```

---

# 3. Indicator Categories

The available indicator families are:

1. Trend Indicators
2. Momentum Indicators
3. Volatility Indicators
4. Volume Indicators
5. Price Transform / Regression Indicators
6. Candlestick Patterns
7. Historical Price Levels
8. Supply / Demand Zones
9. Support / Resistance Zones
10. Session Levels
11. Rolling High / Low Levels
12. Custom Trend Models
13. Fair Value Gaps

---

# 4. Trend Indicators

Trend indicators estimate market direction or trend strength.

## SMA — Simple Moving Average

**Use for:** smoothed direction, dynamic support/resistance, moving-average crossovers.

**Inputs:** `close`

**Parameters:**

- `timeperiod`: int, default `14`, min `1`, max `500`

**Outputs:** `sma`

Example:

```python
{
    "indicator": "SMA",
    "timeframe": "H1",
    "params": {
        "timeperiod": 20
    }
}
```

Typical interpretation:

- close above SMA → bullish bias;
- close below SMA → bearish bias;
- fast SMA crossing above slow SMA → bullish trend transition.

---

## EMA — Exponential Moving Average

**Use for:** responsive trend direction, fast/slow EMA systems, pullbacks in trending markets.

**Inputs:** `close`

**Parameters:**

- `timeperiod`: int, default `14`, min `1`, max `500`

**Outputs:** `ema`

Example:

```python
{
    "indicator": "EMA",
    "timeframe": "H1",
    "params": {
        "timeperiod": 22
    },
    "outputs": ["ema_22"]
}
```

Final output column:

```text
ema_22_H1
```

Two-EMA example:

```python
[
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {"timeperiod": 9},
        "outputs": ["ema_9"]
    },
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {"timeperiod": 50},
        "outputs": ["ema_50"]
    }
]
```

Final output columns:

```text
ema_9_H1
ema_50_H1
```

Typical interpretation:

- EMA 9 > EMA 50 → bullish trend bias;
- EMA 9 < EMA 50 → bearish trend bias.

---

## WMA — Weighted Moving Average

**Use for:** moving-average trend detection with more weight on recent prices.

**Inputs:** `close`

**Parameters:**

- `timeperiod`: int, default `14`

**Outputs:** `wma`

```python
{
    "indicator": "WMA",
    "timeframe": "H1",
    "params": {
        "timeperiod": 20
    }
}
```

---

## DEMA — Double Exponential Moving Average

**Use for:** lower-lag trend tracking.

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `dema`

```python
{
    "indicator": "DEMA",
    "timeframe": "H1",
    "params": {"timeperiod": 20}
}
```

---

## TEMA — Triple Exponential Moving Average

**Use for:** low-lag moving-average trend systems.

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `tema`

---

## KAMA — Kaufman Adaptive Moving Average

**Use for:** adaptive trend following where market noise changes over time.

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `kama`

---

## SAR — Parabolic SAR

**Use for:** directional trend following and trailing-stop style logic.

**Inputs:** `high`, `low`

**Parameters:**

- `acceleration`: float, default `0.02`
- `maximum`: float, default `0.2`

**Outputs:** `sar`

```python
{
    "indicator": "SAR",
    "timeframe": "M15",
    "params": {
        "acceleration": 0.02,
        "maximum": 0.2
    }
}
```

Typical interpretation:

- SAR below price → bullish;
- SAR above price → bearish.

---

## ADX — Average Directional Index

**Use for:** measuring trend strength, not direction.

**Inputs:** `high`, `low`, `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `adx`

```python
{
    "indicator": "ADX",
    "timeframe": "H1",
    "params": {"timeperiod": 14}
}
```

Typical interpretation:

- rising/high ADX → stronger directional market;
- low ADX → weak trend or consolidation.

Do not use ADX alone to decide bullish vs bearish direction.

---

## PLUS_DI / MINUS_DI

**Use for:** directional component of the ADX/DMI system.

**Inputs:** `high`, `low`, `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:**

- `PLUS_DI` → `plus_di`
- `MINUS_DI` → `minus_di`

Example:

```python
[
    {
        "indicator": "PLUS_DI",
        "timeframe": "H1",
        "params": {"timeperiod": 14}
    },
    {
        "indicator": "MINUS_DI",
        "timeframe": "H1",
        "params": {"timeperiod": 14}
    }
]
```

Typical interpretation:

- PLUS_DI > MINUS_DI → bullish directional pressure;
- MINUS_DI > PLUS_DI → bearish directional pressure.

---

# 5. Momentum Indicators

Momentum indicators measure the speed, strength, or persistence of price movement.

## RSI — Relative Strength Index

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `rsi`

```python
{
    "indicator": "RSI",
    "timeframe": "M15",
    "params": {
        "timeperiod": 14
    }
}
```

Typical uses:

- momentum confirmation;
- overbought/oversold context;
- divergence;
- pullback confirmation inside a larger trend.

Do not automatically treat overbought as a sell or oversold as a buy.

---

## MACD

**Inputs:** `close`

**Parameters:**

- `fastperiod`: default `12`
- `slowperiod`: default `26`
- `signalperiod`: default `9`

**Outputs:** `macd`, `signal`, `hist`

```python
{
    "indicator": "MACD",
    "timeframe": "H1",
    "params": {
        "fastperiod": 12,
        "slowperiod": 26,
        "signalperiod": 9
    }
}
```

Typical uses:

- momentum direction;
- MACD/signal cross;
- histogram acceleration/deceleration;
- trend continuation confirmation.

---

## STOCH

**Inputs:** `high`, `low`, `close`

**Parameters:** none exposed in the current registry.

**Outputs:** `slowk`, `slowd`

```python
{
    "indicator": "STOCH",
    "timeframe": "M15"
}
```

---

## STOCHF

**Inputs:** `high`, `low`, `close`

**Parameters:** none exposed in the current registry.

**Outputs:** `fastk`, `fastd`

---

## CCI

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `cci`

**Use for:** momentum extremes and cyclical movement.

---

## ROC

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `roc`

**Use for:** percentage-style rate of change / acceleration.

---

## MOM

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `mom`

**Use for:** raw momentum comparison.

---

## TRIX

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `trix`

**Use for:** smoothed momentum and trend changes.

---

# 6. Volatility Indicators

## ATR

**Inputs:** `high`, `low`, `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `atr`

```python
{
    "indicator": "ATR",
    "timeframe": "M15",
    "params": {
        "timeperiod": 14
    }
}
```

Typical uses:

- stop distance;
- trailing stop;
- volatility filters;
- minimum movement requirements;
- position sizing.

---

## NATR

Normalized ATR.

**Inputs:** `high`, `low`, `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `natr`

**Use for:** comparing volatility across instruments or price scales.

---

## BBANDS — Bollinger Bands

**Inputs:** `close`

**Parameters:**

- `timeperiod`: default `20`
- `nbdevup`: default `2`
- `nbdevdn`: default `2`

**Outputs:**

- `bbands_upper`
- `bbands_middle`
- `bbands_lower`

```python
{
    "indicator": "BBANDS",
    "timeframe": "H1",
    "params": {
        "timeperiod": 20,
        "nbdevup": 2,
        "nbdevdn": 2
    }
}
```

Typical uses:

- volatility expansion/contraction;
- price location relative to bands;
- mean-reversion context;
- breakout context.

---

## VOLATILITY_REGIME

Custom volatility-state classifier.

**Inputs:** `high`, `low`, `close`

**Parameters:**

- `timeperiod`: int, default `14`, min `1`, max `500`
- `regime_lookback`: int, default `100`, min `2`, max `5000`
- `low_percentile`: float, default `33`
- `high_percentile`: float, default `66`

**Outputs:** `volatility_regime`

**Output type:** scalar

```python
{
    "indicator": "VOLATILITY_REGIME",
    "timeframe": "M5",
    "params": {
        "timeperiod": 14,
        "regime_lookback": 100,
        "low_percentile": 33,
        "high_percentile": 66
    }
}
```

Typical use:

- allow breakout systems only during sufficiently high volatility;
- avoid entries in excessively quiet markets;
- switch strategy behavior by volatility state.

Do not assume exact numeric regime labels unless the runtime implementation defines them separately.

---

# 7. Volume Indicators

The current registry exposes:

- `OBV`
- `MFI`
- `AD`
- `ADOSC`

**Inputs:** `high`, `low`, `close`, `volume`

**Parameters:** none exposed in the registry.

**Outputs:** lowercase indicator name.

Example:

```python
{
    "indicator": "OBV",
    "timeframe": "H1"
}
```

Possible uses:

- price/volume confirmation;
- accumulation/distribution context;
- divergence;
- momentum validation.

Important: forex volume may represent tick volume depending on the data source.

---

# 8. Price Transform / Regression Indicators

## LINEARREG

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `linearreg`

**Use for:** smoothed regression-based price estimate.

```python
{
    "indicator": "LINEARREG",
    "timeframe": "H1",
    "params": {"timeperiod": 20}
}
```

## LINEARREG_SLOPE

**Inputs:** `close`

**Parameters:** `timeperiod`, default `14`

**Outputs:** `linearreg_slope`

**Use for:** regression trend direction and magnitude.

Typical interpretation:

- slope > 0 → rising regression trend;
- slope < 0 → falling regression trend.

---

# 9. Candlestick Patterns

All candlestick pattern indicators require:

`open`, `high`, `low`, `close`

The registry defines:

- `CDLENGULFING` — Engulfing
- `CDLHAMMER` — Hammer
- `CDLINVERTEDHAMMER` — Inverted Hammer
- `CDLSHOOTINGSTAR` — Shooting Star
- `CDLDOJI` — Doji
- `CDLDRAGONFLYDOJI` — Dragonfly Doji
- `CDLGRAVESTONEDOJI` — Gravestone Doji
- `CDLMORNINGSTAR` — Morning Star
- `CDLEVENINGSTAR` — Evening Star
- `CDLPIERCING` — Piercing
- `CDLDARKCLOUDCOVER` — Dark Cloud Cover
- `CDL3WHITESOLDIERS` — Three White Soldiers
- `CDL3BLACKCROWS` — Three Black Crows
- `CDLHARAMI` — Harami
- `CDLHARAMICROSS` — Harami Cross
- `CDLSPINNINGTOP` — Spinning Top
- `CDLTAKURI` — Takuri
- `CDLUPSIDEGAP2CROWS` — Upside Gap Two Crows
- `CDLSEPARATINGLINES` — Separating Lines

**Parameters:** none.

**Native signal meaning:**

- `100` → Bullish
- `-100` → Bearish
- `0` → None

Example:

```python
{
    "indicator": "CDLENGULFING",
    "timeframe": "M15"
}
```

Use candlestick patterns as setup confirmation rather than automatically treating every detected pattern as a complete trading signal.

Example combination:

```python
[
    {
        "indicator": "DEMAND_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 24
        }
    },
    {
        "indicator": "CDLENGULFING",
        "timeframe": "M15"
    }
]
```

Possible reasoning:

> Look for bullish engulfing confirmation on M15 when price interacts with an H1 demand zone.

---

# 10. Historical Price Levels

These indicators return scalar historical levels.

## PREV_DAY_HIGH

**Outputs:** `prev_day_high`

Default parameters:

```python
{
    "lookback_periods": 1,
    "price_field": "high"
}
```

Example:

```python
{
    "indicator": "PREV_DAY_HIGH",
    "timeframe": "H1"
}
```

## PREV_DAY_LOW

**Outputs:** `prev_day_low`

## DAY_BEFORE_PREV_HIGH

**Outputs:** `day_before_prev_day_high`

## DAY_BEFORE_PREV_LOW

**Outputs:** `day_before_prev_day_low`

## LAST_WEEK_HIGH

**Outputs:** `last_week_high`

## LAST_WEEK_LOW

**Outputs:** `last_week_low`

### Common uses

- liquidity sweeps;
- breakout confirmation;
- rejection entries;
- target selection;
- market structure context.

Example liquidity-sweep context:

```python
[
    {
        "indicator": "PREV_DAY_LOW",
        "timeframe": "M15"
    },
    {
        "indicator": "LONDON_LOW",
        "timeframe": "M15"
    }
]
```

---

# 11. Supply and Demand Zones

Zones return a lower and upper boundary.

Common base parameters for zone indicators:

- `lookback_bars`: default `50`, min `0`, max `500`
- `lookback_hours`: default `0`, min `0`, max `720`
- `zone_index`: default `0`, min `0`, max `10`

`zone_index = 0` normally means the first/current returned zone according to the runtime detector.

Do not assume exact ordering beyond what the detector implementation guarantees.

---

## SUPPLY_ZONE

**Detection method:** `supply_demand`

**Inputs:** `open`, `high`, `low`, `close`

Additional parameters:

- `sd_lookback`: int, default `60`, min `1`, max `1440`
- `sd_lookback_hours`: float, default `0`, min `0`, max `720`
- `sd_max_base_candles`: int, default `30`, min `2`, max `300`

**Outputs:**

- `supply_low`
- `supply_high`

```python
{
    "indicator": "SUPPLY_ZONE",
    "timeframe": "H1",
    "params": {
        "sd_lookback_hours": 5
    }
}
```

Typical use:

- bearish reaction areas;
- short setup context;
- target for long positions;
- invalidation/structure context.

---

## DEMAND_ZONE

Same parameters as `SUPPLY_ZONE`.

**Outputs:**

- `demand_low`
- `demand_high`

```python
{
    "indicator": "DEMAND_ZONE",
    "timeframe": "H1",
    "params": {
        "sd_lookback_hours": 5
    }
}
```

Typical use:

- bullish reaction areas;
- long setup context;
- target for short positions.

---

# 12. Support and Resistance Zones

## RESISTANCE_ZONE

**Detection method:** `support_resistance`

Additional parameters:

- `sr_hours`: int, default `24`, min `1`, max `720`
- `sr_timeframe_minutes`: int, default `15`, min `1`, max `1440`
- `zone_buffer`: float, default `0.0003`, min `0.0`, max `0.01`

Also supports the common zone parameters:

- `lookback_bars`
- `lookback_hours`
- `zone_index`

**Outputs:**

- `resistance_low`
- `resistance_high`

Correct example:

```python
{
    "indicator": "RESISTANCE_ZONE",
    "timeframe": "H1",
    "params": {
        "sr_hours": 5
    }
}
```

Do NOT use `sr_lookback_hours`; it is not defined in the current registry.

---

## SUPPORT_ZONE

Same parameters as `RESISTANCE_ZONE`.

**Outputs:**

- `support_low`
- `support_high`

```python
{
    "indicator": "SUPPORT_ZONE",
    "timeframe": "H1",
    "params": {
        "sr_hours": 5
    }
}
```

Typical uses:

- reaction areas;
- breakout/retest setups;
- range boundaries;
- entry filters.

---

# 13. Session High / Low

These indicators expose session extremes.

Supported sessions in the registry:

- `london`
- `newyork`
- `asian`

## Available indicators

- `LONDON_HIGH` → `london_high`
- `LONDON_LOW` → `london_low`
- `NEWYORK_HIGH` → `newyork_high`
- `NEWYORK_LOW` → `newyork_low`
- `ASIAN_HIGH` → `asian_high`
- `ASIAN_LOW` → `asian_low`

Example:

```python
[
    {
        "indicator": "LONDON_HIGH",
        "timeframe": "M15"
    },
    {
        "indicator": "LONDON_LOW",
        "timeframe": "M15"
    }
]
```

Common uses:

- session range;
- liquidity sweeps;
- London/New York breakout strategies;
- stop placement;
- intraday targets.

---

# 14. Rolling High / Low

## ROLLING_HIGH

**Parameters:**

- `hours`: int, default `4`, min `1`, max `168`
- `price_field`: fixed/default `high`

**Outputs:** `rolling_high`

```python
{
    "indicator": "ROLLING_HIGH",
    "timeframe": "M15",
    "params": {
        "hours": 4
    }
}
```

## ROLLING_LOW

**Outputs:** `rolling_low`

```python
{
    "indicator": "ROLLING_LOW",
    "timeframe": "M15",
    "params": {
        "hours": 4
    }
}
```

Common uses:

- recent range boundaries;
- breakout detection;
- stop/target context;
- rolling liquidity levels.

---

# 15. Custom Trend Models

These are custom higher-level trend features.

## SLOPE_TREND

**Inputs:** `close`

**Parameters:**

- `hours`: int, default `4`, min `1`, max `72`

**Outputs:**

- `slope`
- `slope_trend`

**Output type:** multi

```python
{
    "indicator": "SLOPE_TREND",
    "timeframe": "H1",
    "params": {
        "hours": 4
    }
}
```

---

## EMA_TREND

**Inputs:** `close`

**Parameters:**

- `fast_span`: int, default `9`, min `2`, max `50`
- `slow_span`: int, default `50`, min `5`, max `200`

**Outputs:**

- `ema_fast`
- `ema_slow`
- `ema_trend`

```python
{
    "indicator": "EMA_TREND",
    "timeframe": "H1",
    "params": {
        "fast_span": 9,
        "slow_span": 50
    }
}
```

---

## COMBINED_TREND

Combines slope and EMA-based trend information.

**Parameters:**

- `hours`: int, default `4`, min `1`, max `72`
- `fast_span`: int, default `9`, min `2`, max `50`
- `slow_span`: int, default `50`, min `5`, max `200`

**Outputs:**

- `slope`
- `slope_trend`
- `ema_fast`
- `ema_slow`
- `ema_trend`
- `trend`

```python
{
    "indicator": "COMBINED_TREND",
    "timeframe": "H4",
    "params": {
        "hours": 4,
        "fast_span": 9,
        "slow_span": 50
    }
}
```

**Use for:** obtaining a higher-level trend bias without manually combining separate EMA and slope indicators.

---

# 16. Fair Value Gaps

Fair value gaps are three-candle imbalance zones.

The registry models:

- bullish FVG: gap between the earlier candle high and later candle low;
- bearish FVG: gap between the earlier candle low and later candle high.

Common parameters:

- `lookback_bars`: int, default `100`
- `lookback_hours`: float, default `None`
- `min_gap_pct`: float, default `0.0`, min `0.0`, max `0.1`
- `zone_index`: int, default `0`
- `mitigated`: bool, default `False`

`mitigated=False` means the detector should skip gaps that price has already returned into according to the implementation.

---

## BULLISH_FVG

**Outputs:**

- `bullish_fvg_low`
- `bullish_fvg_high`

```python
{
    "indicator": "BULLISH_FVG",
    "timeframe": "M15",
    "params": {
        "lookback_bars": 100,
        "min_gap_pct": 0.0005,
        "zone_index": 0,
        "mitigated": False
    }
}
```

Typical use:

- bullish retracement zone;
- continuation entry context;
- confluence with demand/support.

---

## BEARISH_FVG

**Outputs:**

- `bearish_fvg_low`
- `bearish_fvg_high`

```python
{
    "indicator": "BEARISH_FVG",
    "timeframe": "M15",
    "params": {
        "lookback_bars": 100,
        "mitigated": False
    }
}
```

---

# 17. Strategy Construction Patterns

## A. Trend Following

Goal: trade in the direction of an established trend.

```python
indicators = [
    {
        "indicator": "COMBINED_TREND",
        "timeframe": "H4",
        "params": {
            "hours": 4,
            "fast_span": 9,
            "slow_span": 50
        }
    },
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {
            "timeperiod": 20
        }
    },
    {
        "indicator": "ADX",
        "timeframe": "H1",
        "params": {
            "timeperiod": 14
        }
    }
]
```

Possible logic:

- H4 trend determines direction;
- H1 EMA provides dynamic trend location;
- ADX filters weak/non-trending periods.

---

## B. Supply / Demand Reversal

```python
indicators = [
    {
        "indicator": "SUPPLY_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 24
        }
    },
    {
        "indicator": "DEMAND_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 24
        }
    },
    {
        "indicator": "CDLENGULFING",
        "timeframe": "M15"
    },
    {
        "indicator": "RSI",
        "timeframe": "M15",
        "params": {
            "timeperiod": 14
        }
    }
]
```

Possible logic:

- price reaches H1 supply/demand;
- M15 price action confirms;
- RSI supplies momentum context.

---

## C. Liquidity Sweep

```python
indicators = [
    {
        "indicator": "PREV_DAY_HIGH",
        "timeframe": "M15"
    },
    {
        "indicator": "PREV_DAY_LOW",
        "timeframe": "M15"
    },
    {
        "indicator": "LONDON_HIGH",
        "timeframe": "M15"
    },
    {
        "indicator": "LONDON_LOW",
        "timeframe": "M15"
    }
]
```

Possible logic:

- detect price trading through a known historical/session level;
- require a close back through the level;
- optionally combine with trend or candlestick confirmation.

---

## D. Breakout + Volatility

```python
indicators = [
    {
        "indicator": "ROLLING_HIGH",
        "timeframe": "M15",
        "params": {
            "hours": 4
        }
    },
    {
        "indicator": "ROLLING_LOW",
        "timeframe": "M15",
        "params": {
            "hours": 4
        }
    },
    {
        "indicator": "VOLATILITY_REGIME",
        "timeframe": "M5",
        "params": {
            "regime_lookback": 100
        }
    },
    {
        "indicator": "ATR",
        "timeframe": "M15",
        "params": {
            "timeperiod": 14
        }
    }
]
```

Possible logic:

- detect breakout of recent rolling range;
- reject trades in unsuitable volatility regimes;
- use ATR to normalize breakout size or risk.

---

## E. FVG Continuation

```python
indicators = [
    {
        "indicator": "EMA_TREND",
        "timeframe": "H1",
        "params": {
            "fast_span": 9,
            "slow_span": 50
        }
    },
    {
        "indicator": "BULLISH_FVG",
        "timeframe": "M15",
        "params": {
            "lookback_bars": 100,
            "mitigated": False
        }
    },
    {
        "indicator": "BEARISH_FVG",
        "timeframe": "M15",
        "params": {
            "lookback_bars": 100,
            "mitigated": False
        }
    }
]
```

Possible logic:

- only consider bullish FVGs in bullish trend;
- only consider bearish FVGs in bearish trend;
- wait for price to retrace into the gap.

---

# 18. Choosing Indicators from Natural Language

When the user describes a strategy, map concepts to indicators.

| User concept | Prefer |
|---|---|
| trend direction | `EMA_TREND`, `COMBINED_TREND`, `EMA`, `SMA` |
| trend strength | `ADX`, `PLUS_DI`, `MINUS_DI` |
| momentum | `RSI`, `MACD`, `MOM`, `ROC`, `CCI`, `TRIX` |
| volatility | `ATR`, `NATR`, `BBANDS`, `VOLATILITY_REGIME` |
| supply / demand | `SUPPLY_ZONE`, `DEMAND_ZONE` |
| support / resistance | `SUPPORT_ZONE`, `RESISTANCE_ZONE` |
| yesterday high/low | `PREV_DAY_HIGH`, `PREV_DAY_LOW` |
| previous week levels | `LAST_WEEK_HIGH`, `LAST_WEEK_LOW` |
| London range | `LONDON_HIGH`, `LONDON_LOW` |
| New York range | `NEWYORK_HIGH`, `NEWYORK_LOW` |
| Asian range | `ASIAN_HIGH`, `ASIAN_LOW` |
| recent N-hour range | `ROLLING_HIGH`, `ROLLING_LOW` |
| fair value gap / imbalance | `BULLISH_FVG`, `BEARISH_FVG` |
| candle confirmation | `CDL*` patterns |
| regression slope | `LINEARREG_SLOPE`, `SLOPE_TREND` |
| volume confirmation | `OBV`, `MFI`, `AD`, `ADOSC` |

---

# 19. Agent Decision Rules

The trading agent SHOULD:

1. Start from the trading idea, not from the indicator list.
2. Select the minimum indicators required to express the idea.
3. Separate:
   - context indicators;
   - setup indicators;
   - confirmation indicators;
   - volatility/risk filters.
4. Prefer higher-timeframe context and lower-timeframe execution when the strategy is multi-timeframe.
5. Use zones/levels for location.
6. Use trend indicators for direction.
7. Use momentum/candlesticks for confirmation.
8. Use volatility indicators for regime/risk.
9. Avoid duplicate indicators that measure nearly identical information unless comparison itself is part of the strategy.
10. Never claim an indicator guarantees a profitable trade.
11. Never silently invent unavailable indicators.
12. Never silently invent parameter names.
13. Never use unsupported parameter values outside documented min/max bounds.
14. Preserve the user's requested timeframe unless it conflicts with the strategy specification.
15. When the user does not provide periods, use registry defaults unless there is a clear strategy reason to choose another value.

---

# 20. Validation Checklist

Before returning an indicator configuration, verify:

- [ ] Every indicator exists in this skill.
- [ ] Every indicator has a timeframe.
- [ ] Every parameter belongs to that indicator.
- [ ] Parameter types are correct.
- [ ] Values respect min/max constraints when defined.
- [ ] Custom `outputs`, when provided, match the native output count/order.
- [ ] Custom output aliases do not already include the timeframe suffix.
- [ ] Final runtime output names follow `<output>_<TF>`.
- [ ] No duplicate indicator configuration was added accidentally.
- [ ] The indicators collectively implement the user's trading hypothesis.
- [ ] Higher/lower timeframe roles are internally consistent.

---

# 21. Corrected Version of the Example Configuration

```python
indicators = [
    {
        "indicator": "SUPPLY_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 5
        }
    },
    {
        "indicator": "DEMAND_ZONE",
        "timeframe": "H1",
        "params": {
            "sd_lookback_hours": 5
        }
    },
    {
        "indicator": "RESISTANCE_ZONE",
        "timeframe": "H1",
        "params": {
            "sr_hours": 5
        }
    },
    {
        "indicator": "SUPPORT_ZONE",
        "timeframe": "H1",
        "params": {
            "sr_hours": 5
        }
    },
    {
        "indicator": "VOLATILITY_REGIME",
        "timeframe": "M5",
        "params": {
            "regime_lookback": 5
        }
    },
    {
        "indicator": "BBANDS",
        "timeframe": "H1"
    },
    {
        "indicator": "EMA",
        "timeframe": "H1",
        "params": {
            "timeperiod": 22
        },
        "outputs": ["ema_22"]
    },
    {
        "indicator": "SMA",
        "timeframe": "H1",
        "params": {
            "timeperiod": 20
        }
    }
]
```

The EMA alias `ema_22` becomes the final runtime output `ema_22_H1`. If `outputs` were omitted, the same configuration would use the native output `ema_H1`.

Note that `regime_lookback=5` is valid according to the registry minimum of `2`, but it is much shorter than the registry default of `100`. The agent should only use such a short regime lookback when the strategy explicitly requires very short-term regime classification.

---

# 22. Complete Supported Indicator Index

## Trend

`SMA`, `EMA`, `WMA`, `DEMA`, `TEMA`, `KAMA`, `SAR`, `ADX`, `PLUS_DI`, `MINUS_DI`

## Momentum

`RSI`, `MACD`, `STOCH`, `STOCHF`, `CCI`, `ROC`, `MOM`, `TRIX`

## Volatility

`ATR`, `NATR`, `BBANDS`, `VOLATILITY_REGIME`

## Volume

`OBV`, `MFI`, `AD`, `ADOSC`

## Price Transform

`LINEARREG`, `LINEARREG_SLOPE`

## Candlestick Patterns

`CDLENGULFING`, `CDLHAMMER`, `CDLINVERTEDHAMMER`, `CDLSHOOTINGSTAR`,
`CDLDOJI`, `CDLDRAGONFLYDOJI`, `CDLGRAVESTONEDOJI`, `CDLMORNINGSTAR`,
`CDLEVENINGSTAR`, `CDLPIERCING`, `CDLDARKCLOUDCOVER`, `CDL3WHITESOLDIERS`,
`CDL3BLACKCROWS`, `CDLHARAMI`, `CDLHARAMICROSS`, `CDLSPINNINGTOP`,
`CDLTAKURI`, `CDLUPSIDEGAP2CROWS`, `CDLSEPARATINGLINES`

## Historical Price Levels

`PREV_DAY_HIGH`, `PREV_DAY_LOW`, `DAY_BEFORE_PREV_HIGH`,
`DAY_BEFORE_PREV_LOW`, `LAST_WEEK_HIGH`, `LAST_WEEK_LOW`

## Supply / Demand

`SUPPLY_ZONE`, `DEMAND_ZONE`

## Support / Resistance

`RESISTANCE_ZONE`, `SUPPORT_ZONE`

## Session Levels

`LONDON_HIGH`, `LONDON_LOW`, `NEWYORK_HIGH`, `NEWYORK_LOW`,
`ASIAN_HIGH`, `ASIAN_LOW`

## Rolling Levels

`ROLLING_HIGH`, `ROLLING_LOW`

## Custom Trend Models

`SLOPE_TREND`, `EMA_TREND`, `COMBINED_TREND`

## Fair Value Gaps

`BULLISH_FVG`, `BEARISH_FVG`
