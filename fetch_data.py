#!/usr/bin/env python3
"""fetch_data.py — nightly data fetch + scoring for the OpsScreener web app.

Runs in GitHub Actions after market close. For every ticker in watchlist.csv it
fetches prior-close price, analyst targets, 6-month ATM implied volatility,
market cap, the 50-day MA, and the next earnings date via yfinance, scores each
name with the OpsScreener rules (see 01_ARCHITECTURE.md), and writes the result
to docs/data/latest.json. The static web page loads that JSON — so the site
shows last night's data with the top buys already flagged, no backend needed.

Rate limiting is the #1 risk (Yahoo returns HTTP 429 when hit too fast), so:
  - SLEEP_BETWEEN_CALLS pause between tickers
  - retry-with-exponential-backoff around every network call
  - per-ticker try/except so one bad name never crashes the run
  - .info cached once per ticker per run
"""
from __future__ import annotations

import csv
import datetime as dt
import functools
import json
import os
import statistics
import time
from typing import Any, Callable, Optional

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "watchlist.csv")
OUT_PATH = os.path.join(HERE, "docs", "data", "latest.json")

# --- tunables (keep in sync with docs/screener.js THRESHOLDS) ---
SLEEP_BETWEEN_CALLS = 1.5  # seconds between tickers
RETRIES = 3
BACKOFF_BASE = 2.0  # seconds: 2, 4, 8
TARGET_IV_DAYS = 180  # pick the option expiry closest to ~6 months out
RISK_FREE_RATE = 0.04  # annual; used to solve implied vol from option prices
MIN_VALID_IV = 0.02  # decimal; ignore degenerate solver results
MAX_VALID_IV = 5.0  # decimal; ignore absurd IV (>500%)
NEAR_STRIKES = 5  # sample this many near-the-money strikes per side for IV
MAX_EXPIRY_ATTEMPTS = 4  # try this many expiries (closest to 180d) for valid IV
PARTIAL_FAIL_RATIO = 0.30  # warn if more than this fraction of names fail

THRESHOLDS = {
    "safe": {
        "min_score": 0.8,
        "min_upside_pct": 12,
        "min_analysts": 5,
        "min_cap_b": 10,
        "earnings_window_days": 14,
    },
    "risky": {
        "min_score": 0.6,
        "min_upside_pct": 20,
        "min_analysts": 4,
        "min_cap_b": 2,
        "earnings_window_days": 14,
    },
}

STATUS_FLAGGED = "flagged"
STATUS_PASSED = "passed_no_flag"
STATUS_DEFERRED = "deferred_earnings"
STATUS_NO_OPTIONS = "no_options"
STATUS_FAILED = "fetch_failed"


def with_retry(fn: Callable) -> Callable:
    """Retry a flaky network call up to RETRIES times with exponential backoff.

    Retries on any exception OR a falsy/empty return value (yfinance often
    returns an empty dict/frame rather than raising when rate-limited).
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(RETRIES):
            try:
                result = fn(*args, **kwargs)
                if result is not None and not (
                    hasattr(result, "empty") and result.empty
                ):
                    return result
            except Exception as exc:  # noqa: BLE001 — we want to retry on anything
                last_exc = exc
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2**attempt))
        if last_exc is not None:
            raise last_exc
        return None

    return wrapper


@with_retry
def fetch_info(tk: yf.Ticker) -> dict:
    """Return the ticker's .info dict (retried)."""
    return tk.info


@with_retry
def fetch_history(tk: yf.Ticker):
    """Return ~3 months of daily history for the 50-day MA (retried)."""
    return tk.history(period="3mo")


