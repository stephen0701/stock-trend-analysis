# -*- coding: utf-8 -*-
"""
fetch_prices.py — 抓取追蹤清單 + 大盤(S&P 500)歷史日線
輸出: data/raw/<TICKER>.csv
"""
import os
import sys
import json
import time
from io import StringIO
from urllib.request import Request, urlopen
from datetime import date

import pandas as pd
from price_validation import prepare_download

WATCHLIST = ["NVDA", "GOOG", "LLY", "DRAM"]
BENCHMARK = "^GSPC"            # S&P 500,存成 GSPC.csv
START = "2005-01-01"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")


def fetch_yfinance(ticker):
    import yfinance as yf
    df = yf.download(ticker, start=START, auto_adjust=True, progress=False, timeout=20)
    if df is None or df.empty:
        raise RuntimeError("yfinance empty")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].round(4)
    df.index.name = "Date"
    return prepare_download(df, ticker)


def fetch_stooq(ticker):
    sym = "^spx" if ticker == "^GSPC" else ticker.lower() + ".us"
    url = "https://stooq.com/q/d/l/?s={}&i=d".format(sym)
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
        csv = response.read().decode("utf-8-sig")
    df = pd.read_csv(StringIO(csv), parse_dates=["Date"], index_col="Date")
    if df.empty:
        raise RuntimeError("stooq empty")
    df = df[df.index >= START]
    if "Volume" not in df.columns:
        df["Volume"] = 0
    return prepare_download(df[["Open", "High", "Low", "Close", "Volume"]].round(4), ticker)


def fetch_best(ticker):
    candidates = []
    for attempt in range(3):
        try:
            df = fetch_yfinance(ticker)
            candidates.append((df, "yfinance"))
            if not df.attrs.get("missingDates"):
                return df, "yfinance"
            print(f"[{ticker}] incomplete sessions {df.attrs['missingDates']}; retrying")
        except Exception as exc:
            print(f"[{ticker}] Yahoo attempt {attempt + 1}: {exc}")
        if attempt < 2:
            time.sleep(2 ** attempt)
    try:
        candidates.append((fetch_stooq(ticker), "stooq"))
    except Exception as exc:
        print(f"[{ticker}] Stooq unavailable: {exc}")
    if not candidates:
        raise RuntimeError("No valid recent prices from either source")
    # Prefer the freshest valid session, not an older backup result.
    return max(candidates, key=lambda item: item[0].index[-1])


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    ok, status = True, {}
    for t in WATCHLIST + [BENCHMARK]:
        fname = t.replace("^", "") + ".csv"
        try:
            df, src = fetch_best(t)
            path = os.path.join(RAW_DIR, fname)
            df.to_csv(path + ".tmp")
            os.replace(path + ".tmp", path)
            status[t.replace("^", "")] = {
                "source": src, "missingDates": df.attrs.get("missingDates", []),
                "priceDate": df.index[-1].strftime("%Y-%m-%d")}
            print("[{}] OK ({}) {} rows {} ~ {}".format(t, src, len(df), df.index[0].date(), df.index[-1].date()))
        except Exception as e:
            ok = False
            print("[{}] FAILED: {}".format(t, e), file=sys.stderr)
    if ok:
        path = os.path.join(RAW_DIR, "price_status.json")
        with open(path + ".tmp", "w", encoding="utf-8") as fp:
            json.dump(status, fp, ensure_ascii=False, allow_nan=False)
        os.replace(path + ".tmp", path)
    print("done", date.today(), "" if ok else "(with errors)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
