# -*- coding: utf-8 -*-
"""
build_app_data.py — 整合所有資料,產生 App 用的 data.js
內容: 趨勢判定 + 技術指標 + 基本面 + 財報倒數 + 相對大盤強弱 + 支撐壓力 + 量能 + 事件 + 新聞
"""
import json
import os
from datetime import datetime, date

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
APP = os.path.join(ROOT, "app")

INFO = {
    "NVDA": {"name": "NVIDIA", "sub": "科技/AI 晶片"},
    "GOOG": {"name": "Alphabet (Google)", "sub": "科技/雲端與廣告"},
    "LLY": {"name": "Eli Lilly 禮來", "sub": "醫療健康/製藥"},
}


def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def technicals(df, spx):
    c, h, l = df["Close"], df["High"], df["Low"]
    px = float(c.iloc[-1])
    ma20, ma60, ma120 = c.rolling(20).mean(), c.rolling(60).mean(), c.rolling(120).mean()
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    dn = (-d.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100 / (1 + up / dn)).iloc[-1])
    macd_line = _ema(c, 12) - _ema(c, 26)
    macd_hist = float((macd_line - _ema(macd_line, 9)).iloc[-1])
    sd = c.rolling(20).std()
    pb = float(((c - (ma20 - 2 * sd)) / (4 * sd)).iloc[-1])
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    up_m, dn_m = h.diff(), -l.diff()
    pdm = up_m.where((up_m > dn_m) & (up_m > 0), 0.0)
    ndm = dn_m.where((dn_m > up_m) & (dn_m > 0), 0.0)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    ndi = 100 * ndm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi)
    adx = float(dx.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    vol_ann = float(c.pct_change().rolling(20).std().iloc[-1]) * (252 ** 0.5) * 100
    m20, m60, m120 = float(ma20.iloc[-1]), float(ma60.iloc[-1]), float(ma120.iloc[-1])
    ma60_rising = float(ma60.iloc[-1]) > float(ma60.iloc[-6])

    # 相對大盤強弱 (RS): 個股報酬 - S&P500 報酬
    rs = {}
    for label, n in (("1m", 21), ("3m", 63)):
        rs[label] = round(float((c.iloc[-1] / c.iloc[-n - 1] - 1) - (spx.iloc[-1] / spx.iloc[-n - 1] - 1)) * 100, 1)

    # 支撐 / 壓力: 近 60 日最低 / 最高
    support = float(l.tail(60).min())
    resistance = float(h.tail(60).max())

    bull_stack = px > m20 > m60
    bear_stack = px < m20 < m60
    if adx >= 20 and bull_stack and ma60_rising:
        trend, term = "up", "上升趨勢"
        desc = ("多頭排列:股價({:,.0f})站上 20 日均線({:,.0f}),且 20 日均線高於 60 日均線({:,.0f}),"
                "60 日均線向上。ADX {:.0f} ≥ 20,趨勢明確。").format(px, m20, m60, adx)
    elif adx >= 20 and bear_stack and not ma60_rising:
        trend, term = "down", "下降趨勢"
        desc = ("空頭排列:股價({:,.0f})跌破 20 日均線({:,.0f}),且 20 日均線低於 60 日均線({:,.0f}),"
                "60 日均線向下。ADX {:.0f} ≥ 20,趨勢明確。").format(px, m20, m60, adx)
    else:
        trend, term = "range", "盤整(區間震盪)"
        why = "ADX {:.0f} < 20,趨勢強度不足".format(adx) if adx < 20 else "均線糾結,多空不明"
        desc = ("{}。股價在 20 日均線({:,.0f})與 60 日均線({:,.0f})之間徘徊,"
                "尚未形成方向,通常等待突破支撐或壓力後再確認。").format(why, m20, m60)

    def bias(b, s):
        return "bull" if b else ("bear" if s else "neutral")

    rsi_read = ("超買(>70,小心過熱)" if rsi > 70 else
                ("超賣(<30,可能反彈)" if rsi < 30 else
                 ("偏強" if rsi >= 55 else ("偏弱" if rsi <= 45 else "中性"))))
    inds = [
        {"key": "均線排列", "value": "20日 {:,.0f} / 60日 {:,.0f} / 120日 {:,.0f}".format(m20, m60, m120),
         "read": "多頭排列" if bull_stack else ("空頭排列" if bear_stack else "糾結"),
         "bias": bias(bull_stack, bear_stack)},
        {"key": "相對大盤強弱", "value": "1月 {:+.1f}% / 3月 {:+.1f}%".format(rs["1m"], rs["3m"]),
         "read": "強於大盤" if rs["1m"] > 1 else ("弱於大盤" if rs["1m"] < -1 else "與大盤同步"),
         "bias": bias(rs["1m"] > 1, rs["1m"] < -1)},
        {"key": "RSI (14)", "value": "{:.0f}".format(rsi), "read": rsi_read,
         "bias": "bull" if 55 <= rsi <= 70 else ("bear" if 30 <= rsi <= 45 else "neutral")},
        {"key": "MACD 柱狀", "value": "{:+.2f}".format(macd_hist),
         "read": "動能轉強" if macd_hist > 0 else "動能轉弱",
         "bias": bias(macd_hist > 0, macd_hist < 0)},
        {"key": "布林通道 %B", "value": "{:.2f}".format(pb),
         "read": "貼近上軌(強勢/略過熱)" if pb > 0.8 else ("貼近下軌(弱勢/略超跌)" if pb < 0.2 else "通道中段"),
         "bias": bias(pb > 0.8, pb < 0.2)},
        {"key": "ADX (14)", "value": "{:.0f}".format(adx),
         "read": "趨勢強" if adx >= 25 else ("趨勢成形中" if adx >= 20 else "無明顯趨勢(盤整)"),
         "bias": "neutral"},
        {"key": "年化波動率", "value": "{:.0f}%".format(vol_ann),
         "read": "高波動(風險大)" if vol_ann > 40 else ("中等波動" if vol_ann > 25 else "低波動"),
         "bias": "neutral"},
    ]
    return {"trend": trend, "trendTerm": term, "trendDesc": desc, "indicators": inds,
            "support": round(support, 2), "resistance": round(resistance, 2),
            "supportPct": round((support / px - 1) * 100, 1),
            "resistancePct": round((resistance / px - 1) * 100, 1)}


def fundamentals_card(f):
    def fmt(v, pct=False, x=False):
        if v is None:
            return "—"
        if pct:
            return "{:+.1f}%".format(v * 100)
        if x:
            return "{:.1f} 倍".format(v)
        return str(v)
    mc = f.get("marketCap")
    mc_s = "{:.2f} 兆美元".format(mc / 1e12) if mc and mc >= 1e12 else ("{:.0f} 億美元".format(mc / 1e8) if mc else "—")
    dy = f.get("dividendYield")
    dy_s = "{:.2f}%".format(dy) if dy is not None else "—"
    return [
        {"key": "市值", "value": mc_s},
        {"key": "本益比(近四季)", "value": fmt(f.get("trailingPE"), x=True)},
        {"key": "預估本益比", "value": fmt(f.get("forwardPE"), x=True)},
        {"key": "EPS 年增率", "value": fmt(f.get("earningsGrowth"), pct=True)},
        {"key": "營收年增率", "value": fmt(f.get("revenueGrowth"), pct=True)},
        {"key": "股息殖利率", "value": dy_s},
    ]


def plain_summary(t, df, tech, days_to_earnings):
    c = df["Close"]
    chg_1m = (c.iloc[-1] / c.iloc[-21] - 1) * 100
    chg_3m = (c.iloc[-1] / c.iloc[-63] - 1) * 100
    name = INFO[t]["name"]
    word = "上漲" if chg_1m > 2 else ("下跌" if chg_1m < -2 else "盤整")
    s = "{} 近一個月{}({:+.1f}%),近三個月 {:+.1f}%,目前判定為「{}」。".format(name, word, chg_1m, chg_3m, tech["trendTerm"])
    s += "支撐位約 {:,.0f}({:+.1f}%)、壓力位約 {:,.0f}({:+.1f}%)。".format(
        tech["support"], tech["supportPct"], tech["resistance"], tech["resistancePct"])
    if days_to_earnings is not None:
        s += " 距下次財報還有 {} 天,財報前後波動通常加大,請留意。".format(days_to_earnings)
    return s


def main():
    with open(os.path.join(PROC, "events.json"), encoding="utf-8") as fp:
        events = json.load(fp)
    with open(os.path.join(PROC, "fundamentals.json"), encoding="utf-8") as fp:
        funda = json.load(fp)
    spx_df = pd.read_csv(os.path.join(RAW, "GSPC.csv"), parse_dates=["Date"], index_col="Date")
    spx = spx_df["Close"]

    data = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "stocks": {}}
    for t, meta in INFO.items():
        df = pd.read_csv(os.path.join(RAW, t + ".csv"), parse_dates=["Date"], index_col="Date")
        tech = technicals(df, spx)
        f = funda["stocks"].get(t, {})
        ev = events["stocks"][t]
        tail = df.tail(180)
        spx_tail = spx.reindex(tail.index).ffill()
        spx_norm = (spx_tail / spx_tail.iloc[0] * float(tail["Close"].iloc[0])).round(2)
        d2e = None
        if f.get("nextEarnings"):
            try:
                d2e = (date.fromisoformat(f["nextEarnings"]) - date.today()).days
                if d2e < 0:
                    d2e = None
            except Exception:
                pass
        entry = dict(meta)
        entry.update(tech)
        entry.update({
            "dates": [x.strftime("%m/%d") for x in tail.index],
            "close": [round(float(x), 2) for x in tail["Close"]],
            "volume": [int(x) for x in tail["Volume"]],
            "spx": [float(x) for x in spx_norm],
            "fundamentals": fundamentals_card(f),
            "nextEarnings": f.get("nextEarnings"),
            "daysToEarnings": d2e,
            "summary": plain_summary(t, df, tech, d2e),
            "price_events": ev["price_events"],
            "news": ev["news"],
        })
        data["stocks"][t] = entry
    js = "window.APP_DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    os.makedirs(APP, exist_ok=True)
    with open(os.path.join(APP, "data.js"), "w", encoding="utf-8") as fp:
        fp.write(js)
    print("app/data.js updated ({})".format(data["updated"]))


if __name__ == "__main__":
    main()