def compute_iv(tk: yf.Ticker, price: float) -> Optional[float]:
    """6-month ATM implied volatility as a decimal (0.35 = 35%), or None.

    IMPORTANT: yfinance's own `impliedVolatility` field is currently unreliable —
    it returns degenerate / quantized garbage (≈0, or binary fractions like
    1/32, 1/16) for many strikes. We therefore IGNORE that field entirely and
    instead solve implied volatility ourselves from option market prices with
    Black-Scholes, which yields stable, sane values.

    Logic:
      1. Pick the option expiry closest to ~180 days out (fall back to the next
         closest, up to MAX_EXPIRY_ATTEMPTS, if a chain yields nothing usable).
      2. For the NEAR_STRIKES strikes nearest the price on each of calls/puts,
         take the option mid price (bid/ask midpoint; lastPrice if no quotes).
      3. Invert Black-Scholes for each to get its implied vol.
      4. Discard results outside MIN_VALID_IV..MAX_VALID_IV and return the
         median of what remains.
    Returns None if no expiry produces a valid near-the-money IV.
    """
    try:
        expiries = tk.options
    except Exception:
        return None
    if not expiries:
        return None

    today = dt.date.today()

    def days_off(exp: str) -> int:
        d = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        return abs(((d - today).days) - TARGET_IV_DAYS)

    ranked = sorted(expiries, key=days_off)

    for expiry in ranked[:MAX_EXPIRY_ATTEMPTS]:
        exp_date = dt.datetime.strptime(expiry, "%Y-%m-%d").date()
        years = (exp_date - today).days / 365.0
        if years <= 0:
            continue
        try:
            chain = tk.option_chain(expiry)
        except Exception:
            continue

        ivs = []
        for kind, frame in (("c", chain.calls), ("p", chain.puts)):
            if frame is None or frame.empty or "strike" not in frame:
                continue
            near = frame.assign(_d=(frame["strike"] - price).abs()).nsmallest(
                NEAR_STRIKES, "_d"
            )
            for _, opt in near.iterrows():
                mid = option_mid_price(opt)
                if mid is None:
                    continue
                iv = implied_vol(kind, price, float(opt["strike"]), years, mid)
                if iv is not None and MIN_VALID_IV < iv < MAX_VALID_IV:
                    ivs.append(iv)

        if ivs:
            return statistics.median(ivs)

    return None


def option_mid_price(opt) -> Optional[float]:
    """Best available option price: bid/ask midpoint, else lastPrice."""
    bid = opt.get("bid")
    ask = opt.get("ask")
    if bid and ask and bid > 0 and ask > 0:
        return (float(bid) + float(ask)) / 2.0
    last = opt.get("lastPrice")
    if last and last > 0:
        return float(last)
    return None


