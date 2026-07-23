"""
Quant Engine Configuration — Institutional Parameters
Calibrated from academic literature and empirical backtesting.

References:
- Jegadeesh & Titman (1993): Momentum factor returns
- Moskowitz, Ooi & Pedersen (2012): Time series momentum
- Broadie, Chernov & Johannes (2009): OTM call return distributions
- Goyal & Saretto (2009): IV vs RV predicting option returns
- Daniel & Moskowitz (2016): Momentum crashes / regime filters
- Thorp (2006): Kelly criterion in practice
"""

import os

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "watchlist.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY: OTM Momentum Calls — 40% return target, 30-day horizon
# ═══════════════════════════════════════════════════════════════════════════════

STRATEGY = {
    "name": "Momentum_OTM_Calls",
    "target_return_pct": 40,
    "max_hold_days": 30,
    "min_hold_days": 2,

    # Strike/DTE selection (research-backed: 0.25-0.30 delta, 38-50 DTE)
    "option_selection": {
        "min_delta": 0.20,
        "max_delta": 0.35,
        "target_delta": 0.27,
        "target_dte_min": 35,
        "target_dte_max": 50,
        "target_dte_ideal": 42,
        "min_open_interest": 200,
        "min_volume": 50,
        "max_bid_ask_spread_pct": 8.0,
    },

    # Exit discipline (hybrid protocol — Citadel risk framework)
    "exits": {
        "profit_target_pct": 40,
        "stop_loss_pct": -50,
        "trailing_activation_pct": 25,   # activate trailing after +25%
        "trailing_stop_pct": 60,         # trail at 60% of gains
        "time_stop_dte": 14,             # exit if DTE drops below 14
        "iv_crush_exit_pct": -25,        # exit if IV drops >25% from entry
        "momentum_exit_signals": 2,      # exit if N momentum signals flip bearish
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA MODEL: Multi-factor signal scoring (RenTech statistical approach)
# Composite alpha = weighted sum of orthogonal factors
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_FACTORS = {
    # Factor 1: Price Momentum (Jegadeesh & Titman)
    "momentum": {
        "weight": 0.30,
        "ema_fast": 9,
        "ema_slow": 21,
        "ema_trend": 50,
        "lookback_breakout": 20,
        "min_score_threshold": 0.35,
    },

    # Factor 2: Volatility Regime (Goyal & Saretto, Susquehanna approach)
    "volatility": {
        "weight": 0.25,
        "iv_rank_lookback": 252,
        "iv_rank_ideal_max": 30,    # buy when IV is cheap
        "iv_rank_reject_above": 60,
        "rv_vs_iv_threshold": 0.9,  # prefer when RV > 0.9 * IV
    },

    # Factor 3: Volume/Institutional Flow
    "flow": {
        "weight": 0.20,
        "volume_surge_threshold": 1.5,
        "volume_lookback": 20,
        "obv_confirmation": True,
    },

    # Factor 4: RSI Regime (Chong & Ng 2008)
    "mean_reversion_guard": {
        "weight": 0.15,
        "rsi_period": 14,
        "rsi_momentum_zone_low": 45,
        "rsi_momentum_zone_high": 70,
        "rsi_overbought_reject": 78,
    },

    # Factor 5: Relative Strength vs Index
    "relative_strength": {
        "weight": 0.10,
        "benchmark": "SPY",
        "lookback_days": 20,
        "min_outperformance_pct": 2.0,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# RISK ENGINE: Position sizing & portfolio constraints (Citadel/Kelly)
# Using Half-Kelly with additional portfolio-level limits
# ═══════════════════════════════════════════════════════════════════════════════

RISK = {
    "initial_capital": 100_000,
    "kelly_fraction": 0.5,          # half-Kelly (Thorp recommendation)
    "max_position_pct": 4.0,        # max 4% capital per trade
    "max_concurrent_positions": 8,
    "max_sector_concentration": 3,   # max 3 positions same sector
    "max_correlated_exposure_pct": 15.0,
    "max_portfolio_delta": 500,      # portfolio-level delta limit
    "max_portfolio_vega": 200,       # portfolio-level vega limit

    # Regime filter (Daniel & Moskowitz 2016)
    "regime_filter": {
        "spy_above_50ema": True,     # broad market must be trending up
        "vix_ceiling": 25,           # don't buy calls when VIX > 25
        "vix_ideal_range": [12, 20],
        "pause_after_drawdown_pct": 15,  # pause new entries after 15% DD
    },

    # Transaction costs
    "commission_per_contract": 0.65,
    "slippage_pct": 2.5,            # realistic OTM options slippage
}

# ═══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO: Simulation parameters
# Student-t with jump diffusion (Bates 1996)
# ═══════════════════════════════════════════════════════════════════════════════

MONTE_CARLO = {
    "n_simulations": 10_000,
    "confidence_levels": [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95],

    # Underlying dynamics
    "distribution": "student_t_jump",  # student_t | gbm | jump_diffusion
    "student_t_df": 5,                 # degrees of freedom (fat tails)
    "jump_intensity": 0.08,            # ~20 jump days/year
    "jump_mean": -0.01,                # avg jump size (slight downward bias)
    "jump_std": 0.04,                  # jump size volatility

    # Correlation in stress
    "normal_correlation": 0.30,
    "stress_correlation": 0.70,
    "stress_threshold_vix": 25,
}

# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTER
# ═══════════════════════════════════════════════════════════════════════════════

BACKTEST = {
    "lookback_years": 2,
    "walk_forward_window_months": 6,
    "walk_forward_step_months": 1,
    "benchmark": "SPY",
    "risk_free_rate": 0.043,
}

# ═══════════════════════════════════════════════════════════════════════════════
# DATA PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

DATA = {
    "sleep_between_calls": 1.2,
    "max_retries": 3,
    "backoff_base": 2.0,
    "batch_size": 20,
    "history_period": "2y",
    "iv_proxy_vix_beta_default": 1.3,
}
