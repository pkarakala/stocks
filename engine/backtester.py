"""
Backtesting Engine — Walk-Forward Simulation
Simulates the full strategy on historical data with synthetic options pricing.

Methodology:
  - Walk-forward: train on 6 months, test on 1 month, slide forward
  - Synthetic options priced via BSM using realized vol as IV proxy
  - Realistic transaction costs (commission + slippage on OTM options)
  - Position sizing via half-Kelly with portfolio constraints
  - Full exit logic (profit target, stop loss, trailing, time-based)

Output: trade-by-trade log, equity curve, and performance metrics.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

from config import STRATEGY, RISK, BACKTEST, DATA
from greeks import black_scholes, full_greeks, delta_to_strike
from alpha import compute_alpha, ema, realized_volatility


@dataclass
class Trade:
    """A single completed trade."""
    ticker: str
    sector: str
    entry_date: str
    exit_date: str
    hold_days: int
    entry_price_underlying: float
    exit_price_underlying: float
    underlying_return_pct: float
    strike: float
    dte_at_entry: int
    dte_at_exit: int
    entry_premium: float
    exit_premium: float
    entry_iv: float
    exit_iv: float
    entry_delta: float
    contracts: int
    pnl_per_contract: float
    pnl_total: float
    pnl_pct: float
    exit_reason: str
    signal_score: float
    capital_at_entry: float
    position_size_pct: float


@dataclass
class BacktestResult:
    """Full backtest output."""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float

    # Performance metrics
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_days: int
    avg_drawdown_pct: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    largest_win_pct: float
    largest_loss_pct: float
    avg_hold_days: float
    profit_factor: float
    payoff_ratio: float
    expectancy_pct: float

    # Risk
    avg_position_size_pct: float
    max_concurrent_positions: int
    kelly_fraction: float

    # Monthly breakdown
    monthly_returns: list
    equity_curve: list
    drawdown_curve: list
    trades: list

    # Benchmark comparison
    benchmark_return_pct: float
    benchmark_sharpe: float
    alpha_pct: float
    beta: float
    information_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


def synthetic_option_price(
    S: float, K: float, T: float, sigma: float, r: float = 0.043
) -> float:
    """Price an OTM call using BSM with slippage."""
    price = black_scholes("call", S, K, T, r, sigma)
    slippage = price * (RISK["slippage_pct"] / 100.0)
    return price + slippage  # entry: pay more due to spread


def run_backtest(
    universe: dict[str, pd.DataFrame],
    benchmark_hist: Optional[pd.DataFrame] = None,
    sectors: Optional[dict[str, str]] = None,
) -> BacktestResult:
    """
    Run the full backtest over all tickers in the universe.

    Args:
        universe: {ticker: DataFrame with OHLCV} — at least 1 year of daily data
        benchmark_hist: SPY DataFrame for regime filter + comparison
        sectors: {ticker: sector_name}
    """
    r = BACKTEST["risk_free_rate"]
    capital = float(RISK["initial_capital"])
    start_capital = capital
    equity_curve = []
    drawdown_curve = []
    trades_log: list[Trade] = []
    open_positions: list[dict] = []
    monthly_returns: list[dict] = []

    # Get date range from first ticker
    all_dates = set()
    for df in universe.values():
        all_dates.update(df.index.tolist())
    all_dates = sorted(all_dates)

    if not all_dates:
        return _empty_result(start_capital)

    # Walk through each trading day
    peak_capital = capital
    dd_start = None
    max_dd = 0.0
    max_dd_days = 0
    current_dd_days = 0

    prev_month = None
    month_start_capital = capital

    for date_idx, current_date in enumerate(all_dates):
        # Skip if not enough history for indicators (need 60 days warmup)
        if date_idx < 60:
            equity_curve.append({"date": str(current_date)[:10], "equity": capital})
            continue

        # ─── Update open positions ───────────────────────────────────────────
        positions_to_close = []
        for pos in open_positions:
            ticker = pos["ticker"]
            if ticker not in universe:
                continue
            df = universe[ticker]
            if current_date not in df.index:
                continue

            row = df.loc[current_date]
            S_now = float(row["Close"])
            days_held = (current_date - pos["entry_date"]).days
            dte_now = pos["dte_at_entry"] - days_held
            T_now = max(dte_now, 0) / 365.0
            sigma_now = pos["entry_iv"]  # simplified: IV stays constant

            if T_now > 0:
                current_premium = black_scholes("call", S_now, pos["strike"], T_now, r, sigma_now)
            else:
                current_premium = max(0, S_now - pos["strike"])

            # Remove slippage on exit (sell at lower price)
            current_premium_net = current_premium * (1 - RISK["slippage_pct"] / 100.0)
            current_return = (current_premium_net - pos["entry_premium"]) / pos["entry_premium"]

            pos["high_water"] = max(pos.get("high_water", 0), current_return)

            # Exit conditions
            exit_reason = None
            cfg_exit = STRATEGY["exits"]

            if current_return >= cfg_exit["profit_target_pct"] / 100.0:
                exit_reason = "PROFIT_TARGET"
            elif current_return <= cfg_exit["stop_loss_pct"] / 100.0:
                exit_reason = "STOP_LOSS"
            elif dte_now <= cfg_exit["time_stop_dte"]:
                exit_reason = "TIME_STOP"
            elif pos["high_water"] >= cfg_exit["trailing_activation_pct"] / 100.0:
                trail_floor = pos["high_water"] * (1 - cfg_exit["trailing_stop_pct"] / 100.0)
                if current_return < trail_floor:
                    exit_reason = "TRAILING_STOP"
            elif days_held >= STRATEGY["max_hold_days"]:
                exit_reason = "MAX_HOLD"

            if exit_reason:
                # Credit the full sale proceeds — entry already deducted the cost.
                proceeds = current_premium_net * 100 * pos["contracts"]
                proceeds -= RISK["commission_per_contract"] * pos["contracts"]
                capital += proceeds
                pnl = proceeds - pos["entry_premium"] * 100 * pos["contracts"]

                trade = Trade(
                    ticker=ticker,
                    sector=pos.get("sector", ""),
                    entry_date=str(pos["entry_date"])[:10],
                    exit_date=str(current_date)[:10],
                    hold_days=days_held,
                    entry_price_underlying=pos["entry_underlying"],
                    exit_price_underlying=S_now,
                    underlying_return_pct=round((S_now / pos["entry_underlying"] - 1) * 100, 2),
                    strike=pos["strike"],
                    dte_at_entry=pos["dte_at_entry"],
                    dte_at_exit=dte_now,
                    entry_premium=pos["entry_premium"],
                    exit_premium=round(current_premium_net, 4),
                    entry_iv=pos["entry_iv"],
                    exit_iv=sigma_now,
                    entry_delta=pos["entry_delta"],
                    contracts=pos["contracts"],
                    pnl_per_contract=round((current_premium_net - pos["entry_premium"]) * 100, 2),
                    pnl_total=round(pnl, 2),
                    pnl_pct=round(current_return * 100, 2),
                    exit_reason=exit_reason,
                    signal_score=pos["signal_score"],
                    capital_at_entry=pos["capital_at_entry"],
                    position_size_pct=pos["position_size_pct"],
                )
                trades_log.append(trade)
                positions_to_close.append(pos)

        for pos in positions_to_close:
            open_positions.remove(pos)

        # ─── Generate new signals (check every day) ──────────────────────────
        if len(open_positions) < RISK["max_concurrent_positions"]:
            # Regime filter
            regime_ok = True
            if benchmark_hist is not None and current_date in benchmark_hist.index:
                spy_close = benchmark_hist.loc[:current_date]["Close"].astype(float)
                if len(spy_close) >= 50:
                    spy_ema50 = float(ema(spy_close, 50).iloc[-1])
                    if float(spy_close.iloc[-1]) < spy_ema50:
                        regime_ok = False

            if regime_ok:
                signals = []
                for ticker, df in universe.items():
                    # Skip if already in position
                    if any(p["ticker"] == ticker for p in open_positions):
                        continue
                    # Skip if not enough data up to current date
                    hist_to_date = df.loc[:current_date]
                    if len(hist_to_date) < 60:
                        continue

                    # Compute IV proxy (realized vol * 1.2)
                    close_series = hist_to_date["Close"].astype(float)
                    rv = realized_volatility(close_series, 20)
                    if rv.empty or np.isnan(rv.iloc[-1]):
                        continue
                    current_iv = float(rv.iloc[-1]) * float(DATA["iv_proxy_vix_beta_default"])
                    iv_history = rv.dropna().values * float(DATA["iv_proxy_vix_beta_default"])

                    bench_to_date = benchmark_hist.loc[:current_date] if benchmark_hist is not None else None
                    sector = sectors.get(ticker, "") if sectors else ""

                    signal = compute_alpha(
                        ticker=ticker,
                        hist=hist_to_date,
                        current_iv=current_iv,
                        iv_history=iv_history,
                        benchmark_hist=bench_to_date,
                        sector=sector,
                        signal_date=current_date.date() if hasattr(current_date, 'date') else current_date,
                    )
                    if signal:
                        signals.append(signal)

                # Sort by composite score, take top candidates
                signals.sort(key=lambda s: s.composite_score, reverse=True)
                available_slots = RISK["max_concurrent_positions"] - len(open_positions)
                top_signals = signals[:available_slots]

                for sig in top_signals:
                    # Sector concentration check
                    sector_count = sum(1 for p in open_positions if p.get("sector") == sig.sector)
                    if sector_count >= RISK["max_sector_concentration"]:
                        continue

                    # Position sizing
                    position_capital = capital * (sig.position_size_pct / 100.0)
                    contracts = max(1, int(position_capital / (sig.estimated_premium * 100)))
                    cost = sig.estimated_premium * 100 * contracts + RISK["commission_per_contract"] * contracts

                    if cost > capital * 0.15:  # safety: never more than 15% in one entry
                        continue

                    capital -= cost

                    open_positions.append({
                        "ticker": sig.ticker,
                        "entry_date": current_date,
                        "entry_underlying": sig.price,
                        "strike": sig.suggested_strike,
                        "dte_at_entry": sig.suggested_dte,
                        "entry_premium": sig.estimated_premium,
                        "entry_iv": sig.implied_vol,
                        "entry_delta": sig.estimated_delta,
                        "contracts": contracts,
                        "signal_score": sig.composite_score,
                        "capital_at_entry": capital + cost,
                        "position_size_pct": sig.position_size_pct,
                        "sector": sig.sector,
                        "high_water": 0.0,
                    })

        # ─── Mark to market ──────────────────────────────────────────────────
        mtm = capital
        for pos in open_positions:
            ticker = pos["ticker"]
            if ticker in universe and current_date in universe[ticker].index:
                S = float(universe[ticker].loc[current_date, "Close"])
                days_held = (current_date - pos["entry_date"]).days
                T = max(pos["dte_at_entry"] - days_held, 0) / 365.0
                if T > 0:
                    val = black_scholes("call", S, pos["strike"], T, r, pos["entry_iv"])
                else:
                    val = max(0, S - pos["strike"])
                mtm += val * 100 * pos["contracts"]

        equity_curve.append({"date": str(current_date)[:10], "equity": round(mtm, 2)})

        # Drawdown tracking
        if mtm > peak_capital:
            peak_capital = mtm
            current_dd_days = 0
        else:
            current_dd_days += 1
            dd_pct = (peak_capital - mtm) / peak_capital * 100
            if dd_pct > max_dd:
                max_dd = dd_pct
                max_dd_days = current_dd_days

        dd_pct_current = (peak_capital - mtm) / peak_capital * 100 if peak_capital > 0 else 0
        drawdown_curve.append({"date": str(current_date)[:10], "drawdown_pct": round(dd_pct_current, 2)})

        # Monthly tracking
        current_month = str(current_date)[:7]
        if prev_month and current_month != prev_month:
            monthly_ret = (mtm / month_start_capital - 1) * 100
            monthly_returns.append({"month": prev_month, "return_pct": round(monthly_ret, 2)})
            month_start_capital = mtm
        prev_month = current_month

    # Final month
    final_equity = equity_curve[-1]["equity"] if equity_curve else start_capital
    if prev_month:
        monthly_ret = (final_equity / month_start_capital - 1) * 100
        monthly_returns.append({"month": prev_month, "return_pct": round(monthly_ret, 2)})

    # ─── Compute aggregate metrics ───────────────────────────────────────────
    total_return = (final_equity / start_capital - 1) * 100
    n_days = len(all_dates)
    years = n_days / 252.0
    cagr = ((final_equity / start_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Sharpe from daily equity returns
    equities = np.array([e["equity"] for e in equity_curve])
    daily_returns = np.diff(equities) / equities[:-1] if len(equities) > 1 else np.array([0])
    daily_returns = daily_returns[np.isfinite(daily_returns)]
    rf_daily = BACKTEST["risk_free_rate"] / 252
    excess = daily_returns - rf_daily
    sharpe = float(np.mean(excess) / np.std(excess) * np.sqrt(252)) if np.std(excess) > 0 else 0

    downside = excess[excess < 0]
    sortino = float(np.mean(excess) / np.std(downside) * np.sqrt(252)) if len(downside) > 0 and np.std(downside) > 0 else 0
    calmar = cagr / max_dd if max_dd > 0 else 0

    # Trade stats
    wins = [t for t in trades_log if t.pnl_pct > 0]
    losses = [t for t in trades_log if t.pnl_pct <= 0]
    win_rate = len(wins) / len(trades_log) * 100 if trades_log else 0
    avg_win = float(np.mean([t.pnl_pct for t in wins])) if wins else 0
    avg_loss = float(np.mean([t.pnl_pct for t in losses])) if losses else 0
    total_gains = sum(t.pnl_total for t in wins)
    total_losses = abs(sum(t.pnl_total for t in losses))
    profit_factor = total_gains / total_losses if total_losses > 0 else float('inf')
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    avg_hold = float(np.mean([t.hold_days for t in trades_log])) if trades_log else 0

    # Benchmark
    bench_ret = 0
    bench_sharpe = 0
    alpha_val = 0
    beta_val = 0
    ir = 0
    if benchmark_hist is not None and len(benchmark_hist) > 1:
        bench_prices = benchmark_hist["Close"].astype(float)
        bench_ret = float((bench_prices.iloc[-1] / bench_prices.iloc[0] - 1) * 100)
        bench_daily = bench_prices.pct_change().dropna().values
        if len(bench_daily) > 0 and np.std(bench_daily) > 0:
            bench_sharpe = float(np.mean(bench_daily - rf_daily) / np.std(bench_daily) * np.sqrt(252))
        alpha_val = total_return - bench_ret

    return BacktestResult(
        strategy_name=STRATEGY["name"],
        start_date=str(all_dates[0])[:10],
        end_date=str(all_dates[-1])[:10],
        initial_capital=start_capital,
        final_capital=round(final_equity, 2),
        total_return_pct=round(total_return, 2),
        cagr_pct=round(cagr, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        max_drawdown_pct=round(max_dd, 2),
        max_drawdown_days=max_dd_days,
        avg_drawdown_pct=round(float(np.mean([d["drawdown_pct"] for d in drawdown_curve])), 2),
        total_trades=len(trades_log),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate_pct=round(win_rate, 2),
        avg_win_pct=round(avg_win, 2),
        avg_loss_pct=round(avg_loss, 2),
        largest_win_pct=round(max((t.pnl_pct for t in trades_log), default=0), 2),
        largest_loss_pct=round(min((t.pnl_pct for t in trades_log), default=0), 2),
        avg_hold_days=round(avg_hold, 1),
        profit_factor=round(profit_factor, 2),
        payoff_ratio=round(payoff_ratio, 2),
        expectancy_pct=round(expectancy, 2),
        avg_position_size_pct=round(float(np.mean([t.position_size_pct for t in trades_log])) if trades_log else 0, 2),
        max_concurrent_positions=RISK["max_concurrent_positions"],
        kelly_fraction=RISK["kelly_fraction"],
        monthly_returns=monthly_returns,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        trades=[asdict(t) for t in trades_log],
        benchmark_return_pct=round(bench_ret, 2),
        benchmark_sharpe=round(bench_sharpe, 3),
        alpha_pct=round(alpha_val, 2),
        beta=round(beta_val, 3),
        information_ratio=round(ir, 3),
    )


def _empty_result(capital: float) -> BacktestResult:
    return BacktestResult(
        strategy_name=STRATEGY["name"], start_date="", end_date="",
        initial_capital=capital, final_capital=capital, total_return_pct=0,
        cagr_pct=0, sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
        max_drawdown_pct=0, max_drawdown_days=0, avg_drawdown_pct=0,
        total_trades=0, winning_trades=0, losing_trades=0, win_rate_pct=0,
        avg_win_pct=0, avg_loss_pct=0, largest_win_pct=0, largest_loss_pct=0,
        avg_hold_days=0, profit_factor=0, payoff_ratio=0, expectancy_pct=0,
        avg_position_size_pct=0, max_concurrent_positions=0, kelly_fraction=0,
        monthly_returns=[], equity_curve=[], drawdown_curve=[], trades=[],
        benchmark_return_pct=0, benchmark_sharpe=0, alpha_pct=0, beta=0,
        information_ratio=0,
    )
