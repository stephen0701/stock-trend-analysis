# 架構說明

> 定位:**描述現況的趨勢儀表板**。不預測、不建議,把判斷所需的資訊整理到你看得懂。

## 資料流

```
Yahoo Finance(備援 Stooq)
   │
   ├─ fetch_prices.py        NVDA/GOOG/LLY + S&P500 歷史日線 → data/raw/*.csv
   ├─ fetch_events.py        ±4% 重大波動日 + 新聞含摘要   → data/processed/events.json
   ├─ fetch_fundamentals.py  本益比等基本面 + 下次財報日    → data/processed/fundamentals.json
   │
   └─ build_app_data.py      計算趨勢判定與全部指標 → app/data.js
                                  │
                              app/index.html(手機/瀏覽器)
```

## 趨勢判定規則(技術分析標準)

- **上升趨勢**:股價 > 20日均線 > 60日均線(多頭排列)、60日均線向上、ADX ≥ 20
- **下降趨勢**:完全相反(空頭排列、60日均線向下、ADX ≥ 20)
- **盤整**:ADX < 20(趨勢強度不足)或均線糾結

指標皆為描述性統計,不涉及預測。曾有 AI 預測模組,經回測未能穩定贏過
「永遠猜漲」基準,且使用者目標為觀測現況,已於 2026-06-05 移除。

## 自動化

- 本機:`run_daily.py`(約 30 秒)
- 雲端:GitHub Actions(`.github/workflows/daily-update.yml`),
  週二~六 UTC 22:00(台灣早上 6:00)自動執行並部署 GitHub Pages

## 日後可擴充

1. LLM 新聞中文摘要與利多/利空標註(接 API,改 fetch_events.py)
2. 週線長期趨勢 + 日線短期趨勢的多時間框架判定
3. 紙上交易日記(記錄自己的判斷並回頭驗證)
4. 加追蹤標的:改 pipeline 四支程式的 WATCHLIST/INFO
