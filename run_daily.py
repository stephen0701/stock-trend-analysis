# -*- coding: utf-8 -*-
"""
run_daily.py — 每日更新主程式(一鍵全部更新,約 30 秒)

依序執行:
  1. pipeline/fetch_prices.py        抓最新股價 + S&P 500
  2. pipeline/fetch_events.py        重大波動日 + 新聞(含摘要)
  3. pipeline/fetch_fundamentals.py  基本面 + 下次財報日
  4. pipeline/build_app_data.py      組合 App 資料

本機: python run_daily.py(或雙擊 run_daily.bat)
雲端: GitHub Actions 每日自動執行(見 docs/GITHUB_SETUP.md)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ("抓取股價", "fetch_prices.py"),
    ("事件與新聞", "fetch_events.py"),
    ("基本面與財報日", "fetch_fundamentals.py"),
    ("組合 App 資料", "build_app_data.py"),
]


def main():
    print("=== 每日更新開始 ===")
    for name, script in STEPS:
        print("\n--- {} ---".format(name))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", script)])
        if r.returncode != 0:
            print("!! 步驟失敗: {},中止。".format(name))
            sys.exit(1)
    print("\n=== 全部完成,打開 app/index.html 查看 ===")


if __name__ == "__main__":
    main()
