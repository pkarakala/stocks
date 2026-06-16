# How to use this package

Three files build the whole screener in one Claude Code session.

## Step 1 — make the project folder and drop these in

```bash
mkdir -p ~/projects/ai-screener
cd ~/projects/ai-screener
```

Move `watchlist.csv` and `01_ARCHITECTURE.md` into `~/projects/ai-screener/`.
(`00_BUILD_PROMPT.md` you just copy-paste from — it doesn't need to live in the
folder, but it's fine if it does.)

## Step 2 — open Claude Code in that folder

```bash
cd ~/projects/ai-screener
claude
```

## Step 3 — paste the build prompt

Open `00_BUILD_PROMPT.md`, copy the whole thing, paste it into Claude Code, hit
enter. It will read `ARCHITECTURE.md` and `watchlist.csv`, confirm its
understanding, then build every file.

## Step 4 — after it builds

It will have tested on MSFT + a 5-name slice. To run the full 100-name scan
yourself once (spaced out so Yahoo doesn't rate-limit):

```bash
./venv/bin/python scheduler.py
```

Check `results/` for the CSV and the text digest.

## Notes

- The tier assignments (safe vs risky) in `watchlist.csv` are a sensible starting
  point, not gospel. Some names sit near the $10B line and market caps move —
  the script verifies cap live, so a mis-tiered name just gets caught by the cap
  filter. Review and re-tag as you like.
- A few ETF/benchmark tickers (QQQ, SMH) are in the safe list as references; they
  have no analyst targets, so they'll log as `no_options` / `passed_no_flag` —
  harmless, but remove them if you only want single names.
- Email is off by default. Build and trust the text-file output first, then turn
  on Gmail once the logic looks right.
