"""
Daily Signal Pipeline — Entry Point
Runs nightly (GitHub Actions or local cron). Generates:
  - Daily BUY / SELL / HOLD actions (persistent paper portfolio)
  - Ranked alpha signals with factor decomposition
  - Per-ticker explorer data (quant stats + plain-English summary)
  - Monte Carlo simulations for top signals
  - Rolling 2-year backtest

Output: data/latest.json (consumed by the console)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from config import DATA, OUTPUT_DIR, WATCHLIST_PATH, STRATEGY, RISK, MONTE_CARLO
from alpha import compute_alpha, realized_volatility, ema, rsi as rsi_fn
from monte_carlo import simulate_trade
from backtester import run_backtest
from portfolio import evaluate_positions, open_new_positions, portfolio_summary


def load_watchlist() -> list[dict]:
    path = Path(WATCHLIST_PATH)
    with open(path, newline="") as f:
        return [{k: v.strip() for k, v in r.items()} for r in csv.DictReader(f)]


def fetch_universe(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """Batch-fetch OHLCV for all tickers."""
    print(f"Fetching {len(tickers)} tickers ({period} history)...")
    data = yf.download(
        " ".join(tickers),
        period=period,
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )

    universe = {}
    for ticker in tickers:
        try:
            df = data if len(tickers) == 1 else data[ticker]
            if df is not None and not df.empty and len(df) > 60:
                df = df.dropna(subset=["Close"])
                universe[ticker] = df
        except (KeyError, TypeError):
            continue

    print(f"  Got data for {len(universe)}/{len(tickers)} tickers")
    return universe


def plain_english_summary(t: dict) -> str:
    """One-paragraph, no-jargon explanation of a ticker's current state."""
    parts = []
    trend = "moving up" if t["above_trend"] else "moving down"
    parts.append(f"{t['ticker']} is {trend} — it closed at ${t['price']:.2f}.")

    if t["pct_20d"] > 5:
        parts.append(f"It's gained {t['pct_20d']:.0f}% over the past month, which is strong.")
    elif t["pct_20d"] > 0:
        parts.append(f"It's up a modest {t['pct_20d']:.1f}% over the past month.")
    else:
        parts.append(f"It's down {abs(t['pct_20d']):.1f}% over the past month.")

    if t["rsi"] > 70:
        parts.append("Warning: it's climbed fast recently and may be due for a breather (overbought).")
    elif t["rsi"] > 55:
        parts.append("Buying pressure is healthy but not overheated — the zone where trends tend to continue.")
    elif t["rsi"] < 40:
        parts.append("Buying interest is weak right now.")

    if t["iv_rank"] < 30:
        parts.append("Options on it are cheap relative to the past year — good time to be a buyer of calls if the trend holds.")
    elif t["iv_rank"] > 60:
        parts.append("Options are expensive right now — the market is charging a premium, which works against call buyers.")

    if t["volume_ratio"] > 1.5:
        parts.append(f"Trading volume is {t['volume_ratio']:.1f}x normal — big money is active in this name.")

    if t["has_signal"]:
        parts.append("✅ VERDICT: This one passes our screen today — see the trade card for exact strike and size.")
    else:
        parts.append(f"VERDICT: Not a buy today — {t['fail_reason']}.")

    return " ".join(parts)


