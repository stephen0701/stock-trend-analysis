# -*- coding: utf-8 -*-
"""
build_app_data.py — 整合所有資料,產生 App 用的 data.js
內容: 趨勢判定 + 轉換點 + 訊號彙整 + 技術指標 + 基本面 + 財報倒數
       + 相對大盤強弱 + 支撐壓力 + 多時間維度走勢 + 事件 + 新聞
"""
import json
import os
from datetime import datetime, date, timezone, timedelta

import numpy as np
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
CHART_DAYS = 1260   # 約 5 年日線,前端依時間維度切片


def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def adx_series(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    up_m, dn_m = h.diff(), -l.diff()
    pdm = up_m.where((up_m > dn_m) & (up_m > 0), 0.0)
    ndm = dn_m.where((dn_m > up_m) & (dn_m > 0), 0.0)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / atr
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def trend_label(px, m20, m60, m60_rising, adx):
    """單日趨勢判定,回傳 up/down/range"""
    if adx >= 20 and px > m20 > m60 and m60_rising:
        return "up"
    if adx >= 20 and px < m20 < m60 and not m60_rising:
        return "down"
    return "range"


def trend_series(df):
    """逐日計算歷史趨勢標籤(用於找轉換點)"""
    c = df["Close"]
    m20, m60 = c.rolling(20).mean(), c.rolling(60).mean()
    adx = adx_series(df)
    m60_rising = m60 > m60.shift(5)
    labels = []
    for i in range(len(c)):
        if i < 60 or pd.isna(adx.iloc[i]):
            labels.append(None)
        else:
            labels.append(trend_label(c.iloc[i], m20.iloc[i], m60.iloc[i],
                                       bool(m60_rising.iloc[i]), adx.iloc[i]))
    return pd.Series(labels, index=c.index)


TERM = {"up": "上升趨勢", "down": "下降趨勢", "range": "盤整(區間震盪)"}

# 六種轉折點的說明(技術派解讀 + 偏向 + 風險提醒)
TRANSITION = {
    ("range", "up"): {"icon": "📈", "tag": "偏多訊號",
        "text": "由盤整轉為上升:股價結束橫盤、站上均線。技術派視為偏多,順勢者常在此階段留意進場。但轉折確認有延遲,現價未必是低點;也可能是假突破,幾天後跌回盤整。"},
    ("up", "range"): {"icon": "⏸", "tag": "漲勢暫歇",
        "text": "由上升轉為盤整:上漲動能減弱、開始橫盤。技術派視為漲勢暫歇,持有者可考慮部分獲利了結或設好停利。注意:可能只是中途休息,不一定是反轉。"},
    ("up", "down"): {"icon": "📉", "tag": "賣出/避險訊號",
        "text": "由上升轉為下降:跌破均線、空頭排列成形。技術派視為趨勢反轉向下,是減碼或出場的重要警訊,尤其用來保護既有獲利。偶爾為急跌後假摔隨即反彈。"},
    ("down", "range"): {"icon": "⏸", "tag": "跌勢止穩",
        "text": "由下降轉為盤整:跌勢停止、開始橫盤,可能在打底。技術派視為跌勢暫歇但尚未轉多,通常觀望等方向。注意:盤整後可能再續跌,不代表落底。"},
    ("down", "up"): {"icon": "📈", "tag": "反轉偏多訊號",
        "text": "由下降轉為上升:趨勢反轉向上。技術派視為強烈偏多訊號。但這種 V 轉相對少見且容易失敗,假訊號比例高,建議等站穩幾天再確認。"},
    ("range", "down"): {"icon": "📉", "tag": "轉弱訊號",
        "text": "由盤整轉為下降:橫盤後跌破支撐、空頭成形。技術派視為偏空,提醒避免進場或考慮減碼。同樣可能為假跌破,隨後拉回盤整。"},
}


def transition_detail(last_change):
    if not last_change:
        return None
    key = (last_change["from"], last_change["to"])
    info = TRANSITION.get(key)
    if not info:
        return None
    return {"icon": info["icon"], "tag": info["tag"], "text": info["text"],
            "date": last_change["date"]}


def regime_info(df):
    """轉換點三層: 歷史轉換點 / 目前狀態維持天數+轉換日 / 確認中提示"""
    ts = trend_series(df).dropna()
    if ts.empty:
        return {}
    # 歷史轉換點(最近 5 年內)
    changes = []
    prev = None
    for d, lab in ts.items():
        if prev is not None and lab != prev:
            changes.append({"date": d.strftime("%Y-%m-%d"),
                            "from": prev, "to": lab,
                            "fromTerm": TERM[prev], "toTerm": TERM[lab]})
        prev = lab
    cur = ts.iloc[-1]
    # 目前狀態從哪天開始
    since = ts.index[-1]
    for d in reversed(ts.index):
        if ts[d] == cur:
            since = d
        else:
            break
    held_days = int((ts.index[-1] - since).days)
    held_bars = int((ts.index >= since).sum())
    last_change = changes[-1] if changes else None

    # 確認中提示: 目前盤整,但股價剛突破近20日壓力 / 跌破支撐
    c = df["Close"]
    h, l = df["High"], df["Low"]
    px = float(c.iloc[-1])
    res20 = float(h.iloc[-21:-1].max())
    sup20 = float(l.iloc[-21:-1].min())
    pending = None
    if cur == "range":
        if px > res20:
            pending = {"dir": "up", "text": "觀察中:股價剛突破近 20 日高點,可能轉為上升趨勢,但趨勢強度尚未確認(可能為假突破)"}
        elif px < sup20:
            pending = {"dir": "down", "text": "觀察中:股價剛跌破近 20 日低點,可能轉為下降趨勢,但尚未確認(可能為假跌破)"}
    return {
        "current": cur,
        "sinceDate": since.strftime("%Y-%m-%d"),
        "heldDays": held_days,
        "heldBars": held_bars,
        "lastChange": last_change,
        "transitionDetail": transition_detail(last_change),
        "changes": changes[-30:],   # 近 30 次轉換,給圖標記用
        "pending": pending,
    }


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
    adx = float(adx_series(df).iloc[-1])
    vol_ann = float(c.pct_change().rolling(20).std().iloc[-1]) * (252 ** 0.5) * 100
    m20, m60, m120 = float(ma20.iloc[-1]), float(ma60.iloc[-1]), float(ma120.iloc[-1])
    ma60_rising = m60 > float(ma60.iloc[-6])

    rs = {}
    for label, n in (("1m", 21), ("3m", 63)):
        rs[label] = round(float((c.iloc[-1] / c.iloc[-n - 1] - 1) - (spx.iloc[-1] / spx.iloc[-n - 1] - 1)) * 100, 1)

    support = float(l.tail(60).min())
    resistance = float(h.tail(60).max())

    trend = trend_label(px, m20, m60, ma60_rising, adx)
    term = TERM[trend]
    if trend == "up":
        desc = ("多頭排列:股價({:,.0f})站上 20 日均線({:,.0f}),且 20 日均線高於 60 日均線({:,.0f}),"
                "60 日均線向上。ADX {:.0f} ≥ 20,趨勢明確。").format(px, m20, m60, adx)
    elif trend == "down":
        desc = ("空頭排列:股價({:,.0f})跌破 20 日均線({:,.0f}),且 20 日均線低於 60 日均線({:,.0f}),"
                "60 日均線向下。ADX {:.0f} ≥ 20,趨勢明確。").format(px, m20, m60, adx)
    else:
        why = "ADX {:.0f} < 20,趨勢強度不足".format(adx) if adx < 20 else "均線糾結,多空不明"
        desc = ("{}。股價在 20 日均線({:,.0f})與 60 日均線({:,.0f})之間徘徊,"
                "尚未形成方向,通常等待突破支撐或壓力後再確認。").format(why, m20, m60)

    def bias(b, s):
        return "bull" if b else ("bear" if s else "neutral")

    bull_stack = px > m20 > m60
    bear_stack = px < m20 < m60
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
    # 訊號彙整
    bull = sum(1 for i in inds if i["bias"] == "bull")
    bear = sum(1 for i in inds if i["bias"] == "bear")
    neu = len(inds) - bull - bear
    if bull >= bear + 2:
        verdict = "多方訊號較一致,順勢者可留意支撐位附近的進場機會。"
    elif bear >= bull + 2:
        verdict = "空方訊號較一致,持有者留意風險,逢反彈至壓力位可考慮減碼。"
    else:
        verdict = "多空訊號拉鋸、方向不明朗,觀望為宜,等待趨勢明確再行動。"
    signals = {"bull": bull, "bear": bear, "neutral": neu, "verdict": verdict}

    # 兩步驟操作法: 趨勢 + 訊號共識
    if trend == "up" and bull >= bear + 2:
        action = {"level": "buy", "label": "留意買進",
                  "text": "趨勢為上升,且訊號多數偏多——兩個條件同向。順勢者可留意進場,但別追高,建議等股價回到支撐位附近再分批進,並設好停損(跌破支撐就出場)。"}
    elif trend == "down" and bear >= bull + 2:
        action = {"level": "sell", "label": "留意減碼",
                  "text": "趨勢為下降,且訊號多數偏空——兩個條件同向。持有者宜留意風險、考慮減碼或出場,以保護資金。"}
    else:
        action = {"level": "wait", "label": "觀望為宜",
                  "text": "趨勢與訊號共識未同向(或處於盤整),方向不明朗。此時最好按兵不動,等兩個條件一致再行動——多數虧損都來自在不該動時硬要動。"}
    signals["action"] = action

    return {"trend": trend, "trendTerm": term, "trendDesc": desc, "indicators": inds,
            "signals": signals,
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


def plain_summary(t, df, tech, reg, d2e):
    c = df["Close"]
    chg_1m = (c.iloc[-1] / c.iloc[-21] - 1) * 100
    chg_3m = (c.iloc[-1] / c.iloc[-63] - 1) * 100
    name = INFO[t]["name"]
    word = "上漲" if chg_1m > 2 else ("下跌" if chg_1m < -2 else "盤整")
    s = "{} 近一個月{}({:+.1f}%),近三個月 {:+.1f}%,目前判定為「{}」".format(name, word, chg_1m, chg_3m, tech["trendTerm"])
    if reg.get("heldBars"):
        s += "(自 {} 起,已維持 {} 個交易日)。".format(reg["sinceDate"], reg["heldBars"])
    else:
        s += "。"
    s += "支撐位約 {:,.0f}({:+.1f}%)、壓力位約 {:,.0f}({:+.1f}%)。".format(
        tech["support"], tech["supportPct"], tech["resistance"], tech["resistancePct"])
    if reg.get("pending"):
        s += " " + reg["pending"]["text"] + "。"
    if d2e is not None:
        s += " 距下次財報還有 {} 天,財報前後波動通常加大,請留意。".format(d2e)
    return s


def main():
    with open(os.path.join(PROC, "events.json"), encoding="utf-8") as fp:
        events = json.load(fp)
    with open(os.path.join(PROC, "fundamentals.json"), encoding="utf-8") as fp:
        funda = json.load(fp)
    spx_df = pd.read_csv(os.path.join(RAW, "GSPC.csv"), parse_dates=["Date"], index_col="Date")
    spx = spx_df["Close"]

    TPE = timezone(timedelta(hours=8))
    now_tpe = datetime.now(timezone.utc).astimezone(TPE).strftime("%Y-%m-%d %H:%M")
    data = {"updated": now_tpe + " (台灣時間)", "stocks": {}}
    for t, meta in INFO.items():
        df = pd.read_csv(os.path.join(RAW, t + ".csv"), parse_dates=["Date"], index_col="Date")
        tech = technicals(df, spx)
        reg = regime_info(df)
        f = funda["stocks"].get(t, {})
        ev = events["stocks"][t]
        tail = df.tail(CHART_DAYS)
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
            "regime": reg,
            "dates": [x.strftime("%Y-%m-%d") for x in tail.index],
            "close": [round(float(x), 2) for x in tail["Close"]],
            "volume": [int(x) for x in tail["Volume"]],
            "spx": [float(x) for x in spx_norm],
            "fundamentals": fundamentals_card(f),
            "nextEarnings": f.get("nextEarnings"),
            "daysToEarnings": d2e,
            "summary": plain_summary(t, df, tech, reg, d2e),
            "price_events": ev["price_events"],
            "news": ev["news"],
        })
        data["stocks"][t] = entry
    js = "window.APP_DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    os.makedirs(APP, exist_ok=True)
    with open(os.path.join(APP, "data.js"), "w", encoding="utf-8") as fp:
        fp.write(js)
    print("app/data.js updated ({})".format(data["updated"]))
    for t, v in data["stocks"].items():
        r = v["regime"]
        print("  {} {} | 維持 {} 日(自 {}) | 訊號 多{}/空{}/中{}".format(
            t, v["trendTerm"], r.get("heldBars"), r.get("sinceDate"),
            v["signals"]["bull"], v["signals"]["bear"], v["signals"]["neutral"]))


if __name__ == "__main__":
    main()
