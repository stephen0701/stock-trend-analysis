"""Require the latest completed US equity session, including holidays and DST."""
import pandas as pd
import pandas_market_calendars as mcal


def expected_session(now=None):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    schedule = mcal.get_calendar("NYSE").schedule(
        start_date=(now - pd.Timedelta(days=30)).date(), end_date=now.date())
    completed = schedule.loc[schedule.market_close <= now]
    if completed.empty:
        raise ValueError("No completed trading session found")
    return completed.index[-1].strftime("%Y-%m-%d")


def require_session(frame, expected):
    actual = frame.index[-1].strftime("%Y-%m-%d")
    if actual != expected:
        raise ValueError(f"Expected completed session {expected}, received {actual}")
