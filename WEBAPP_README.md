# OpsScreener Calculator — Web App

A client-side React calculator for the AI-names options screener. It implements
the exact scoring and filter logic from `01_ARCHITECTURE.md` (sections 4 and 5):

```
iv_adj_score = mean_upside_% / IV_%
```

A name is **flagged** only when all six checks pass for its tier (score, mean
upside, analyst count, market cap, price above the 50-day MA, and earnings not
within the window). It's research, not financial advice.

## Why static / no backend

GitHub Pages serves static files only — it can't run Python or a live web
server, and browsers can't call Yahoo Finance directly (CORS + rate limits). So
this is a **calculator**: you enter the per-ticker numbers (from the Python tool's
CSV, your broker, or any data source) and it computes the score and verdict
instantly in the browser. The Python screener in this repo is what actually
fetches the live data.

## Files

```
docs/
├── index.html       # loads React + Babel from CDN, no build step
├── app.jsx          # the React UI (transpiled in-browser by Babel)
├── screener.js      # pure scoring + filter logic (port of the Python rules)
├── watchlist.js     # the 100-name universe (generated from watchlist.csv)
└── styles.css
generate_watchlist_js.py  # regenerates docs/watchlist.js from watchlist.csv
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

1. Create a repo and push this project:

   ```bash
   git init
   git add .
   git commit -m "Add OpsScreener calculator web app"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

2. In the repo on GitHub: **Settings → Pages**.
3. Under **Build and deployment → Source**, choose **Deploy from a branch**.
4. Set branch to **main** and folder to **/docs**, then **Save**.
5. Wait ~1 minute. Your site is live at:

   ```
   https://<you>.github.io/<repo>/
   ```

That's it — the `/docs` folder is self-contained, so no build action is needed.

## Updating the watchlist

Edit `watchlist.csv`, then regenerate the JS data file:

```bash
python3 generate_watchlist_js.py
```

Commit and push; Pages redeploys automatically.

## Tuning thresholds

All thresholds live in one place: the `THRESHOLDS` object at the top of
`docs/screener.js`, keyed by tier (`safe` / `risky`) — the same numbers as the
Python `config.py`. Change them there and the UI updates on reload.
