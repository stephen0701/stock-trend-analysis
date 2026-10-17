# Local setup, automation, and deployment

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Validation](VALIDATION.md)

## Prerequisites

- Git to clone the repository.
- Python **3.11**, matching the Actions runtime, for refreshes and Python tests.
- Node.js for `tests/test_frontend.cjs`; no npm packages are required.
- A browser and internet access for the Chart.js CDN and external data providers.

Previewing the saved application does not require installing Python packages. Refreshing it requires `requirements.txt`. The default Yahoo path requires no API token.

## Clone and preview

```bash
git clone https://github.com/stephen0701/stock-trend-analysis.git
cd stock-trend-analysis
python -m http.server 8000 --directory app
```

Open http://localhost:8000/ and stop the server with `Ctrl+C` when finished. Opening `app/index.html` directly also works with its script-based payload loading. Browser storage is specific to the origin, so holdings entered on localhost will not be shared with the live Pages site.

`app/data.js` and the files under `data/` are committed snapshots. They can be older than the live site because the deployment workflow regenerates data without committing it. Stale-data warnings during a local preview are expected when the snapshot is old. Do not run just the builder to make an old snapshot appear freshly acquired.

## Install the pipeline dependencies

Keep the environment outside the repository so it cannot be included accidentally in a commit. Run these commands from the repository root.

**Windows PowerShell:**

```powershell
py -3.11 -m venv ..\stock-trend-analysis-venv
..\stock-trend-analysis-venv\Scripts\python.exe -m pip install -r requirements.txt
..\stock-trend-analysis-venv\Scripts\python.exe run_daily.py
```

The `py` command is the Windows Python launcher. If it is unavailable, use the path to your Python 3.11 interpreter to create the environment. Invoking the environment's executable directly avoids changing PowerShell execution policy.

**macOS/Linux:**

```bash
python3.11 -m venv ../stock-trend-analysis-venv
source ../stock-trend-analysis-venv/bin/activate
python -m pip install -r requirements.txt
python run_daily.py
```

**Windows Command Prompt alternative:** activate `..\stock-trend-analysis-venv\Scripts\activate.bat`, then run `python run_daily.py` or `run_daily.bat` from the repository root. The batch launcher uses whichever `python` is on `PATH`; install dependencies into that environment first.

## What a refresh changes

`run_daily.py` invokes these scripts with the same interpreter, in order:

| Stage | Inputs/source | Outputs |
| --- | --- | --- |
| `pipeline/fetch_prices.py` | Yahoo daily quotes, NYSE calendar, verified records | `data/raw/{NVDA,GOOG,LLY,DRAM,GSPC}.csv`, `data/raw/price_status.json`, and the ignored verified-bar cache. |
| `pipeline/fetch_events.py` | Price CSVs and Yahoo news | `data/processed/events.json`. |
| `pipeline/fetch_fundamentals.py` | Yahoo metadata and earnings calendar | `data/processed/fundamentals.json`. |
| `pipeline/build_app_data.py` | Price CSVs, processed JSON, optional price status | `app/data.js`. |

A failure stops later stages. Successful earlier local stages can already have replaced their outputs; there is no rollback of the entire local run. Check the terminal exit status before treating a refresh as complete. Reload the browser after a successful run. A refresh changes saved data files, so review `git status` before committing unrelated work.

To rebuild only the payload from existing files, use `python pipeline/build_app_data.py`. This does not fetch data or verify the latest completed session. Its output should not be used as evidence of a successful market-data refresh.

## Run the existing tests

Use the environment's Python executable, or activate the environment first:

