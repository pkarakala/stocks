"""
Signal Generation Engine
Momentum breakout detection with multi-factor scoring for OTM call entries.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import STRATEGY, SIGNAL_WEIGHTS, GREEKS as GREEKS_CFG


@dataclass
class Signal:
    ticker: str
    date: dt.date
    signal_type: str  # "LONG_CALL"
    score: float      # composite signal strength [0, 1]
    price: float
    suggested_strike: float
    suggested_dte: int
    estimated_delta: float
    estimated_premium: float
    target_exit_price: float
    stop_loss_price: float
    risk_reward_ratio: float

    # Factor scores
    momentum_score: float
    iv_rank_score: float
    volume_score: float
    risk_reward_score: float
    liquidity_score: float

    # Context
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float
    iv_rank: float
    volume_ratio: float
    breakout_pct: float

    rationale: str = ""


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_iv_rank(current_iv: float, iv_history: list[float]) -> float:
    if not iv_history or current_iv is None:
        return 50.0
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    if iv_max == iv_min:
        return 50.0
    return ((current_iv - iv_min) / (iv_max - iv_min)) * 100.0


def estimate_otm_strike(price: float, delta_target: float, iv: float, dte: int) -> float:
    T = dte / 365.0
    if T <= 0 or iv <= 0:
        return round(price * 1.05, 0)
    sigma_move = iv * math.sqrt(T)
    from scipy.stats import norm as scipy_norm
    z = scipy_norm.ppf(1.0 - delta_target)
    strike = price * math.exp(sigma_move * z * 0.5)
    return round(strike, 0)


def estimate_premium(price: float, strike: float, iv: float, dte: int, r: float) -> float:
    from greeks import black_scholes_price
    T = dte / 365.0
    return black_scholes_price("call", price, strike, T, r, iv)


def generate_signals(
    ticker: str,
    hist: pd.DataFrame,
    current_iv: float | None,
    iv_history: list[float] | None,
    date: dt.date | None = None,
) -> Optional[Signal]:
    if hist is None or len(hist) < 60:
        return None
    if current_iv is None or current_iv <= 0:
        return None

    cfg = STRATEGY
    mom = cfg["momentum"]
    entry = cfg["entry"]

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]

    ema_fast = compute_ema(close, mom["ema_fast"])
    ema_slow = compute_ema(close, mom["ema_slow"])
    rsi = compute_rsi(close, mom["rsi_period"])
    atr = compute_atr(high, low, close, mom["atr_period"])

    latest_price = float(close.iloc[-1])
    latest_ema_fast = float(ema_fast.iloc[-1])
    latest_ema_slow = float(ema_slow.iloc[-1])
    latest_rsi = float(rsi.iloc[-1])
    latest_atr = float(atr.iloc[-1])
    avg_volume = float(volume.iloc[-20:].mean())
    latest_volume = float(volume.iloc[-1])
    volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0

    lookback_high = float(high.iloc[-mom["breakout_lookback"]:].max())
    breakout_pct = (latest_price - lookback_high) / lookback_high * 100.0

    # --- Momentum Score ---
    momentum_score = 0.0
    ema_cross_bullish = latest_ema_fast > latest_ema_slow
    ema_slope_positive = ema_fast.iloc[-1] > ema_fast.iloc[-3] if len(ema_fast) > 3 else False
    price_above_ema = latest_price > latest_ema_fast

    if ema_cross_bullish:
        momentum_score += 0.35
    if ema_slope_positive:
        momentum_score += 0.20
    if price_above_ema:
        momentum_score += 0.15
    if breakout_pct > 0:
        momentum_score += min(0.30, breakout_pct / 5.0 * 0.30)
    if 40 <= latest_rsi <= 65:
        momentum_score += 0.10  # not overbought, room to run

    momentum_score = min(1.0, momentum_score)

    # --- Gate: must pass minimum momentum ---
    if momentum_score < 0.4:
        return None
    if not ema_cross_bullish:
        return None

    # --- IV Rank Score (prefer low IV rank for cheap options) ---
    iv_rank = compute_iv_rank(current_iv, iv_history or [])
    if iv_rank < 30:
        iv_rank_score = 1.0
    elif iv_rank < 50:
        iv_rank_score = 0.7
    elif iv_rank < 70:
        iv_rank_score = 0.4
    else:
        iv_rank_score = 0.1  # IV is expensive

    # --- Volume Score ---
    volume_score = min(1.0, (volume_ratio - 1.0) / (mom["volume_surge_mult"] - 1.0)) if volume_ratio > 1.0 else 0.2

    # --- Risk/Reward Score ---
    target_delta = (entry["min_delta"] + entry["max_delta"]) / 2.0
    target_dte = (entry["target_dte_min"] + entry["target_dte_max"]) // 2
    strike = estimate_otm_strike(latest_price, target_delta, current_iv, target_dte)
    premium = estimate_premium(latest_price, strike, current_iv, target_dte, GREEKS_CFG["risk_free_rate"])

    if premium <= 0:
        return None

    target_exit_value = premium * (1 + cfg["target_return_pct"] / 100.0)
    stop_loss_value = premium * (1 + cfg["exit"]["stop_loss_pct"] / 100.0)
    risk_reward = cfg["target_return_pct"] / abs(cfg["exit"]["stop_loss_pct"]) if cfg["exit"]["stop_loss_pct"] != 0 else 0
    risk_reward_score = min(1.0, risk_reward / 1.5)

    # --- Liquidity Score (proxy: volume ratio as liquidity indicator) ---
    liquidity_score = min(1.0, volume_ratio / 2.0)

    # --- Composite Score ---
    composite = (
        SIGNAL_WEIGHTS["momentum_score"] * momentum_score
        + SIGNAL_WEIGHTS["iv_rank_score"] * iv_rank_score
        + SIGNAL_WEIGHTS["volume_score"] * volume_score
        + SIGNAL_WEIGHTS["risk_reward_score"] * risk_reward_score
        + SIGNAL_WEIGHTS["liquidity_score"] * liquidity_score
    )

    if composite < 0.45:
        return None

    # --- Compute estimated delta for the chosen strike ---
    from greeks import compute_greeks
    T = target_dte / 365.0
    greeks = compute_greeks("call", latest_price, strike, T, GREEKS_CFG["risk_free_rate"], current_iv)

    rationale_parts = []
    if ema_cross_bullish:
        rationale_parts.append(f"EMA{mom['ema_fast']}/{mom['ema_slow']} bullish crossover")
    if breakout_pct > 0:
        rationale_parts.append(f"{breakout_pct:.1f}% above {mom['breakout_lookback']}d high")
    if volume_ratio > mom["volume_surge_mult"]:
        rationale_parts.append(f"volume surge {volume_ratio:.1f}x avg")
    if iv_rank < 30:
        rationale_parts.append(f"IV rank {iv_rank:.0f}% (cheap)")

    signal_date = date or dt.date.today()

    return Signal(
        ticker=ticker,
        date=signal_date,
        signal_type="LONG_CALL",
        score=round(composite, 4),
        price=round(latest_price, 2),
        suggested_strike=strike,
        suggested_dte=target_dte,
        estimated_delta=round(greeks.delta, 3),
        estimated_premium=round(premium, 2),
        target_exit_price=round(target_exit_value, 2),
        stop_loss_price=round(stop_loss_value, 2),
        risk_reward_ratio=round(risk_reward, 2),
        momentum_score=round(momentum_score, 4),
        iv_rank_score=round(iv_rank_score, 4),
        volume_score=round(volume_score, 4),
        risk_reward_score=round(risk_reward_score, 4),
        liquidity_score=round(liquidity_score, 4),
        ema_fast=round(latest_ema_fast, 2),
        ema_slow=round(latest_ema_slow, 2),
        rsi=round(latest_rsi, 2),
        atr=round(latest_atr, 2),
        iv_rank=round(iv_rank, 2),
        volume_ratio=round(volume_ratio, 2),
        breakout_pct=round(breakout_pct, 2),
        rationale="; ".join(rationale_parts),
    )
