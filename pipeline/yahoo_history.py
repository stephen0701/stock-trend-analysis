"""Restore a missing historical close from a verified SAME-DATE Yahoo daily bar."""
import numpy as np
import pandas as pd
from price_validation import COLUMNS, normalize, validate_prices

def restore_history(history, records):
    history = normalize(history)
    # Raw Yahoo OHLC is split adjusted. Retain all finite fresh source values.
    for day in history.index[:-1]:
        if pd.notna(history.at[day, "Close"]):
            continue
        record = records.get(day.strftime("%Y-%m-%d"))
        if record is None:
            continue
        saved = pd.DataFrame([record], index=[day])
        validate_prices(saved)
        if "Stock Splits" not in history:
            raise ValueError("Split events are required for historical repair")
        splits = history.loc[history.index > day, "Stock Splits"].astype(float)
        if not np.isfinite(splits).all() or (splits < 0).any():
            raise ValueError("Invalid split events")
        split_factor = float(splits[splits != 0].prod())
        scale = 1 / split_factor
        anchors = ["Open", "High", "Low"]
        # Check any intact prices against split-adjusted verified raw prices.
        for col in anchors:
            value = history.at[day, col]
            if pd.notna(value) and not np.isclose(value, record[col] * scale, rtol=2e-6, atol=0):
                raise ValueError(f"{day.date()}: cached and current OHLC disagree")
        empty_bar = history.loc[day, anchors + ["Close"]].isna().all()
        for col in anchors + ["Close"]:
            if pd.isna(history.at[day, col]):
                history.at[day, col] = float(record[col]) * scale
        if pd.isna(history.at[day, "Volume"]) or (empty_bar and history.at[day, "Volume"] == 0):
            history.at[day, "Volume"] = float(record["Volume"]) * split_factor
        print(f"Restored verified Yahoo close for {day.date()}")

    # Recompute only missing adjustment factors from current Yahoo factors and
    # distributions. Never carry yesterday's adjusted price across an ex-date.
    for i in range(len(history)-2, -1, -1):
        day, after = history.index[i], history.index[i+1]
        if pd.notna(history.at[day, "Adj Close"]):
            continue
        if day.strftime("%Y-%m-%d") not in records:
            continue
        close = history.at[day, "Close"]
        next_close, next_adj = history.at[after, "Close"], history.at[after, "Adj Close"]
        if not np.isfinite([close, next_close, next_adj]).all() or min(close, next_close, next_adj) <= 0:
            continue
        if "Dividends" not in history:
            raise ValueError("Corporate-action data is required for historical repair")
        dividend = history.at[after, "Dividends"]
        capital_gain = history.at[after, "Capital Gains"] if "Capital Gains" in history else 0
        distribution = dividend + capital_gain
        if not np.isfinite(distribution) or distribution < 0 or distribution >= close:
            raise ValueError("Invalid distribution while restoring historical adjustment")
        history.at[day, "Adj Close"] = close * (next_adj / next_close) * (1 - distribution / close)
    return history
