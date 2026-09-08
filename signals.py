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
    return "buy", None

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
    close = df["close_M15"].values

    if close[i] > support_low[i] and close[i] < support_high[i]:
        return "buy", support_low[i]
    elif close[i] > resistance_low[i] and close[i] < resistance_high[i]:
        return "sell", resistance_high[i]

    support_lows = []
    support_highs = []
    resistance_lows = []
    resistance_highs = []
    for j in range(i - 10, i):
        if not math.isnan(support_low[j]) and not math.isnan(support_high[j]):
            support_lows.append(support_low[j])
            support_highs.append(support_high[j])
        if not math.isnan(resistance_low[j]) and not math.isnan(resistance_high[j]):
            resistance_lows.append(resistance_low[j])
            resistance_highs.append(resistance_high[j])
    
    if len(support_lows) > 0 and len(support_highs) > 0:
        if close[i] > support_lows[-1] and close[i] < support_highs[-1]:
            return "buy", support_lows[-1]
    if len(resistance_lows) > 0 and len(resistance_highs) > 0:
        if close[i] > resistance_lows[-1] and close[i] < resistance_highs[-1]:
            return "sell", resistance_highs[-1]
        
    return None, None

def sr_exit(df, i, pos):
    support_high = df["support_high_H4"].values
    support_low = df["support_low_H4"].values
    resistance_high = df["resistance_high_H4"].values
    resistance_low = df["resistance_low_H4"].values
    close = df["close_M15"].values

    if pos == "buy":
        if (close[i] > resistance_low[i] and close[i] < resistance_high[i]) or close[i] < support_low[i]:
            return True
    elif pos == "sell":
        if (close[i] > support_low[i] and close[i] < support_high[i]) or close[i] > resistance_high[i]:
            return True
    return False