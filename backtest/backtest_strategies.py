import pandas as pd

def sr_entry(df, i):
    support_high = df["support_high_H4"].values
    support_low = df["support_low_H4"].values
    resistance_high = df["resistance_high_H4"].values
    resistance_low = df["resistance_low_H4"].values
    high = df["high_M15"].values
    low = df["high_M15"].values

    volatility_regime = df["volatility_regime_M15"].values

    if volatility_regime[i] > 1:
        if high[i] < resistance_high[i] and low[i] > resistance_low[i] and resistance_low[i] > support_high[i]:
            zone_range = resistance_high[i] - resistance_low[i]

            high_range = high[i] - resistance_low[i]

            zone = high_range * 100 / zone_range

            if zone < 50:
                return "sell", resistance_high[i], None

        if high[i] < support_high[i] and low[i] > support_low[i] and support_high[i] < resistance_low[i]:
            zone_range = support_high[i] - support_low[i]

            high_range = high[i] - support_low[i]

            zone = high_range * 100 / zone_range

            if zone > 50:
                return "buy", support_low[i], None
        
    return None, None, None

def sr_exit(df, i, pos):
    support_high = df["support_high_H4"].values
    resistance_low = df["resistance_low_H4"].values
    close = df["close_M15"].values

    if pos == "buy":
        if close[i] > resistance_low[i] and support_high[i] < resistance_low[i]:
            return True
    elif pos == "sell":
        if close[i] < support_high[i] and support_high[i] < resistance_low[i]:
            return True
    return False

def consolidation_entry(df, i):
    consolidation = df["consolidation_H1"].values
    consolidation_high = df["consolidation_high_H1"].values
    consolidation_low = df["consolidation_low_H1"].values
    high = df["high_H1"].values
    low = df["low_H1"].values
    trend = df["ema_trend_H1"].values

    if consolidation[i] == False:
        lookback = 5
        new_lookback = i - lookback
        lookback_count = 0
        if new_lookback > lookback + 1:
            for j in range(i, new_lookback, -1):
                lookback_count += 1
                if consolidation[j]:
                    if trend[i] == "down" and lookback_count == lookback:
                        lookback_count = 0
                        return "sell", consolidation_high[j], None
                    elif trend[i] == "up" and lookback_count == lookback:
                        lookback_count = 0
                        return "buy", consolidation_high[j], None
                    else:
                        lookback_count = 0
                        continue

    return None, None, None

def consolidation_exit(df, i, pos):
    consolidation = df["consolidation_H1"].values
    close = df["close_H1"].values
    if consolidation[i]:
        return True
    return False