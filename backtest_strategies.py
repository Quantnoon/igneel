def sr_entry(df, i):
    support_high = df["support_high_H4"].values
    support_low = df["support_low_H4"].values
    resistance_high = df["resistance_high_H4"].values
    resistance_low = df["resistance_low_H4"].values
    close = df["close_M15"].values

    if close[i] > support_low[i] and close[i] < support_high[i]:
        return "buy"
    elif close[i] > resistance_low[i] and close[i] < resistance_high[i]:
        return "sell"
    return None

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

def session_breakout_entry(df, i):
    hour = df["time"].dt.hour.iloc[i]

    if 8 <= hour < 16:
        if df["close_M15"].values[i] > df["asian_high_M15"].values[i]:
            return "buy"
        elif df["close_M15"].values[i] < df["asian_low_M15"].values[i]:
            return "sell"
    return None

def session_breakout_exit(df, i, pos):
    if pos == "buy":
        if df["close_M15"].values[i] < df["asian_high_M15"].values[i] or df["close_M15"].values[i] >= df["london_high_M15"].values[i] or df["close_M15"].values[i] >= df["newyork_high_M15"].values[i]:
            return True
    elif pos == "sell":
        if df["close_M15"].values[i] > df["asian_low_M15"].values[i] or df["close_M15"].values[i] <= df["london_low_M15"].values[i] or df["close_M15"].values[i] <= df["newyork_low_M15"].values[i]:
            return True
    return False