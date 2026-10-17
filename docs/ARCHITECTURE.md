# Architecture and methodology

[README](../README.md) · [Setup and deployment](GITHUB_SETUP.md) · [Validation](VALIDATION.md)

## System boundaries

Python fetches and transforms market data locally or in GitHub Actions. A static browser application renders the resulting payload and stores holdings locally. There is no project API server, database service, frontend bundler, or trained prediction model.

| Layer | Implementation | Responsibility |
| --- | --- | --- |
| Orchestration | `run_daily.py` | Run four subprocesses sequentially with the current Python interpreter; stop after a failed stage. |
| Acquisition | `pipeline/fetch_prices.py` | Fetch daily quotes, require the correct completed session, retry failures, and stage price files. |
| Validation and recovery | `price_validation.py`, `yahoo_history.py`, `trading_session.py` | Validate OHLCV, recover eligible historical gaps, and identify the latest completed NYSE session. |
| Enrichment | `fetch_events.py`, `fetch_fundamentals.py` | Detect large moves; retrieve news, fundamentals, and earnings dates. |
| Analysis | `build_app_data.py` | Calculate indicators and regime transitions; serialize the browser payload. |
| Presentation | `app/index.html`, `app/data.js` | Render the Traditional Chinese interface with vanilla JavaScript and Chart.js 4.4.1. |
| Delivery | `.github/workflows/daily-update.yml` | Run regressions, rebuild data, cache verified bars, and deploy a static Pages artifact. |

Pipeline modules are under `pipeline/`; their filenames are shortened in this table for readability.

## Data pipeline

### 1. Daily prices

`fetch_prices.py` requests history starting at **2005-01-01**, where available, for NVDA, GOOG, LLY, DRAM, and the S&P 500 (`^GSPC`, stored as `GSPC.csv`). Yahoo Finance through `yfinance` is the default provider.

The Yahoo path requests history with `auto_adjust=False` and corporate-action fields, plus a separate one-day response. It checks that their final dates agree, verifies exchange-session metadata and market close, validates the complete one-day bar, and replaces the matching final historical bar. It then applies `Adj Close / Close` to OHLC prices and rounds output to four decimal places. Reported volume is retained. Despite the directory name, `data/raw/*.csv` contains **adjusted OHLC**, rather than untouched provider responses.

Validation includes:

1. Normalize and sort dates; reject empty responses, invalid dates, and duplicate sessions.
2. Require finite numeric OHLCV, positive prices, nonnegative volume, and consistent high/low bounds.
3. Use the NYSE calendar to identify the latest session whose market close has passed, including holidays, daylight saving changes, and early closes.
4. Require that session for every stock and the benchmark, with at least 65 rows per fetched instrument.
5. Retry each failed quote fetch up to three attempts, waiting 20 and then 40 seconds between attempts.
6. After all instruments pass, stage CSVs and `price_status.json`, then replace their destination files individually.

Staging prevents a failed acquisition from replacing the price set prematurely. The final replacements are per file; they are not a transaction covering the entire pipeline.

### Verified history recovery

`data/yahoo_verified_seed.json` supplies initial records. Runtime records are stored in the ignored `data/raw/.cache/yahoo_verified.json`. Each successful ticker is saved through a temporary file and `os.replace`, so its verified daily bar can survive a later ticker's failure.

`yahoo_history.py` can restore an existing historical row with a missing close only when a verified **same-ticker, same-date** bar is available. It accounts for subsequent splits, checks intact OHLC values for conflicts, and reconstructs missing adjusted closes using current adjustment factors and distributions. Valid fresh source corrections are preserved.

This recovery does not insert absent dates, substitute another day's quote, or repair arbitrary missing fields in otherwise valid rows. Unresolved gaps or conflicts fail subsequent validation. Cached records improve recovery but cannot guarantee upstream availability. Historical source responses underlying the committed seed were not independently re-fetched in this documentation review.

### 2. Price events and news

`fetch_events.py` reads the price CSVs, considers the last **504 rows**, and flags a daily close return when its absolute value is at least **4%** or at least **three sample standard deviations** of returns in that window. It retains the last 12 detected events per instrument. These are price-movement annotations; the pipeline does not establish their causes.

Up to eight news items per instrument are read from `yfinance`. The first matching regular-expression rule on title plus provider summary/description determines a positive, negative, or neutral label and a Traditional Chinese reason. Stored fields include headline, date, URL, publisher, label, and reason. Provider summary text is used for classification but is **not retained as an article summary in the output**. Failed news requests return an empty list. This is keyword matching, without a learned sentiment model or measured classification accuracy.

Output: `data/processed/events.json`.

### 3. Fundamentals and earnings

`fetch_fundamentals.py` retrieves market capitalization, trailing/forward P/E, earnings/revenue growth, dividend yield, and the first available upcoming earnings date from `Ticker.info` and `Ticker.calendar`. Exceptions are handled per request. Missing fields appear as placeholders rather than failing the whole price update. Fund and company fields may differ in availability.

