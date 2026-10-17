# Validation record

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Setup and deployment](GITHUB_SETUP.md)

This record describes the documentation review on **October 17, 2026**, against application source commit `7ac64a08c69ee1a9510258857b7e02a7aca06ac8`. It separates observable engineering behavior from claims the repository does not establish.

## Existing automated checks

Both existing commands passed during this review: **21 Python tests** and the **JavaScript rendering regression**. The local environment used Windows, Python **3.11.8**, Node.js **24.19.0**, and the unchanged `requirements.txt`.

```bash
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

| Test file | Covered behavior |
| --- | --- |
| `test_quotes.py` | Same-date completed-session Yahoo repair, price adjustment, numeric session metadata, rejection of incorrect dates/open sessions/incomplete bars/interior gaps, Tiingo adjusted-price parsing, and no request without a token. |
| `test_history.py` | Same-date historical recovery, persisted records, dividend and split handling, conflict rejection, unresolved gaps without verified records, and preservation of valid source corrections. |
| `test_schedule.py` | Taiwan/US session alignment, weekends and holidays, winter and early closes, stale-session rejection, retries/exhaustion, and verified-cache file persistence. |
| `test_frontend.cjs` | Rendering using the committed payload and injected invalid values (`NaN`, `Infinity`, `null`, and a string); unavailable-quote states, warning text, and suppression of invalid valuation totals. |

The first local Python run passed 20 tests but encountered a sandbox permission error when replacing a file in the default temporary directory. All 21 passed after `TEMP` and `TMP` were directed to a writable workspace directory. Application and test source were unchanged. This environment adjustment is not a new application dependency.

The JavaScript test executes the inline script in a Node `vm` with a small mocked DOM and browser storage. It checks generated markup and safeguards; it does not exercise a real layout engine, Chart.js interaction, browser persistence, or the full valid detail page. The cache test reads back a saved JSON file within the test process; its name does not establish a subprocess-level persistence test.

These checks do not measure indicator parity with another library, classification accuracy, investment returns, full application coverage, provider uptime, or end-to-end deployment reliability. No full network data-refresh run was performed locally for this documentation update.

## Live deployment and screenshots

The [published dashboard](https://stephen0701.github.io/stock-trend-analysis/) was accessible during this review and displayed a generation time of **2026-10-17 15:01 (Taiwan time)**. The watchlist, NVIDIA detail chart, and learning navigation were inspected in a browser. The chart displayed its price and benchmark lines, volume, historical markers, and native tooltip.

The existing [scheduled run 122](https://github.com/stephen0701/stock-trend-analysis/actions/runs/39012035753), associated with the reviewed source commit, completed successfully on October 17, 2026. This is evidence of that run's success, not a service-level guarantee. No production workflow was manually triggered for this documentation review.

| Screenshot | Provenance |
| --- | --- |
| [`images/watchlist.png`](images/watchlist.png) | Live dashboard, October 17, 2026; crop to the application area; all four watchlist instruments visible. |
| [`images/price-chart.png`](images/price-chart.png) | Live NVIDIA detail page, same session; three-month chart, cropped to the chart card. |

Screenshots preserve the Traditional Chinese UI. They contain public dashboard output and no personal purchase-lot records. Their prices and timestamps are historical examples and will differ from later deployments.

## Review boundaries

This portfolio update changes documentation and screenshot assets. The Traditional Chinese UI, analysis formulas, price acquisition/recovery rules, data snapshots, requirements, tests, workflow, and deployment configuration are preserved.

The saved `app/data.js` reviewed in Git showed a July 9, 2026 generation timestamp, whereas the live deployment had October data. This matches the workflow's artifact-only generation; it does not commit refreshed data to the source branch. The documentation therefore distinguishes a local snapshot preview from a live validated refresh.

The old documentation's claims about a Stooq fallback, retained news summaries, automatic data commits, a single 06:00 Taiwan schedule, and an undocumented removed prediction experiment have been replaced with behavior supported by the current source. No historical backtest or personal contribution claims are inferred from that older prose.
