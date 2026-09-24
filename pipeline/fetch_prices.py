# -*- coding: utf-8 -*-
"""
fetch_prices.py — 抓取追蹤清單 + 大盤(S&P 500)歷史日線
輸出: data/raw/<TICKER>.csv
"""
import os
import sys
import argparse
import json
from pathlib import Path
import tempfile
from datetime import date

import pandas as pd
import numpy as np
from price_validation import COLUMNS, normalize, validate_prices
from yahoo_history import restore_history


def repair_yahoo_history(history, latest, metadata, now=None, records=None):
    """Replace only the SAME completed session with its actual daily OHLCV."""
    history, latest = normalize(history), normalize(latest)
    if history.index[-1] != latest.index[-1]:
        raise ValueError("Yahoo history and single-day response dates differ")
    regular = metadata.get("currentTradingPeriod", {}).get("regular", {})
    end, tz = regular.get("end"), metadata.get("exchangeTimezoneName")
    if not end or not tz:
        raise ValueError("Yahoo session metadata missing")
    end = (pd.Timestamp(end, unit="s", tz="UTC") if isinstance(end, (int, float))
           else pd.Timestamp(end))
    if end.tzinfo is None:
        raise ValueError("Session end has no timezone")
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    bar_date = latest.index[-1].date()
    session_date = end.tz_convert(tz).date()
    if bar_date > session_date or (bar_date == session_date and now < end):
        raise ValueError("Latest session has not closed")
    if (now.tz_convert(tz).date() - bar_date).days > 7:
        raise ValueError("Latest session is more than seven days old")
    validate_prices(latest)
    adj = pd.to_numeric(latest["Adj Close"], errors="coerce")
    if not np.isfinite(adj).all() or not (adj > 0).all():
        raise ValueError("Single-day adjusted close is missing")
    cols = COLUMNS + ["Adj Close"]
    history.loc[latest.index[-1], cols] = latest.iloc[-1][cols]
    if records:
        history = restore_history(history, records)
    raw = validate_prices(history)
    ratio = pd.to_numeric(history["Adj Close"], errors="coerce") / raw.Close
    if not np.isfinite(ratio).all() or not (ratio > 0).all():
        raise ValueError("Historical adjusted close is invalid")
    raw[COLUMNS[:4]] = raw[COLUMNS[:4]].mul(ratio, axis=0)
    return validate_prices(raw).round(4)

WATCHLIST = ["NVDA", "GOOG", "LLY", "DRAM"]
BENCHMARK = "^GSPC"            # S&P 500,存成 GSPC.csv
START = "2005-01-01"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")


def fetch_yfinance(ticker, verified=None):
    import yfinance as yf
    history = yf.download(ticker, start=START, auto_adjust=False, keepna=True, actions=True,
                          progress=False, timeout=20)
    obj = yf.Ticker(ticker)
    latest = obj.history(period="1d", auto_adjust=False, actions=False,
                         keepna=True, timeout=20)
    records = verified.get(ticker, {}) if verified is not None else {}
    result = repair_yahoo_history(history, latest, obj.get_history_metadata(), records=records)
    if verified is not None:
        raw = normalize(latest)
        verified.setdefault(ticker, {})[raw.index[-1].strftime("%Y-%m-%d")] = {
            col: float(raw.iloc[-1][col]) for col in COLUMNS}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["yahoo", "tiingo"], default="yahoo")
    parser.add_argument("--output-dir", type=Path, default=Path(RAW_DIR))
    args = parser.parse_args()
    seed = Path(ROOT) / "data" / "yahoo_verified_seed.json"
    verified = json.loads(seed.read_text(encoding="utf-8")) if seed.exists() else {}
    cache_path = args.output_dir / ".cache" / "yahoo_verified.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        for ticker, records in cached.items():
            verified.setdefault(ticker, {}).update(records)
    results, status = {}, {}
    for ticker in WATCHLIST + [BENCHMARK]:
        source = "yahoo" if ticker == BENCHMARK else args.provider
        if source == "tiingo":
            from tiingo_prices import fetch_tiingo
            df = fetch_tiingo(ticker, START)
        else:
            df = fetch_yfinance(ticker, verified)
        df = validate_prices(df)
        if len(df) < 65:
            raise ValueError(f"{ticker}: insufficient history")
        name = ticker.replace("^", "")
        results[name] = df
        status[name] = {"source":source, "priceDate":df.index[-1].strftime("%Y-%m-%d")}
        print(f"[{ticker}] {source}: {len(df)} rows; latest {status[name]['priceDate']}")
    if len({s["priceDate"] for s in status.values()}) != 1:
        raise ValueError("Stocks and benchmark have different latest dates; no files replaced")
    cache_json = json.dumps(verified, allow_nan=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output_dir) as tmp:
        tmp = Path(tmp)
        for name, df in results.items():
            df.to_csv(tmp / (name + ".csv"))
        (tmp / "price_status.json").write_text(json.dumps(status, allow_nan=False), encoding="utf-8")
        for path in tmp.iterdir():
            os.replace(path, args.output_dir / path.name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_tmp = cache_path.with_suffix(".tmp")
    cache_tmp.write_text(cache_json, encoding="utf-8")
    os.replace(cache_tmp, cache_path)
    print("done", date.today())


if __name__ == "__main__":
    main()