```bash
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

Tests use fixtures, mocks, temporary files, and the committed frontend payload. They do not require provider credentials or fetch live quotes. See [validation](VALIDATION.md) for their coverage and limitations.

## Existing GitHub Actions workflow

The workflow file is [`.github/workflows/daily-update.yml`](../.github/workflows/daily-update.yml). Its name is `daily-update`.

| Setting | Current value |
| --- | --- |
| Scheduled triggers | `17 22 * * 1-5` and `17 2 * * 2-6`, in UTC. |
| Taiwan schedule | Tuesday–Saturday at 06:17 and 10:17 (UTC+8). |
| Other triggers | Push to `main`; manual `workflow_dispatch`. A pull request alone does not trigger this workflow. |
| Runner/runtime | `ubuntu-latest`; Python 3.11 through `actions/setup-python@v5`; Node.js supplied by the runner. |
| Permissions | `contents: read`, `pages: write`, `id-token: write`. |
| Concurrency | One `daily-pages` group across build and deploy; `cancel-in-progress: false`. |
| Timeouts | 30 minutes for `update-and-deploy`; 15 minutes for the dependent `deploy` job. |
| Published directory | `app/`, uploaded by `actions/upload-pages-artifact@v3`. |
| Deployment | `actions/deploy-pages@v4` to the `github-pages` environment. |

The build job checks out source with `actions/checkout@v4`, installs `requirements.txt`, runs both regression commands, restores the verified-bar cache, and runs the daily pipeline. It attempts to save the cache when the run has not been cancelled and `yahoo_verified.json` exists, including after a pipeline failure. This preserves successful ticker records when a later request fails. Only a successful pipeline reaches artifact upload and the dependent deployment.

Cache keys include `github.run_id` and `github.run_attempt`; restoration uses the `yahoo-verified-v1-` prefix. The cache is separate from Git history and can be evicted. It does not replace the seed or guarantee recovery for every historical gap.

Generated CSV, JSON, and `data.js` changes exist in the runner workspace and deployed artifact. **They are not pushed back to `main`.** A workflow run can therefore deploy data newer than the files visible in the repository.

GitHub schedules can start late, and public repositories can have scheduled workflows disabled after prolonged inactivity. Monitor Actions rather than assuming an exact start time or permanent operation. The NYSE calendar, rather than the weekday cron alone, determines the required completed session.

## Inspect the deployment

- [Live application](https://stephen0701.github.io/stock-trend-analysis/)
- [Workflow history](https://github.com/stephen0701/stock-trend-analysis/actions/workflows/daily-update.yml)

For the existing repository, use the current configuration. No settings changes are needed to view the live demo or run the application locally.

For an independently maintained fork or copy, configure **Settings → Pages → Build and deployment → Source → GitHub Actions**, and ensure Actions and the `github-pages` environment permit deployment from its default branch. The existing workflow listens for pushes to `main`; a different default branch requires an intentional workflow change in that separate copy. Its Pages URL depends on its owner and repository name. A manual run is available under **Actions → daily-update → Run workflow** when an update is intended.

Adding the page to a phone's home screen is a browser shortcut. The repository has no service worker or web app manifest providing offline installation.

## Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| `ModuleNotFoundError` | Install requirements with the same interpreter used to run the pipeline. |
| Quote attempts fail | Read the fetch-stage error: connectivity, date mismatch, unresolved gaps, or price validation can stop publication. The script tries at most three times per ticker. A later schedule is another attempt, not guaranteed recovery. |
| Site still has an older generation time | Check both build and deploy jobs. A failed required stage leaves the previous deployment available. |
| Local data is old | The committed payload is a snapshot. Run the complete pipeline for a validated refresh; a rebuilt timestamp alone does not establish freshness. |
| News/fundamentals are empty | These requests can degrade to empty fields without failing the price pipeline. Check stage logs and provider availability. |
| Chart is missing | Check that the Chart.js CDN is reachable; the script is not vendored locally. |
| Holdings differ between devices | Holdings use browser-local storage, with no account sync or remote backup. |

The watchlist is defined in each of the three fetch stages and in `INFO` in `build_app_data.py`. Changing coverage requires coordinated code/data validation, especially for new or short-history tickers; it is not a runtime configuration feature.
