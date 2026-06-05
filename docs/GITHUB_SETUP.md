# GitHub 雲端自動更新 + 手機使用教學(一次設定,終身自動)

完成後:每個交易日台灣時間早上 6 點,雲端自動更新資料;
你手機打開網址就是最新內容,完全不需要開自己的電腦。

## 第一步:建立 GitHub 帳號與 Repo(約 5 分鐘)

1. 到 https://github.com 註冊帳號(免費)
2. 右上角「+」→「New repository」
   - Repository name: `stock-trend-companion`
   - 選 **Public**(Pages 免費版需要公開;介意的話可改用 Private + 付費方案)
   - 按「Create repository」

## 第二步:上傳整個專案資料夾

最簡單方法(網頁拖拉):
1. 在剛建立的 repo 頁面點「uploading an existing file」
2. 把 `stock_trend_analysis` 資料夾裡的**所有內容**拖進去
   (包含隱藏的 `.github` 資料夾——若拖不進去,見下方「命令列方法」)
3. 按「Commit changes」

命令列方法(需安裝 git):
```
cd C:\Users\USER\Desktop\stock_trend_analysis
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<你的帳號>/stock-trend-companion.git
git push -u origin main
```

## 第三步:啟用 GitHub Pages 與 Actions(約 2 分鐘)

1. Repo 頁面 → Settings → Pages → Source 選 **GitHub Actions**
2. Repo 頁面 → Actions → 若出現啟用提示,按「I understand, enable them」
3. Actions → 左側選「daily-update」→ 右側「Run workflow」手動跑第一次
4. 等 2~3 分鐘跑完(綠色勾勾),Pages 網址就生效:
   `https://<你的帳號>.github.io/stock-trend-companion/`

## 第四步:手機加入主畫面(像 App 一樣用)

- iPhone:Safari 開啟網址 → 分享按鈕 → 「加入主畫面」
- Android:Chrome 開啟網址 → 右上選單 → 「加到主畫面」

## 之後會自動發生的事

- 週二~週六台灣時間早上 6:00(美股收盤後),雲端自動執行 run_daily.py
- 更新的資料自動 commit 回 repo 並重新部署 Pages
- 你手機打開就是最新;App 頂部會顯示「資料更新」時間可以核對

## 常見問題

- **想改追蹤的股票**:改四支 pipeline 程式裡的 WATCHLIST 與 INFO,push 上去即可
- **想改更新時間**:改 `.github/workflows/daily-update.yml` 裡的 cron(UTC 時間)
- **Actions 失敗**:大多是 Yahoo 暫時擋爬蟲,隔天會自動恢復;也可手動 Run workflow 重試
- **免費額度**:GitHub Actions 公開 repo 完全免費,本工作每天約 1 分鐘,遠低於限制
