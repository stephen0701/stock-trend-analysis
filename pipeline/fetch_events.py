# -*- coding: utf-8 -*-
"""
fetch_events.py — 重大波動日偵測 + 新聞(含關鍵字多空判讀)
輸出: data/processed/events.json

新聞判讀為免費關鍵字規則,標示 偏正面/偏負面/中性 與原因分類,準確度有限僅供參考。
"""
import json
import os
import re
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")
WATCHLIST = ["NVDA", "GOOG", "LLY", "DRAM"]
LOOKBACK_DAYS = 504
MOVE_THRESHOLD = 0.04

# (類別關鍵字, 中文原因, 方向)  由上往下找,先中先贏
RULES = [
    (r"beats|tops estimate|exceeds|better.than.expected|blowout|record (revenue|profit|sales)|strong (results|earnings|quarter)", "財報或業績優於預期", "pos"),
    (r"raises (guidance|outlook|forecast)|hikes dividend|buyback|raises price target|upgrade", "展望調升或分析師看好", "pos"),
    (r"misses|falls short|disappoint|weak (results|guidance|demand)|cuts (guidance|outlook|forecast)", "業績或展望不如預期", "neg"),
    (r"downgrade|cuts price target|sell rating|bearish", "分析師調降評等或看空", "neg"),
    (r"lawsuit|probe|investigation|antitrust|regulator|fine|recall|fraud", "法律或監管風險", "neg"),
    (r"layoffs|halts|delay|shortage|tariff|export (curb|ban|restriction)", "營運或政策負面消息", "neg"),
    (r"partnership|deal|contract|wins|launch|unveil|new (chip|drug|product)|approval|breakthrough|expands", "新產品、合作案或獲准消息", "pos"),
    (r"surge|soars|jumps|rallies|rallied|all.time high|record high|hits high", "股價強勢上攻", "pos"),
    (r"falls|drops|plunge|sinks|slumps|tumbles|slides|selloff", "股價走弱或遭拋售", "neg"),
    (r"buy now|top pick|best stock|bull case|why .* (could|will) (rise|soar)", "媒體看多評論", "pos"),
]
SENT_LABEL = {"pos": "偏正面", "neg": "偏負面", "neu": "中性"}


def classify(text):
    t = text.lower()
    for pat, reason, sent in RULES:
        if re.search(pat, t):
            return sent, reason
    return "neu", "一般報導,無明顯多空訊息"


def price_events(ticker):
    df = pd.read_csv(os.path.join(RAW, ticker + ".csv"), parse_dates=["Date"], index_col="Date")
    df = df.tail(LOOKBACK_DAYS)
    ret = df["Close"].pct_change()
    sigma = ret.std()
    big = ret[(ret.abs() >= MOVE_THRESHOLD) | (ret.abs() >= 3 * sigma)]
    events = []
    for d, r in big.tail(12).items():
        events.append({
            "date": d.strftime("%Y-%m-%d"),
            "type": "price",
            "pct": round(float(r) * 100, 1),
            "title": "單日{} {:.1f}%".format("大漲" if r > 0 else "大跌", abs(r) * 100),
        })
    return events


def news_items(ticker):
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items = []
    for it in raw[:8]:
        c = it.get("content", it)
        if not c.get("title"):
            continue
        url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
        summary = (c.get("summary") or c.get("description") or "").strip()
        sent, reason = classify(c.get("title", "") + " " + summary)
        items.append({
            "title": c.get("title"),
            "sent": sent,
            "sentLabel": SENT_LABEL[sent],
            "reason": reason,
            "date": (c.get("pubDate") or "")[:10],
            "url": url,
            "publisher": (c.get("provider") or {}).get("displayName", ""),
        })
    return items


def main():
    os.makedirs(OUT, exist_ok=True)
    out = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "stocks": {}}
    for t in WATCHLIST:
        out["stocks"][t] = {"price_events": price_events(t), "news": news_items(t)}
        ns = out["stocks"][t]["news"]
        print("[{}] events {} / news {} (pos {} / neg {} / neu {})".format(
            t, len(out["stocks"][t]["price_events"]), len(ns),
            sum(1 for n in ns if n["sent"] == "pos"),
            sum(1 for n in ns if n["sent"] == "neg"),
            sum(1 for n in ns if n["sent"] == "neu")))
    with open(os.path.join(OUT, "events.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print("events.json updated")


if __name__ == "__main__":
    main()
