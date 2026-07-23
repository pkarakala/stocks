"""
Monte Carlo Simulation Engine
Student-t jump-diffusion model for underlying paths + BSM repricing.

Models:
  - GBM (baseline, Gaussian)
  - Student-t fat tails (Praetz 1972, df=4-6)
  - Merton jump diffusion (Bates 1996)
  - Student-t + jumps (hybrid, our default)

Outputs:
  - P&L distribution across N paths with early-exit logic
  - VaR/CVaR at multiple confidence levels
  - Probability of hitting 40% target
  - Optimal exit timing distribution
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import t as student_t_dist

from config import MONTE_CARLO, STRATEGY, RISK
from greeks import black_scholes


@dataclass
class SimulationResult:
    """Full Monte Carlo output for a single trade setup."""
    ticker: str
    n_paths: int
    model: str

    # P&L statistics
    mean_return_pct: float
    median_return_pct: float
    std_return_pct: float
    skewness: float
    kurtosis: float

    # Probabilities
    prob_profit: float
    prob_target_hit: float      # P(return >= 40%)
    prob_double: float          # P(return >= 100%)
    prob_total_loss: float      # P(return <= -90%)
    prob_stop_hit: float        # P(return <= stop_loss)

    # Risk metrics
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown_avg: float

    # Timing
    avg_hold_days: float
    median_hold_days: float
    avg_days_to_target: float   # conditional on hitting target

    # Distribution percentiles
    percentiles: dict  # {5: x, 10: x, 25: x, 50: x, 75: x, 90: x, 95: x}

    # Raw data for charting
    pnl_distribution: list     # binned histogram
    paths_sample: list         # 50 sample paths for visualization
    exit_day_distribution: list

    # Expected value
    expected_value_per_trade: float
    kelly_optimal_fraction: float
    edge_per_trade_pct: float


def simulate_paths(
    S0: float,
    sigma: float,
    mu: float = 0.0,
    T_days: int = 45,
    n_paths: int = 10_000,
    model: str = "student_t_jump",
    dt: float = 1.0 / 252.0,
) -> np.ndarray:
    """
    Generate simulated price paths for the underlying.
    Returns array of shape (n_paths, T_days + 1).
    """
    cfg = MONTE_CARLO
    n_steps = T_days

    if model == "gbm":
        Z = np.random.standard_normal((n_paths, n_steps))
    elif model == "student_t":
        df = cfg["student_t_df"]
        Z = student_t_dist.rvs(df, size=(n_paths, n_steps))
        Z = Z / np.sqrt(df / (df - 2))  # normalize to unit variance
    elif model in ("jump_diffusion", "student_t_jump"):
        df = cfg["student_t_df"]
        if model == "student_t_jump":
            Z = student_t_dist.rvs(df, size=(n_paths, n_steps))
            Z = Z / np.sqrt(df / (df - 2))
        else:
            Z = np.random.standard_normal((n_paths, n_steps))

        # Jump component (Poisson arrivals, normal jump sizes)
        jump_n = np.random.poisson(cfg["jump_intensity"] * dt, (n_paths, n_steps))
        jump_sizes = np.random.normal(
            cfg["jump_mean"], cfg["jump_std"], (n_paths, n_steps)
        ) * jump_n

        # Compensated drift
        k = math.exp(cfg["jump_mean"] + 0.5 * cfg["jump_std"]**2) - 1
        compensated_mu = mu - cfg["jump_intensity"] * k
    else:
        raise ValueError(f"Unknown model: {model}")

    drift = (mu - 0.5 * sigma**2) * dt
    if model in ("jump_diffusion", "student_t_jump"):
        drift = (compensated_mu - 0.5 * sigma**2) * dt

    diffusion = sigma * np.sqrt(dt) * Z
    log_returns = drift + diffusion

    if model in ("jump_diffusion", "student_t_jump"):
        log_returns += jump_sizes

    cumulative = np.cumsum(log_returns, axis=1)
    paths = np.column_stack([np.zeros(n_paths), cumulative])
    paths = S0 * np.exp(paths)

    return paths


def simulate_trade(
    ticker: str,
    S0: float,
    strike: float,
    entry_premium: float,
    sigma: float,
    dte: int = 42,
    r: float = 0.043,
    n_paths: int = 10_000,
    model: str = "student_t_jump",
) -> SimulationResult:
    """
    Full Monte Carlo simulation of a single OTM call trade with exit rules.
    """
    cfg_exit = STRATEGY["exits"]
    profit_target = cfg_exit["profit_target_pct"] / 100.0
    stop_loss = cfg_exit["stop_loss_pct"] / 100.0
    max_hold = min(STRATEGY["max_hold_days"], dte - cfg_exit["time_stop_dte"])

    # Estimate drift from momentum (slightly positive for selected stocks)
    mu = 0.10 / 252 * 252  # annualized ~10% drift for momentum stocks

    paths = simulate_paths(S0, sigma, mu=mu / 252, T_days=dte, n_paths=n_paths, model=model)

    # Evaluate option price at each day, apply exit rules
    pnl_pct = np.full(n_paths, np.nan)
    exit_days = np.full(n_paths, max_hold, dtype=int)
    high_water = np.zeros(n_paths)

    for day in range(1, max_hold + 1):
        still_open = np.isnan(pnl_pct)
        if not still_open.any():
            break

        T_remaining = (dte - day) / 365.0
        S_day = paths[still_open, day]

        if T_remaining <= 0:
            option_values = np.maximum(S_day - strike, 0)
        else:
            option_values = np.array([
                black_scholes("call", s, strike, T_remaining, r, sigma)
                for s in S_day
            ])

        current_return = (option_values - entry_premium) / entry_premium
        high_water[still_open] = np.maximum(high_water[still_open], current_return)

        # Check exits
        hit_target = current_return >= profit_target
        hit_stop = current_return <= stop_loss

        # Trailing stop: activated after trailing_activation_pct, stop at trailing_stop_pct of gains
        trailing_active = high_water[still_open] >= (cfg_exit["trailing_activation_pct"] / 100.0)
        trailing_floor = high_water[still_open] * (1 - cfg_exit["trailing_stop_pct"] / 100.0)
        hit_trailing = trailing_active & (current_return < trailing_floor)

        # Apply exits
        indices = np.where(still_open)[0]

        target_idx = indices[hit_target]
        stop_idx = indices[hit_stop]
        trail_idx = indices[hit_trailing & ~hit_target & ~hit_stop]

        pnl_pct[target_idx] = current_return[hit_target]
        pnl_pct[stop_idx] = current_return[hit_stop]
        pnl_pct[trail_idx] = current_return[hit_trailing & ~hit_target & ~hit_stop]

        exit_days[target_idx] = day
        exit_days[stop_idx] = day
        exit_days[trail_idx] = day

    # Close remaining at max_hold
    still_open = np.isnan(pnl_pct)
    if still_open.any():
        T_final = (dte - max_hold) / 365.0
        S_final = paths[still_open, max_hold]
        if T_final > 0:
            final_values = np.array([
                black_scholes("call", s, strike, T_final, r, sigma)
                for s in S_final
            ])
        else:
            final_values = np.maximum(S_final - strike, 0)
        pnl_pct[still_open] = (final_values - entry_premium) / entry_premium

    pnl_pct_100 = pnl_pct * 100  # convert to percentage

    # ─── Compute statistics ───────────────────────────────────────────────────
    mean_ret = float(np.mean(pnl_pct_100))
    median_ret = float(np.median(pnl_pct_100))
    std_ret = float(np.std(pnl_pct_100))

    n = len(pnl_pct_100)
    m3 = float(np.mean((pnl_pct_100 - mean_ret)**3))
    m4 = float(np.mean((pnl_pct_100 - mean_ret)**4))
    skew = m3 / (std_ret**3) if std_ret > 0 else 0
    kurt = m4 / (std_ret**4) - 3 if std_ret > 0 else 0

    prob_profit = float(np.mean(pnl_pct > 0))
    prob_target = float(np.mean(pnl_pct >= profit_target))
    prob_double = float(np.mean(pnl_pct >= 1.0))
    prob_total_loss = float(np.mean(pnl_pct <= -0.90))
    prob_stop = float(np.mean(pnl_pct <= stop_loss))

    var_95 = float(np.percentile(pnl_pct_100, 5))
    var_99 = float(np.percentile(pnl_pct_100, 1))
    tail_5 = pnl_pct_100[pnl_pct_100 <= np.percentile(pnl_pct_100, 5)]
    tail_1 = pnl_pct_100[pnl_pct_100 <= np.percentile(pnl_pct_100, 1)]
    cvar_95 = float(np.mean(tail_5)) if len(tail_5) > 0 else var_95
    cvar_99 = float(np.mean(tail_1)) if len(tail_1) > 0 else var_99

    avg_hold = float(np.mean(exit_days))
    med_hold = float(np.median(exit_days))
    target_hits = exit_days[pnl_pct >= profit_target]
    avg_days_target = float(np.mean(target_hits)) if len(target_hits) > 0 else max_hold

    # Max drawdown per path (from entry)
    max_dd = float(np.mean(np.minimum(0, pnl_pct) * 100))

    # Percentiles
    pctiles = {}
    for p in MONTE_CARLO["confidence_levels"]:
        pctiles[int(p * 100)] = round(float(np.percentile(pnl_pct_100, p * 100)), 2)

    # P&L histogram (for charting)
    hist_counts, hist_edges = np.histogram(pnl_pct_100, bins=50)
    pnl_hist = [
        {"bin_start": round(float(hist_edges[i]), 1),
         "bin_end": round(float(hist_edges[i+1]), 1),
         "count": int(hist_counts[i]),
         "pct": round(float(hist_counts[i]) / n * 100, 2)}
        for i in range(len(hist_counts))
    ]

    # Sample paths for visualization (50 paths)
    sample_idx = np.random.choice(n_paths, min(50, n_paths), replace=False)
    sample_paths = [[round(float(x), 2) for x in paths[i, :max_hold+1]] for i in sample_idx]

    # Exit day distribution
    exit_hist_counts, exit_hist_edges = np.histogram(exit_days, bins=range(0, max_hold + 2))
    exit_dist = [{"day": int(exit_hist_edges[i]), "count": int(exit_hist_counts[i])}
                 for i in range(len(exit_hist_counts))]

    # Expected value and Kelly
    ev_per_trade = mean_ret
    if prob_profit > 0 and (1 - prob_profit) > 0:
        avg_win_pct = float(np.mean(pnl_pct_100[pnl_pct > 0]))
        avg_loss_pct = float(np.mean(np.abs(pnl_pct_100[pnl_pct <= 0])))
        b = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 1
        kelly = (prob_profit * b - (1 - prob_profit)) / b
    else:
        kelly = 0.0

    edge = ev_per_trade

    return SimulationResult(
        ticker=ticker,
        n_paths=n_paths,
        model=model,
        mean_return_pct=round(mean_ret, 2),
        median_return_pct=round(median_ret, 2),
        std_return_pct=round(std_ret, 2),
        skewness=round(skew, 3),
        kurtosis=round(kurt, 3),
        prob_profit=round(prob_profit, 4),
        prob_target_hit=round(prob_target, 4),
        prob_double=round(prob_double, 4),
        prob_total_loss=round(prob_total_loss, 4),
        prob_stop_hit=round(prob_stop, 4),
        var_95=round(var_95, 2),
        var_99=round(var_99, 2),
        cvar_95=round(cvar_95, 2),
        cvar_99=round(cvar_99, 2),
        max_drawdown_avg=round(max_dd, 2),
        avg_hold_days=round(avg_hold, 1),
        median_hold_days=round(med_hold, 1),
        avg_days_to_target=round(avg_days_target, 1),
        percentiles=pctiles,
        pnl_distribution=pnl_hist,
        paths_sample=sample_paths,
        exit_day_distribution=exit_dist,
        expected_value_per_trade=round(ev_per_trade, 2),
        kelly_optimal_fraction=round(max(0, kelly), 4),
        edge_per_trade_pct=round(edge, 2),
    )


def portfolio_simulation(
    trades: list[dict],
    correlation: float = 0.30,
    n_sims: int = 5_000,
) -> dict:
    """
    Portfolio-level Monte Carlo with correlated positions.
    Simulates concurrent trade outcomes accounting for correlation.
    """
    n_trades = len(trades)
    if n_trades == 0:
        return {"total_return_pct": 0, "sharpe": 0}

    # Generate correlated uniform random variables
    mean = np.zeros(n_trades)
    cov = np.full((n_trades, n_trades), correlation)
    np.fill_diagonal(cov, 1.0)

    # Cholesky for correlation
    L = np.linalg.cholesky(cov)
    Z = np.random.standard_normal((n_sims, n_trades))
    correlated_Z = Z @ L.T

    # For each trade, use its individual P&L distribution parameters
    portfolio_returns = np.zeros(n_sims)
    for i, trade in enumerate(trades):
        win_rate = trade.get("prob_profit", 0.35)
        avg_win = trade.get("avg_win_pct", 60)
        avg_loss = trade.get("avg_loss_pct", -40)
        size_pct = trade.get("position_size_pct", 3)

        # Convert correlated normal to uniform, then to trade outcome
        from scipy.stats import norm
        uniform = norm.cdf(correlated_Z[:, i])
        trade_pnl = np.where(uniform <= win_rate, avg_win, avg_loss)
        portfolio_returns += trade_pnl * (size_pct / 100)

    mean_port = float(np.mean(portfolio_returns))
    std_port = float(np.std(portfolio_returns))
    sharpe = mean_port / std_port if std_port > 0 else 0

    return {
        "mean_return_pct": round(mean_port, 2),
        "std_pct": round(std_port, 2),
        "sharpe_ratio": round(sharpe, 3),
        "var_95_pct": round(float(np.percentile(portfolio_returns, 5)), 2),
        "cvar_95_pct": round(float(np.mean(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)])), 2),
        "prob_positive": round(float(np.mean(portfolio_returns > 0)), 4),
        "max_return_pct": round(float(np.max(portfolio_returns)), 2),
        "min_return_pct": round(float(np.min(portfolio_returns)), 2),
    }