def build_ticker_explorer(
    universe: dict, signals_by_ticker: dict, sectors: dict, tiers: dict,
    benchmark_hist: pd.DataFrame | None,
) -> list[dict]:
    """Per-ticker quant snapshot + plain-English summary for the Explorer view."""
    out = []
    for ticker, df in universe.items():
        try:
            close = df["Close"].astype(float)
            high = df["High"].astype(float)
            low = df["Low"].astype(float)
            volume = df["Volume"].astype(float)
            price = float(close.iloc[-1])

            ema9 = float(ema(close, 9).iloc[-1])
            ema21 = float(ema(close, 21).iloc[-1])
            ema50 = float(ema(close, 50).iloc[-1])
            rsi_val = float(rsi_fn(close, 14).iloc[-1])
            rv = realized_volatility(close, 20)
            rv_val = float(rv.iloc[-1]) if not np.isnan(rv.iloc[-1]) else 0.30
            iv_val = rv_val * DATA["iv_proxy_vix_beta_default"]
            iv_hist = rv.dropna().values * DATA["iv_proxy_vix_beta_default"]
            ivr = 50.0
            if len(iv_hist) > 20:
                lo, hi = float(np.nanmin(iv_hist)), float(np.nanmax(iv_hist))
                ivr = ((iv_val - lo) / (hi - lo) * 100) if hi > lo else 50.0

            avg_vol = float(volume.iloc[-20:].mean())
            vol_ratio = float(volume.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0

            pct_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) > 1 else 0
            pct_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0
            pct_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

            sig = signals_by_ticker.get(ticker)
            above_trend = price > ema50

            # Why it failed the screen (plain English)
            fail_reason = ""
            if not sig:
                if ema9 <= ema21:
                    fail_reason = "its short-term trend hasn't turned up yet"
                elif rsi_val > 78:
                    fail_reason = "it's too overheated right now — chasing here is how you buy tops"
                elif ivr > 60:
                    fail_reason = "its options are too expensive to buy"
                else:
                    fail_reason = "its overall momentum score is below our bar"

            # 90-day sparkline (weekly samples)
            spark = [round(float(x), 2) for x in close.iloc[-90::5].tolist()]

            entry = {
                "ticker": ticker,
                "sector": sectors.get(ticker, ""),
                "tier": tiers.get(ticker, ""),
                "price": round(price, 2),
                "pct_1d": round(pct_1d, 2),
                "pct_5d": round(pct_5d, 2),
                "pct_20d": round(pct_20d, 2),
                "ema9": round(ema9, 2),
                "ema21": round(ema21, 2),
                "ema50": round(ema50, 2),
                "above_trend": above_trend,
                "rsi": round(rsi_val, 1),
                "iv_rank": round(ivr, 1),
                "implied_vol": round(iv_val, 4),
                "realized_vol": round(rv_val, 4),
                "volume_ratio": round(vol_ratio, 2),
                "has_signal": sig is not None,
                "signal_score": sig.composite_score if sig else None,
                "fail_reason": fail_reason,
                "sparkline": spark,
            }
            entry["summary"] = plain_english_summary(entry)
            out.append(entry)
        except Exception as exc:
            print(f"  ! explorer failed for {ticker}: {exc}")
    out.sort(key=lambda t: (not t["has_signal"], -(t["signal_score"] or 0), -t["pct_20d"]))
    return out


