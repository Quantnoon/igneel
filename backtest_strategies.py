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
    prev_asian_low = prev_asian_low_rows.iloc[-1]
    current_asian_low = df["asian_low_M15"].iloc[i]
    current_asian_high = df["asian_high_M15"].iloc[i]
    current_close = df["close_M15"].iloc[i]


    is_asian = 0 <= hour < 8
    is_new_york = 13 <= hour < 22
    is_london = 8 <= hour < 16

    prev_asian_high_breakout_buy = current_close > prev_asian_high
    prev_asian_high_breakout_sell = current_close < prev_asian_low

    london_breakout = is_london and current_asian_high > prev_asian_high and current_close > current_asian_low

    if prev_asian_high_breakout_buy:
        return "buy", prev_asian_high, None
    elif prev_asian_high_breakout_sell:
        return "sell", prev_asian_low, None

    # print(asian_high[i], prev_asian_high)

    # print(df.head())

    # print(time[i])

    #     if df["close_M15"].values[i] > df["asian_high_M15"].values[i]:
    #         return "buy"
    #     elif df["close_M15"].values[i] < df["asian_low_M15"].values[i]:
    #         return "sell"
    return None, None, None

def session_breakout_exit(df, i, pos):
    hour = df["time"].dt.hour.iloc[i]
    is_asian = 0 <= hour < 8
    is_new_york = 13 <= hour < 22
    is_london = 8 <= hour < 16
    current_time = df["time"].iloc[i]
    
    current_day_start = current_time.normalize()

    prev_london_high_rows = df.loc[
        df["time"] < current_day_start,
        "london_high_M15"
    ].dropna()
    
    prev_newyork_high_rows = df.loc[
        df["time"] < current_day_start,
        "newyork_high_M15"
    ].dropna()

    if prev_london_high_rows.empty or prev_newyork_high_rows.empty:
        return False

    if pos == "buy":
        if is_asian and (df["close_M15"].values[i] >= prev_london_high_rows.iloc[-1] or df["close_M15"].values[i] >= prev_newyork_high_rows.iloc[-1]):
            return True
    elif pos == "sell":
        if df["close_M15"].values[i] > df["asian_low_M15"].values[i] or df["close_M15"].values[i] <= df["london_low_M15"].values[i] or df["close_M15"].values[i] <= df["newyork_low_M15"].values[i]:
            return True
    return False