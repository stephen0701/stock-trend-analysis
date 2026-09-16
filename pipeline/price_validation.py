"""Validate prices before saving or using them; never fabricate missing quotes."""
import numpy as np
import pandas as pd


def validate_prices(df, source="prices"):
    columns = ["Open", "High", "Low", "Close", "Volume"]
    if df is None or df.empty or not set(columns).issubset(df.columns):
        raise ValueError(f"{source}: empty prices or missing OHLCV columns")
    df = df[columns].copy()
    df.index = pd.to_datetime(df.index, errors="coerce")
    if df.index.isna().any() or df.index.has_duplicates:
        raise ValueError(f"{source}: invalid or duplicate dates")
    df = df.sort_index()
    df = df.apply(pd.to_numeric, errors="coerce")
    valid = np.isfinite(df).all(axis=1)
    valid &= (df[columns[:4]] > 0).all(axis=1) & (df.Volume >= 0)
    valid &= (df.High >= df[["Open", "Close", "Low"]].max(axis=1))
    valid &= (df.Low <= df[["Open", "Close", "High"]].min(axis=1))
    if not valid.all():
        dates = df.index[~valid].strftime("%Y-%m-%d").tolist()
        raise ValueError(f"{source}: invalid OHLCV rows: {dates[:5]}")
    df.index.name = "Date"
    return df


def read_prices(path):
    return validate_prices(pd.read_csv(path, index_col="Date"), str(path))
