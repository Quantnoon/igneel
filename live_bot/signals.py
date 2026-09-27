import math

def get_test_signal(df, i):
    # low = df["low_M1"].values
    # high = df["high_M1"].values
    # sma = df["sma_M1"].values

    # if sma[i] < low[i]:
    #     return "buy"
    # elif sma[i] > high[i]:
    #     return "sell"
    # else:
    #     return None
    return None, None

def get_test_exit_signal(df, i, pos):
    return True

def sd_entry(df, i):
    demand_low = df["demand_low_H1"].values
    demand_high = df["demand_high_H1"].values
    supply_low = df["supply_low_H1"].values
    supply_high = df["supply_high_H1"].values

    bbands_middle = df["bbands_middle_H1"].values

    close = df["close_M5"].values

    if close[i] > supply_low[i] and close[i] < supply_high[i] and close[i] < bbands_middle[i]:
        return "sell"

    elif close[i] > demand_low[i] and close[i] < demand_high[i] and close[i] > bbands_middle[i]:
        return "buy"

    else:
        return None

def sd_exit(df, i, pos):
    bbands_upper = df["bbands_upper_H1"].values
    bbands_middle = df["bbands_middle_H1"].values
    bbands_lower = df["bbands_lower_H1"].values

    close = df["close_M5"].values

    if pos == "buy" and (close[i] > bbands_upper[i] or close[i] < bbands_middle[i]):
        return True
    elif pos == "sell" and (close[i] < bbands_lower[i] or close[i] > bbands_middle[i]):
        return True
    else:
        return False

def exit_test_signal(df, i, pos):
    close = df["close_M1"].values
    sma = df["sma_M1"].values

    if pos == "buy" and sma[i] > close[i]:
        return True
    elif pos == "sell" and  sma[i] < close[i]:
        return True
    return False

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
                return "sell", resistance_high[i]

        if high[i] < support_high[i] and low[i] > support_low[i] and support_high[i] < resistance_low[i]:
            zone_range = support_high[i] - support_low[i]

            high_range = high[i] - support_low[i]

            zone = high_range * 100 / zone_range

            if zone > 50:
                return "buy", support_low[i]
        
    return None, None

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