def run_daily_pipeline():
    print("=" * 70)
    print(f"  QUANT CONSOLE — Daily Pipeline Run")
    print(f"  {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    watchlist = load_watchlist()
    tickers = [r["ticker"] for r in watchlist]
    sectors = {r["ticker"]: r.get("theme", "") for r in watchlist}
    tiers = {r["ticker"]: r.get("tier", "core") for r in watchlist}

    universe = fetch_universe(tickers + ["SPY", "QQQ", "^VIX"], period=DATA["history_period"])
    benchmark_hist = universe.pop("SPY", None)
    universe.pop("QQQ", None)
    vix_hist = universe.pop("^VIX", None)

    vix_level = None
    if vix_hist is not None and not vix_hist.empty:
        vix_level = float(vix_hist["Close"].iloc[-1])
        print(f"\n  VIX: {vix_level:.1f}")

    regime_ok = True
    regime_reason = "Market trend is up and volatility is calm — good conditions for this strategy."
    if vix_level and vix_level > RISK["regime_filter"]["vix_ceiling"]:
        regime_ok = False
        regime_reason = f"VIX is {vix_level:.0f} (fear gauge above {RISK['regime_filter']['vix_ceiling']}) — options are overpriced and markets are jumpy. Sitting out new trades."

    if benchmark_hist is not None and len(benchmark_hist) > 50:
        spy_close = benchmark_hist["Close"].astype(float)
        spy_ema50 = float(ema(spy_close, 50).iloc[-1])
        spy_price = float(spy_close.iloc[-1])
        if spy_price < spy_ema50:
            regime_ok = False
            regime_reason = "The overall market (S&P 500) is below its 50-day trend line — most momentum trades fail in this environment. Sitting out new trades."

    # ─── Signals ─────────────────────────────────────────────────────────────
    print(f"\n  Scanning {len(universe)} tickers...")
    signals = []
    current_prices, current_ivs = {}, {}

    for ticker, df in universe.items():
        close = df["Close"].astype(float)
        current_prices[ticker] = float(close.iloc[-1])
        rv = realized_volatility(close, 20)
        if rv.empty or np.isnan(rv.iloc[-1]):
            continue
        current_iv = float(rv.iloc[-1]) * DATA["iv_proxy_vix_beta_default"]
        current_ivs[ticker] = current_iv
        iv_history = rv.dropna().values * DATA["iv_proxy_vix_beta_default"]

        signal = compute_alpha(
            ticker=ticker, hist=df, current_iv=current_iv, iv_history=iv_history,
            benchmark_hist=benchmark_hist, sector=sectors.get(ticker, ""),
        )
        if signal:
            signals.append(signal)

    signals.sort(key=lambda s: s.composite_score, reverse=True)
    signals_by_ticker = {s.ticker: s for s in signals}
    print(f"  Found {len(signals)} signals")

    # ─── Portfolio: sells first, then buys ───────────────────────────────────
    print("\n  Updating paper portfolio...")
    sells, holds = evaluate_positions(current_prices, current_ivs)
    buys = open_new_positions(signals if regime_ok else [])
    port = portfolio_summary()
    print(f"    {len(buys)} buys, {len(sells)} sells, {len(holds)} holds")
    print(f"    Unrealized P&L: ${port['unrealized_pnl']:+,.0f} · Realized: ${port['realized_pnl']:+,.0f}")

    # ─── Explorer data ───────────────────────────────────────────────────────
    print("\n  Building ticker explorer...")
    explorer = build_ticker_explorer(universe, signals_by_ticker, sectors, tiers, benchmark_hist)

    # ─── Monte Carlo on top signals ──────────────────────────────────────────
    print(f"\n  Monte Carlo ({MONTE_CARLO['n_simulations']:,} paths each)...")
    simulations = []
    for sig in signals[:10]:
        sim = simulate_trade(
            ticker=sig.ticker, S0=sig.price, strike=sig.suggested_strike,
            entry_premium=sig.estimated_premium, sigma=sig.implied_vol,
            dte=sig.suggested_dte, n_paths=MONTE_CARLO["n_simulations"],
        )
        simulations.append(sim)

    # ─── Backtest ────────────────────────────────────────────────────────────
    print("\n  Running 2-year backtest...")
    backtest_result = run_backtest(universe, benchmark_hist, sectors)
    print(f"    Return: {backtest_result.total_return_pct:+.1f}% · Sharpe: {backtest_result.sharpe_ratio:.2f} · Trades: {backtest_result.total_trades}")

    # ─── Output ──────────────────────────────────────────────────────────────
    output = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "date": dt.date.today().isoformat(),
        "regime": {
            "status": "BULLISH" if regime_ok else "BEARISH",
            "vix": vix_level,
            "new_entries_allowed": regime_ok,
            "explanation": regime_reason,
        },
        "actions": {
            "buys": buys,
            "sells": sells,
            "holds": holds,
        },
        "portfolio": port,
        "signals": [s.to_dict() for s in signals],
        "explorer": explorer,
        "simulations": [asdict(s) for s in simulations],
        "backtest": backtest_result.to_dict(),
        "strategy_config": {
            "name": STRATEGY["name"],
            "target_return_pct": STRATEGY["target_return_pct"],
            "max_hold_days": STRATEGY["max_hold_days"],
            "delta_range": [STRATEGY["option_selection"]["min_delta"], STRATEGY["option_selection"]["max_delta"]],
            "dte_range": [STRATEGY["option_selection"]["target_dte_min"], STRATEGY["option_selection"]["target_dte_max"]],
        },
        "universe_size": len(universe),
        "signal_count": len(signals),
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "latest.json"), "w") as f:
        json.dump(output, f, indent=2, default=str)
    with open(os.path.join(OUTPUT_DIR, f"{dt.date.today().isoformat()}.json"), "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Wrote data/latest.json")
    print("=" * 70)


if __name__ == "__main__":
    run_daily_pipeline()
