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


def prepare_download(df, source="prices", today=None):
    """Only omit up to three trailing incomplete sessions, never interior corruption."""
    columns = ["Open", "High", "Low", "Close", "Volume"]
    if df is None or df.empty or not set(columns).issubset(df.columns):
        return validate_prices(df, source)
    df = df[columns].copy()
    df.index = pd.to_datetime(df.index, errors="coerce")
    if df.index.isna().any() or df.index.has_duplicates:
        raise ValueError(f"{source}: invalid or duplicate dates")
    df = df.sort_index().apply(pd.to_numeric, errors="coerce")
    complete = np.isfinite(df).all(axis=1)
    missing_dates = []
    while len(df) and not complete.iloc[len(df)-1]:
        missing_dates.insert(0, df.index[-1].strftime("%Y-%m-%d"))
        df = df.iloc[:-1]
    if len(missing_dates) > 3:
        raise ValueError(f"{source}: too many incomplete sessions")
    result = validate_prices(df, source)
    today = pd.Timestamp(today or pd.Timestamp.now(tz="America/New_York").date())
    age = (today.date() - result.index[-1].date()).days
    if age < 0 or age > 7:
        raise ValueError(f"{source}: latest valid session is not recent: {result.index[-1]}")
    result.attrs["missingDates"] = missing_dates
    return result
