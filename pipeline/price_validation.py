"""Validate daily quotes without inventing prices or dropping missing sessions."""
import numpy as np
import pandas as pd

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

def normalize(df):
    if df is None or df.empty:
        raise ValueError("empty price response")
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index, errors="raise")
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    if df.index.isna().any() or df.index.has_duplicates:
        raise ValueError("invalid or duplicate trading dates")
    df.index.name = "Date"
    return df.sort_index()

def validate_prices(df):
    df = normalize(df)[COLUMNS].apply(pd.to_numeric, errors="coerce")
    valid = np.isfinite(df).all(axis=1)
    valid &= (df[COLUMNS[:4]] > 0).all(axis=1) & (df.Volume >= 0)
    valid &= df.High >= df[["Open", "Close", "Low"]].max(axis=1)
    valid &= df.Low <= df[["Open", "Close", "High"]].min(axis=1)
    if not valid.all():
        raise ValueError("invalid prices on " + ", ".join(df.index[~valid].strftime("%Y-%m-%d")[:5]))
    return df

def read_prices(path):
    return validate_prices(pd.read_csv(path, index_col="Date"))
