# -*- coding: utf-8 -*-
"""
fetch_prices.py — 抓取追蹤清單 + 大盤(S&P 500)歷史日線
輸出: data/raw/<TICKER>.csv
"""
import os
import sys
from datetime import date

import pandas as pd

WATCHLIST = ["NVDA", "GOOG", "LLY"]
BENCHMARK = "^GSPC"            # S&P 500,存成 GSPC.csv
START = "2005-01-01"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")


def fetch_yfinance(ticker):
    import yfinance as yf
    df = yf.download(ticker, start=START, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("yfinance empty")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].round(4)
    df.index.name = "Date"
    return df


def fetch_stooq(ticker):
    sym = "^spx" if ticker == "^GSPC" else ticker.lower() + ".us"
    url = "https://stooq.com/q/d/l/?s={}&i=d".format(sym)
    df = pd.read_csv(url, parse_dates=["Date"], index_col="Date")
    if df.empty:
        raise RuntimeError("stooq empty")
    df = df[df.index >= START]
    if "Volume" not in df.columns:
        df["Volume"] = 0
    return df[["Open", "High", "Low", "Close", "Volume"]].round(4)


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    ok = True
    for t in WATCHLIST + [BENCHMARK]:
        fname = t.replace("^", "") + ".csv"
        try:
            try:
                df, src = fetch_yfinance(t), "yfinance"
            except Exception as e:
                print("[{}] yfinance failed ({}), trying stooq...".format(t, e))
                df, src = fetch_stooq(t), "stooq"
            path = os.path.join(RAW_DIR, fname)
            df.to_csv(path)
            print("[{}] OK ({}) {} rows {} ~ {}".format(t, src, len(df), df.index[0].date(), df.index[-1].date()))
        except Exception as e:
            ok = False
            print("[{}] FAILED: {}".format(t, e), file=sys.stderr)
    print("done", date.today(), "" if ok else "(with errors)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
