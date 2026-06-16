# ARCHITECTURE.md — AI Names Daily Options Screener

This is the authoritative technical spec. Build to this document.

## 1. Purpose

A scheduled tool that, once per trading day after market close, evaluates a fixed
universe of 100 AI-themed stocks for options swing-trade setups. For each name it
fetches price, analyst targets, and implied volatility, computes an IV-adjusted
upside score, applies filters, and emits a ranked digest of names that pass. The
goal is to surface buys, not to place trades.

The core idea: raw analyst upside % is a gross number. Implied volatility is what
the options market charges to access that upside. Dividing upside by IV gives a
cost-adjusted score — how much consensus upside you get per unit of volatility
you pay for. Higher is better.

## 2. File structure

```
ai-screener/
├── watchlist.csv          # 100 names: ticker, tier, theme, notes
├── config.py              # all tunable values live here
├── screener.py            # fetch + score a single ticker -> dict
├── runner.py              # loop watchlist, filter, rank, write results
├── alerts.py              # format digest text + optional email
├── scheduler.py           # cron entry point; runs a full daily cycle
├── results/
│   └── .gitkeep
├── requirements.txt
├── README.md
└── .gitignore
```

## 3. Data layer (per ticker, via yfinance)

For each ticker fetch and derive:

| Field | Source | Notes |
|---|---|---|
| current price | `info["regularMarketPrice"]` → fallback `info["currentPrice"]` | |
| market cap | `info["marketCap"]` | used for the $10B floor |
| analyst targets | `targetLowPrice`, `targetMeanPrice`, `targetMedianPrice`, `targetHighPrice` | |
| analyst count | `numberOfAnalystOpinions` | low-confidence if < 5 |
| 6-month ATM IV | options chain (see below) | the non-obvious part |
| 50-day MA | `ticker.history(period="3mo")["Close"].rolling(50).mean()` | last value |
| earnings date | `ticker.calendar` or `ticker.get_earnings_dates()` | days until next |

### 6-month ATM IV — exact logic

1. `expiries = ticker.options` → list of date strings.
2. Pick the expiry whose distance from today is closest to 180 days.
3. `chain = ticker.option_chain(expiry)` → `chain.calls`, `chain.puts`.
4. ATM strike = the strike closest to current price, found separately for calls
   and puts.
5. IV = average of the ATM call `impliedVolatility` and ATM put `impliedVolatility`.
6. yfinance returns IV as a decimal (0.35 = 35%). Keep it decimal internally,
   multiply by 100 only for display.
7. If there are no options, or IV is NaN/None, set IV to `None` and mark the name
   as "no options data" — it should still appear in the raw CSV but cannot pass
   the score filter.

## 4. Scoring

```
upside_pct(target)   = (target - price) / price * 100        # per target type
mean_upside_pct      = upside_pct(targetMeanPrice)
iv_adj_score         = mean_upside_pct / (iv * 100)          # the headline score
above_50d_ma         = price > ma50                          # bool, momentum gate
days_to_earnings     = (next_earnings_date - today).days     # int or None
```

Compute `upside_pct` for low / mean / median / high so the CSV has the full
range, but `iv_adj_score` uses the mean target.

## 5. Filters & thresholds (config.py)

A name is FLAGGED only if it passes ALL of these. The thresholds differ slightly
by tier because risky names structurally carry higher IV and higher upside.

| Filter | Safe tier | Risky tier |
|---|---|---|
| iv_adj_score > | 0.8 | 0.6 |
| mean_upside_pct > | 12% | 20% |
| analyst_count >= | 5 | 4 |
| market_cap > | $10B | $2B |
| price > 50-day MA | required | required |
| days_to_earnings not within | 14 days | 14 days |

Put every number above in `config.py` as a dict keyed by tier, e.g.
`THRESHOLDS["safe"]["min_score"]`. Never hardcode them in logic.

Notes:
- The earnings filter exists because IV inflates artificially in the ~2 weeks
  before earnings, distorting the score. A name failing only the earnings gate
  should be logged as "deferred — earnings soon" rather than silently dropped,
  so I know to revisit it after the print.
- A name with `iv = None` (no options) can never be flagged but still gets a row
  in the raw CSV.

## 6. Output

Two artifacts every run, written to `results/`:

**A. Raw CSV** — `results/YYYY-MM-DD.csv`
One row per ticker (all 100, flagged or not), columns:
`ticker, tier, theme, price, market_cap_b, mean_target, mean_upside_pct,
low_upside_pct, high_upside_pct, iv_pct, iv_adj_score, analyst_count,
above_50d_ma, days_to_earnings, status`

`status` ∈ {`flagged`, `passed_no_flag`, `deferred_earnings`, `no_options`,
`fetch_failed`}.

**B. Text digest** — `results/digest_YYYY-MM-DD.txt`
Human-readable. Structure:
- Header: date, how many names scanned, how many flagged.
- Section "SAFE flags" — tabulate table of flagged safe names, sorted by score
  descending: ticker | theme | price | upside% | IV% | score | analysts.
- Section "RISKY flags" — same table for risky names.
- Section "Deferred (earnings within 14d)" — names that would have flagged.
- Footer: one-line reminder this is research, not advice.

**C. Email (optional, off by default)**
`alerts.py` has a `send_digest_email()` that sends the text digest via Gmail
SMTP. Gated by `SEND_EMAIL` in config. When False, it's a no-op that prints
"email disabled". README documents the Gmail app-password setup.

## 7. Scheduling

`scheduler.py` is the single entry point cron invokes. It:
1. Loads config + watchlist.
2. Runs the full scan (with rate-limit pacing).
3. Writes CSV + text digest.
4. Calls `alerts.send_digest_email()` (no-op if disabled).
5. Logs start/end time and any per-ticker failures to a run log.

Cron line (4:30pm ET weekdays; user adjusts for their timezone) goes in the
README, e.g.:
```
30 16 * * 1-5  cd /Users/<user>/projects/ai-screener && ./venv/bin/python scheduler.py >> results/run.log 2>&1
```

## 8. Rate-limit & resilience strategy (mandatory)

- `SLEEP_BETWEEN_CALLS` (default 1.5s) between tickers. At 100 names that's ~2.5
  min per run, which is fine — this is a daily batch, not real-time.
- Retry decorator: 3 attempts, exponential backoff (2s, 4s, 8s) on exception or
  empty `.info`.
- Per-ticker try/except so one failure → `status = fetch_failed`, logged, run
  continues.
- Cache `.info` per ticker per run.
- If more than 30% of tickers fail in a run, the digest header prints a loud
  warning that Yahoo may be rate-limiting and the results are partial.

## 9. Testing plan (do this during the build, not after)

1. `screener.py` on `MSFT` alone → print the returned dict, eyeball every field.
2. `runner.py` on a 5-ticker slice (`MSFT, NVDA, PLTR, CRDO, OKLO`) → confirm CSV
   columns, text digest sections, and that at least the filtering logic runs.
3. Full 100-name run is left to the user to run manually once, to avoid burning
   the rate limit during the build.

## 10. README requirements

Written so a non-expert friend could run it:
- What it does, in 2 sentences.
- Setup: clone/unzip, create venv, `pip install -r requirements.txt`.
- Run manually: `./venv/bin/python scheduler.py`.
- Where output lands (`results/`).
- How to schedule with cron (give the exact line + how to edit crontab).
- How to turn on email (Gmail app password steps, flip `SEND_EMAIL = True`).
- How to edit the watchlist (CSV columns explained).
- How to tune thresholds (point at `config.py`, explain each).
- One-line disclaimer: research tool, not financial advice.