def _bs_price(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes price of a European call ('c') or put ('p'), no dividends."""
    import math

    if sigma <= 0 or T <= 0:
        return max(0.0, (S - K) if kind == "c" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    norm_cdf = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    if kind == "c":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def implied_vol(
    kind: str, S: float, K: float, T: float, market_price: float
) -> Optional[float]:
    """Solve implied volatility from an option's market price via bisection.

    Returns the volatility (decimal) that makes the Black-Scholes price match
    `market_price`, or None if inputs are invalid. The MIN/MAX band filter
    upstream rejects the boundary results you get for sub-intrinsic prices.
    """
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    lo, hi = 1e-4, 5.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _bs_price(kind, S, K, T, RISK_FREE_RATE, mid) > market_price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def days_to_earnings(tk: yf.Ticker) -> Optional[int]:
    """Days until the next earnings date, or None if unknown."""
    today = dt.date.today()
    # Prefer get_earnings_dates; fall back to .calendar.
    try:
        ed = tk.get_earnings_dates(limit=8)
        if ed is not None and not ed.empty:
            future = [d.date() for d in ed.index.to_pydatetime() if d.date() >= today]
            if future:
                return (min(future) - today).days
    except Exception:
        pass
    try:
        cal = tk.calendar
        if isinstance(cal, dict):
            vals = cal.get("Earnings Date") or []
            future = [d for d in vals if isinstance(d, dt.date) and d >= today]
            if future:
                return (min(future) - today).days
    except Exception:
        pass
    return None


def pct(target: Optional[float], price: float) -> Optional[float]:
    """Upside percent of a target vs price, or None."""
    if target is None or price <= 0:
        return None
    return (target - price) / price * 100.0


def score_row(row: dict) -> dict:
    """Fetch + score one ticker. Always returns a dict (status=fetch_failed on error)."""
    ticker = row["ticker"]
    tier = row["tier"]
    theme = row["theme"]
    t = THRESHOLDS.get(tier, THRESHOLDS["safe"])

    base = {
        "ticker": ticker,
        "tier": tier,
        "theme": theme,
        "price": None,
        "market_cap_b": None,
        "mean_target": None,
        "mean_upside_pct": None,
        "low_upside_pct": None,
        "high_upside_pct": None,
        "iv_pct": None,
        "iv_adj_score": None,
        "analyst_count": None,
        "above_50d_ma": None,
        "days_to_earnings": None,
        "status": STATUS_FAILED,
    }

    try:
        tk = yf.Ticker(ticker)
        info = fetch_info(tk) or {}

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            return base  # cannot score without a price
        price = float(price)

        market_cap = info.get("marketCap")
        market_cap_b = float(market_cap) / 1e9 if market_cap else None

        mean_target = info.get("targetMeanPrice")
        low_target = info.get("targetLowPrice")
        high_target = info.get("targetHighPrice")
        analyst_count = info.get("numberOfAnalystOpinions")

        # 50-day MA from 3mo history
        ma50 = None
        hist = fetch_history(tk)
        if hist is not None and not hist.empty and "Close" in hist:
            ma_series = hist["Close"].rolling(50).mean().dropna()
            if not ma_series.empty:
                ma50 = float(ma_series.iloc[-1])

        iv = compute_iv(tk, price)  # decimal or None
        dte = days_to_earnings(tk)

        mean_upside = pct(mean_target, price)
        low_upside = pct(low_target, price)
        high_upside = pct(high_target, price)
        iv_pct = iv * 100 if iv is not None else None
        iv_adj = (mean_upside / iv_pct) if (iv_pct and mean_upside is not None) else None
        above_ma = (price > ma50) if ma50 is not None else None
        earnings_soon = dte is not None and 0 <= dte <= t["earnings_window_days"]

        # status
        if iv_pct is None:
            status = STATUS_NO_OPTIONS
        else:
            non_earnings_pass = all(
                [
                    iv_adj is not None and iv_adj > t["min_score"],
                    mean_upside is not None and mean_upside > t["min_upside_pct"],
                    analyst_count is not None and analyst_count >= t["min_analysts"],
                    market_cap_b is not None and market_cap_b > t["min_cap_b"],
                    above_ma is True,
                ]
            )
            if non_earnings_pass and earnings_soon:
                status = STATUS_DEFERRED
            elif non_earnings_pass and not earnings_soon:
                status = STATUS_FLAGGED
            else:
                status = STATUS_PASSED

        base.update(
            price=round(price, 2),
            market_cap_b=round(market_cap_b, 2) if market_cap_b else None,
            mean_target=round(float(mean_target), 2) if mean_target else None,
            mean_upside_pct=round(mean_upside, 2) if mean_upside is not None else None,
            low_upside_pct=round(low_upside, 2) if low_upside is not None else None,
            high_upside_pct=round(high_upside, 2) if high_upside is not None else None,
            iv_pct=round(iv_pct, 2) if iv_pct is not None else None,
            iv_adj_score=round(iv_adj, 3) if iv_adj is not None else None,
            analyst_count=int(analyst_count) if analyst_count else None,
            above_50d_ma=above_ma,
            days_to_earnings=dte,
            status=status,
        )
        return base
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {ticker}: fetch failed: {exc}")
        return base


def main() -> None:
    with open(CSV_PATH, newline="") as f:
        watchlist = [{k: v.strip() for k, v in r.items()} for r in csv.DictReader(f)]

    rows = []
    for i, row in enumerate(watchlist, 1):
        print(f"[{i}/{len(watchlist)}] {row['ticker']} ...")
        rows.append(score_row(row))
        time.sleep(SLEEP_BETWEEN_CALLS)

    failed = sum(1 for r in rows if r["status"] == STATUS_FAILED)
    flagged = sum(1 for r in rows if r["status"] == STATUS_FLAGGED)
    deferred = sum(1 for r in rows if r["status"] == STATUS_DEFERRED)
    partial = (failed / len(rows)) > PARTIAL_FAIL_RATIO if rows else False

    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "as_of_date": now.date().isoformat(),
        "scanned": len(rows),
        "flagged": flagged,
        "deferred": deferred,
        "failed": failed,
        "partial_warning": partial,
        "thresholds": THRESHOLDS,
        "rows": rows,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as out:
        json.dump(payload, out, indent=2)

    print(
        f"\nWrote {OUT_PATH}: {len(rows)} scanned, {flagged} flagged, "
        f"{deferred} deferred, {failed} failed"
        + (" [PARTIAL — possible rate limiting]" if partial else "")
    )


if __name__ == "__main__":
    main()
