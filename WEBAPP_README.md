# OpsScreener Calculator — Web App

A client-side React calculator for the AI-names options screener. It implements
the exact scoring and filter logic from `01_ARCHITECTURE.md` (sections 4 and 5):

```
iv_adj_score = mean_upside_% / IV_%
```

A name is **flagged** only when all six checks pass for its tier (score, mean
upside, analyst count, market cap, price above the 50-day MA, and earnings not
within the window). It's research, not financial advice.

## How it works (data pipeline)

GitHub Pages can't run code or fetch live market data, so the data is produced
**ahead of time by a scheduled GitHub Action** and committed into the repo as a
static JSON file the page reads:

```
fetch_data.py  →  (GitHub Action, nightly)  →  docs/data/latest.json  →  the web page
```

1. `.github/workflows/refresh-data.yml` runs on a cron schedule (after US market
   close) and on demand.
2. `fetch_data.py` pulls prior-close price, analyst targets, market cap, the
   50-day MA, and the next earnings date for all 100 names via yfinance, and
   computes 6-month ATM implied volatility itself (see note below).
3. It scores every name with the OpsScreener rules and writes
   `docs/data/latest.json` (all 100 rows + summary counts).
4. The Action commits that file; Pages redeploys; the page shows the new scan.

The page has two tabs:
- **Daily Scan** — reads `latest.json`: flagged top buys (split safe/risky),
  deferred-earnings names, and the full ranked universe.
- **Calculator** — manual single-ticker scoring, for what-ifs.

### Note on implied volatility

yfinance's own `impliedVolatility` field is currently unreliable (it returns
near-zero / quantized junk for many strikes). So `fetch_data.py` ignores that
field and **solves IV from option market prices with Black-Scholes** across
several near-the-money strikes, taking the median. This produces stable, sane
values (e.g. MSFT ~35%, NVDA ~43%).

### Seeing data right away

`docs/data/latest.json` ships empty, so the first page load shows "No scan yet".
To populate it immediately, trigger the job manually:
**Actions tab → Refresh stock data → Run workflow**. It takes ~3-4 minutes
(100 names, paced to avoid rate limiting), commits the data, and the page shows
it on the next load. After that it refreshes automatically each weekday night.

## Files

```
docs/
├── index.html       # loads React + Babel from CDN, no build step
├── app.jsx          # the React UI (Daily Scan + Calculator tabs)
├── screener.js      # pure scoring + filter logic (port of the Python rules)
├── watchlist.js     # the 100-name universe (generated from watchlist.csv)
├── styles.css
└── data/
    └── latest.json  # nightly scan output (committed by the GitHub Action)
fetch_data.py             # nightly fetch + score (run by the Action)
requirements.txt          # deps for fetch_data.py (yfinance, pandas, numpy<2)
generate_watchlist_js.py  # regenerates docs/watchlist.js from watchlist.csv
.github/workflows/
├── refresh-data.yml       # nightly: fetch data, commit latest.json
└── sync-watchlist.yml     # regenerate watchlist.js when the CSV changes
```

## Run locally

The app loads `app.jsx` over HTTP, so open it through a local server (not
`file://`):

```bash
cd docs
python3 -m http.server 8123
# then open http://localhost:8123
```

## Deploy to GitHub Pages

Target URL: **https://pkarakala.github.io/stocks/** → GitHub user `pkarakala`,
repo named `stocks`, served from `/docs`.

1. Create a **new public repo named `stocks`** under your account at
   https://github.com/new (leave it empty — no README/license).

2. From this project folder, connect the remote and push (the repo is already
   committed locally on `main`):

   ```bash
   git remote add origin https://github.com/pkarakala/stocks.git
   git push -u origin main
   ```

3. In the repo on GitHub: **Settings → Pages**.
4. Under **Build and deployment → Source**, choose **Deploy from a branch**.
5. Set branch to **main** and folder to **/docs**, then **Save**.
6. Wait ~1 minute, then open:

   ```
   https://pkarakala.github.io/stocks/
   ```

The `/docs` folder is self-contained and uses only relative paths, so it works
under the `/stocks/` subpath with no build step and no config changes.

## Updating the watchlist

Edit `watchlist.csv`, then regenerate the JS data file:

```bash
python3 generate_watchlist_js.py
```

Commit and push; Pages redeploys automatically.

### Auto-sync (GitHub Actions)

`.github/workflows/sync-watchlist.yml` runs the generator automatically on every
push to `main` that touches `watchlist.csv` (or the generator). If the resulting
`docs/watchlist.js` differs, it commits the regenerated file back to the repo —
so you can just edit the CSV and push, and the web data stays in sync. You can
also trigger it manually from the repo's **Actions** tab.

Note: the workflow needs write access. In **Settings → Actions → General →
Workflow permissions**, ensure **Read and write permissions** is selected.

## Tuning thresholds

All thresholds live in one place: the `THRESHOLDS` object at the top of
`docs/screener.js`, keyed by tier (`safe` / `risky`) — the same numbers as the
Python `config.py`. Change them there and the UI updates on reload.
