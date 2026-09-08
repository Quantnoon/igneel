import pandas as pd

def sr_entry(df, i):
    support_high = df["support_high_H4"].values
    support_low = df["support_low_H4"].values
    resistance_high = df["resistance_high_H4"].values
    resistance_low = df["resistance_low_H4"].values
    close = df["close_M15"].values

    if close[i] > support_low[i] and close[i] < support_high[i]:
        return "buy", support_low[i], None
    elif close[i] > resistance_low[i] and close[i] < resistance_high[i]:
        return "sell", resistance_high[i], None
    return None, None, None

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
    time = df["time"].values
    asian_high = df["asian_high_M15"].values

    current_time = df["time"].iloc[i]

    current_day_start = current_time.normalize()

    prev_asian_high_rows = df.loc[
        df["time"] < current_day_start,
        "asian_high_M15"
    ].dropna()

    prev_asian_low_rows = df.loc[
        df["time"] < current_day_start,
        "asian_low_M15"
    ].dropna()

    if prev_asian_high_rows.empty or prev_asian_low_rows.empty:
        return None, None, None

    prev_asian_high = prev_asian_high_rows.iloc[-1]
    current_asian_low = df["asian_low_M15"].iloc[i]
    current_asian_high = df["asian_high_M15"].iloc[i]
    current_close = df["close_M15"].iloc[i]

    if 8 <= hour < 16 and current_asian_high > prev_asian_high and current_close > current_asian_low:
        return "buy", current_asian_low, None

    # print(asian_high[i], prev_asian_high)

    # print(df.head())

    # print(time[i])

    #     if df["close_M15"].values[i] > df["asian_high_M15"].values[i]:
    #         return "buy"
    #     elif df["close_M15"].values[i] < df["asian_low_M15"].values[i]:
    #         return "sell"
    return None, None, None

def session_breakout_exit(df, i, pos):
    if pos == "buy":
        if df["close_M15"].values[i] >= df["london_high_M15"].values[i] or df["close_M15"].values[i] >= df["newyork_high_M15"].values[i]:
            return True
    elif pos == "sell":
        if df["close_M15"].values[i] > df["asian_low_M15"].values[i] or df["close_M15"].values[i] <= df["london_low_M15"].values[i] or df["close_M15"].values[i] <= df["newyork_low_M15"].values[i]:
            return True
    return False