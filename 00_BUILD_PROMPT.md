# BUILD PROMPT — AI Names Daily Options Screener Server

Paste this entire message into Claude Code as your first message, after placing
`ARCHITECTURE.md` and `watchlist.csv` in the project folder.

---

I'm building a daily options swing-trade screener that monitors a fixed universe
of 100 AI-themed stocks, scores each one, and emails me the names worth a closer
look. I want the entire thing built in this one session.

## Before you write any code

1. Read `ARCHITECTURE.md` in this folder in full — it is the authoritative spec.
2. Read `watchlist.csv` in this folder — it contains the 100 names, their tier
   (safe / risky), theme, and a one-line note each.
3. Confirm back to me, in 5 bullet points max, your understanding of: the data
   you'll fetch per ticker, the score formula, the filter thresholds (and how
   safe vs risky differ), the output format, and the rate-limit strategy. Then
   proceed without waiting for me.

## What to build

Build the full project exactly as laid out in the "File structure" section of
`ARCHITECTURE.md`. Every file in that tree must exist and be complete:

```
ai-screener/
├── watchlist.csv          # already present — do not overwrite, read it
├── config.py              # thresholds, paths, email settings, sleep timing
├── screener.py            # core: fetch + score one ticker, returns a dict
├── runner.py              # loops the whole watchlist, applies filters, writes output
├── alerts.py              # formats results into a text digest and (optional) email
├── scheduler.py           # entry point cron calls; orchestrates a full daily run
├── results/               # daily CSV logs land here (create the dir, add .gitkeep)
├── requirements.txt
├── README.md
└── .gitignore
```

## Critical constraints (read these carefully)

**Rate limiting is the #1 risk.** I have already been rate-limited (HTTP 429) by
Yahoo Finance when hitting it too fast. With 100 names this WILL happen unless
you handle it. You must:
- Add a configurable `SLEEP_BETWEEN_CALLS` delay (default 1.5s) between tickers.
- Wrap every yfinance call in a retry decorator with exponential backoff (e.g.
  3 retries, doubling wait, on any exception or empty result).
- Cache each ticker's raw `.info` for the duration of a run so you never fetch
  the same thing twice.
- On a hard failure for one ticker, log it, skip it, and keep going — one bad
  name must never crash the whole run.

**Build incrementally and test as you go.** Do NOT write all files then run once
at the end. Instead:
1. Write `config.py` and `screener.py` first.
2. Test `screener.py` on a SINGLE ticker (use `MSFT`) and show me the dict it
   returns. Verify the IV fetch, MA, and earnings date all look right.
3. Only then write `runner.py`, and test it on a 5-name slice of the watchlist
   (not all 100 yet) to confirm filtering and CSV output work.
4. Then write `alerts.py` and `scheduler.py`.
5. Do a final dry run on the 5-name slice end to end.
6. Do NOT run the full 100-name scan yourself — that risks rate limiting. Leave
   that for me to run manually once. Just confirm the code is correct.

**Output: start with a text file, email is optional/off by default.** The daily
digest writes to `results/digest_YYYY-MM-DD.txt` AND `results/YYYY-MM-DD.csv`.
Email sending via Gmail SMTP must be present but gated behind a
`SEND_EMAIL = False` flag in `config.py` so it does nothing until I set up an app
password and flip it on. Document the Gmail app-password setup in the README.

## Code quality

- Every function gets a docstring.
- Use type hints throughout.
- No hardcoded thresholds or tickers anywhere except `config.py` and
  `watchlist.csv`.
- Use `tabulate` for the text digest table, formatted `rounded_outline`.
- Comment the IV-fetch logic and the retry/backoff logic well — those are the
  non-obvious parts.
- Use only the standard scientific stack plus yfinance: `yfinance`, `pandas`,
  `numpy`, `tabulate`. No exotic dependencies.

## Environment

Create a fresh virtualenv `venv` inside the project folder, install into it from
`requirements.txt`, and use it for all testing so we avoid the Anaconda NumPy
conflict I hit before. Pin `numpy<2` in requirements.txt to be safe.

## Final deliverables checklist

Before you tell me you're done, confirm each:
- [ ] All files in the tree exist and are complete
- [ ] `screener.py` tested on MSFT, dict shown to me
- [ ] `runner.py` tested on a 5-name slice, CSV + text digest produced
- [ ] Email path present but `SEND_EMAIL = False`
- [ ] `numpy<2` pinned, venv created and working
- [ ] README covers: setup, venv, running manually, cron scheduling, Gmail app
      password, how to edit the watchlist, how to tune thresholds
- [ ] `git init` + initial commit made
- [ ] A one-paragraph summary of how I run it daily, and the exact cron line to
      add

Build it all now.
