# -*- coding: utf-8 -*-
"""
fetch_fundamentals.py — 基本面與下次財報日
來源: yfinance Ticker.info / Ticker.calendar
輸出: data/processed/fundamentals.json
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
WATCHLIST = ["NVDA", "GOOG", "LLY", "DRAM"]
KEYS = ["trailingPE", "forwardPE", "earningsGrowth", "revenueGrowth", "dividendYield", "marketCap"]


def one(ticker):
    import yfinance as yf
    t = yf.Ticker(ticker)
    info = {}
    try:
        raw = t.info or {}
        info = {k: raw.get(k) for k in KEYS}
    except Exception as e:
        print("[{}] info failed: {}".format(ticker, e))
    earnings = None
    try:
        cal = t.calendar or {}
        dates = cal.get("Earnings Date") or []
        if dates:
            earnings = str(dates[0])
    except Exception as e:
        print("[{}] calendar failed: {}".format(ticker, e))
    info["nextEarnings"] = earnings
    return info


def main():
    os.makedirs(OUT, exist_ok=True)
    out = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "stocks": {t: one(t) for t in WATCHLIST}}
    with open(os.path.join(OUT, "fundamentals.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    for t, v in out["stocks"].items():
        print("[{}] PE={} nextEarnings={}".format(t, v.get("trailingPE"), v.get("nextEarnings")))
    print("fundamentals.json updated")


if __name__ == "__main__":
    main()
