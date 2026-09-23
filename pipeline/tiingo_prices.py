"""Tiingo EOD adapter. Authentication stays in headers, never URLs or logs."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
import pandas as pd
from price_validation import validate_prices

def load_token():
    token = os.environ.get("TIINGO_API_KEY", "")
    path = Path(__file__).resolve().parents[1] / ".env"
    if not token and path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "TIINGO_API_KEY":
                token = value.strip().strip("\"'")
                break
    if not token:
        raise ValueError("TIINGO_API_KEY is missing; configure your free Tiingo account token")
    return token

def parse_prices(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Tiingo returned no price records")
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df.pop("date"), utc=True).dt.tz_localize(None).dt.normalize()
    # Adjusted OHLC includes splits/dividends. Preserve reported volume as in the original app.
    df = df.rename(columns={"adjOpen":"Open", "adjHigh":"High", "adjLow":"Low",
                            "adjClose":"Close", "volume":"Volume"})
    return validate_prices(df).round(4)

def fetch_tiingo(ticker, start="2005-01-01"):
    if ticker.startswith("^"):
        raise ValueError("Index coverage is not assumed; do not substitute SPY for S&P 500")
    token = load_token()
    url = "https://api.tiingo.com/tiingo/daily/" + quote(ticker, safe="") + "/prices?" + urlencode({"startDate":start})
    req = Request(url, headers={"Authorization":"Token " + token, "Accept":"application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            rows = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Tiingo HTTP {exc.code} for {ticker}") from None
    return parse_prices(rows)