Output: `data/processed/fundamentals.json`.

### 4. Analysis and browser payload

`build_app_data.py` reads the CSV and JSON inputs and generates `window.APP_DATA`. It serializes with `allow_nan=False`, writes `app/data.js.tmp`, and replaces `app/data.js` with `os.replace`.

| Calculation | Implementation |
| --- | --- |
| Moving averages | Simple rolling means over 20, 60, and 120 closes. The 120-day value may be unavailable with short histories. |
| Upward trend | `close > MA20 > MA60`, `MA60 > MA60.shift(5)`, and `ADX >= 20`. |
| Downward trend | `close < MA20 < MA60`, the rising condition above is false, and `ADX >= 20`. Equal MA60 values also satisfy the non-rising condition. |
| Range-bound state | All other combinations. |
| ADX | 14-period directional movement and true range, exponentially smoothed with `alpha=1/14`, `adjust=False`. |
| RSI | 14-period simple rolling average gains/losses; flat gain and loss windows map to 50. |
| MACD histogram | EMA(12) minus EMA(26), less its EMA(9) signal; EMAs use `adjust=False`. |
| Bollinger %B | Position within `MA20 ± 2 × rolling standard deviation`; zero standard deviation maps to 0.5. |
| Annualized volatility | 20-period sample standard deviation of daily percentage returns, scaled by `sqrt(252) × 100`. |
| Relative strength | Stock return minus S&P 500 return over 21 and 63 intervals, in percentage points. Benchmark dates are reindexed to stock dates with forward filling and rejected if leading values remain missing. |
| Support/resistance | Minimum low and maximum high over the last 60 available rows. |
| Regime history | Daily trend labels after the initial 60 rows, time in the current state, and the last 30 label changes. |
| Pending transition | While range-bound, a close above/below the preceding 20-row high/low range triggers an observation message. |

The seven displayed indicator rows receive bullish, bearish, or neutral tags. ADX and volatility always have neutral direction tags. A difference of at least two votes produces a directional consensus. Existing buy/reduce/wait prompts combine that consensus with the current trend. No predictive or financial performance is demonstrated by those rules.

The plain-language summary uses closes 20 and 62 intervals apart for its approximate one- and three-month changes (`iloc[-21]` and `iloc[-63]`), whereas benchmark-relative returns use 21 and 63 intervals. These implementation details are preserved. Technical calculations require at least 65 stock rows and 64 benchmark rows.

Up to **1,260** available rows per instrument are included for charting. The frontend offers 5-day, 1-month, 3-month, 1-year, and 5-year ranges and rebases the benchmark to the stock's first visible close for each selected range. A five-year button does not imply five years of history for recently listed instruments.

The payload carries a generation timestamp in Taiwan time, individual `priceDate` values, source/status metadata when present, indicator rows, regimes, prices, volumes, fundamentals, earnings countdowns, price events, and news. A generation timestamp is **not** proof of quote freshness. Running the builder alone does not perform the acquisition stage's completed-session check; earnings countdowns are fixed when the payload is built.

## Frontend behavior and storage

`app/index.html` reads the payload directly, without browser-side calls to the quote APIs. Chart.js is the only external script dependency. News links navigate to external publishers.

`hasQuote` checks the last two closes and daily high/low values before normal watchlist/detail rendering and holdings valuation. Unusable quotes suppress trend display and affected valuation totals. A separate warning is shown when the quote date is more than four calendar days old, or when supplied status metadata contains missing dates. This is a lightweight UI safeguard, not a second exchange-calendar validator. The current price writer produces source/date metadata; it does not emit `missingDates` on the normal successful path.

Purchase lots are stored under the browser `localStorage` key `portfolio`. The application has no server-side holdings storage, authentication, or device synchronization. Clearing site data or changing the hosting origin can remove access to these records.

## Dependencies and operational limits

Direct Python dependencies are pinned in `requirements.txt`: `yfinance==1.7.0`, `pandas==2.2.3`, `numpy==2.2.6`, and `pandas-market-calendars==5.4.0`. Transitive dependencies are not fully locked. CI selects Python 3.11; the workflow does not select a Node.js version separately. The frontend loads Chart.js 4.4.1 from cdnjs and has no local npm dependency tree.

The Tiingo adapter accepts an explicit `--provider tiingo` argument to the price stage, takes its token from `TIINGO_API_KEY` or `.env`, and uses adjusted OHLC with reported volume. The benchmark still uses Yahoo. Adapter parsing and missing-token behavior have fixture-based tests; real Tiingo responses were not verified in this review. Stooq is not an implemented fallback.

Prices, provider fields, and news may be delayed, missing, or revised. Optional enrichment failures can yield incomplete but deployable data. If a required stage fails, the workflow does not upload a new Pages artifact, and the existing deployment remains available. The project has no measured service-level objective, complete end-to-end browser suite, or validated trading-performance claim.
