"""
Alpha Model — Multi-Factor Signal Generation
Renaissance-style: combine orthogonal, statistically validated factors
into a composite alpha score. Each factor independently predictive;
ensemble reduces variance.

Factor universe:
  1. Price Momentum (EMA cross, breakout, slope)
  2. Volatility Regime (IV rank, RV/IV ratio)
  3. Volume/Flow (surge detection, OBV trend)
  4. RSI Momentum Zone (continuation signal, not reversal)
  5. Relative Strength (vs benchmark, sector-adjusted)
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

from config import ALPHA_FACTORS, STRATEGY, RISK


@dataclass
class AlphaSignal:
    """A single trade signal with full factor decomposition."""
    ticker: str
    date: str
    signal_type: str
    composite_score: float
    rank: int = 0

    # Price context
    price: float = 0.0
    price_1d_chg_pct: float = 0.0
    price_5d_chg_pct: float = 0.0
    price_20d_chg_pct: float = 0.0

    # Factor scores [0, 1]
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    flow_score: float = 0.0
    rsi_score: float = 0.0
    relative_strength_score: float = 0.0

    # Technical indicators
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    ema_trend: float = 0.0
    rsi: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    volume_ratio: float = 0.0
    iv_rank: float = 0.0
    realized_vol: float = 0.0
    implied_vol: float = 0.0
    rv_iv_ratio: float = 0.0
    relative_strength_20d: float = 0.0
    breakout_pct: float = 0.0

    # Option parameters
    suggested_strike: float = 0.0
    suggested_dte: int = 0
    estimated_delta: float = 0.0
    estimated_premium: float = 0.0
    estimated_leverage: float = 0.0

    # Risk metrics
    target_pnl_pct: float = 0.0
    stop_loss_pct: float = 0.0
    risk_reward_ratio: float = 0.0
    position_size_pct: float = 0.0
    max_loss_dollars: float = 0.0

    # Context
    sector: str = ""
    rationale: str = ""
    warnings: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def realized_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window).std() * np.sqrt(252)


def iv_rank(current_iv: float, iv_history: np.ndarray) -> float:
    if len(iv_history) == 0 or current_iv is None:
        return 50.0
    iv_min = float(np.nanmin(iv_history))
    iv_max = float(np.nanmax(iv_history))
    if iv_max <= iv_min:
        return 50.0
    return ((current_iv - iv_min) / (iv_max - iv_min)) * 100.0


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    return (volume * direction).cumsum()


def compute_alpha(
    ticker: str,
    hist: pd.DataFrame,
    current_iv: Optional[float],
    iv_history: Optional[np.ndarray],
    benchmark_hist: Optional[pd.DataFrame] = None,
    sector: str = "",
    signal_date: Optional[dt.date] = None,
) -> Optional[AlphaSignal]:
    """
    Compute composite alpha for a single ticker.
    Returns None if the signal doesn't pass minimum thresholds.
    """
    if hist is None or len(hist) < 60:
        return None

    cfg_mom = ALPHA_FACTORS["momentum"]
    cfg_vol = ALPHA_FACTORS["volatility"]
    cfg_flow = ALPHA_FACTORS["flow"]
    cfg_rsi = ALPHA_FACTORS["mean_reversion_guard"]
    cfg_rs = ALPHA_FACTORS["relative_strength"]

    close = hist["Close"].astype(float)
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    volume = hist["Volume"].astype(float)

    if close.iloc[-1] <= 0:
        return None

    # ─── Compute indicators ───────────────────────────────────────────────────
    ema_f = ema(close, cfg_mom["ema_fast"])
    ema_s = ema(close, cfg_mom["ema_slow"])
    ema_t = ema(close, cfg_mom["ema_trend"])
    rsi_series = rsi(close, cfg_rsi["rsi_period"])
    atr_series = atr(high, low, close, 14)
    rv_series = realized_volatility(close, 20)
    obv_series = obv(close, volume)

    price = float(close.iloc[-1])
    ema_fast_val = float(ema_f.iloc[-1])
    ema_slow_val = float(ema_s.iloc[-1])
    ema_trend_val = float(ema_t.iloc[-1])
    rsi_val = float(rsi_series.iloc[-1])
    atr_val = float(atr_series.iloc[-1])
    atr_pct_val = (atr_val / price * 100) if price > 0 else 0
    rv_val = float(rv_series.iloc[-1]) if not np.isnan(rv_series.iloc[-1]) else 0.25
    avg_vol_20 = float(volume.iloc[-20:].mean())
    latest_vol = float(volume.iloc[-1])
    vol_ratio = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

    # Price changes
    pct_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) > 1 else 0
    pct_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0
    pct_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    # Breakout % above N-day high
    lookback_high = float(high.iloc[-cfg_mom["lookback_breakout"]:].max())
    breakout_pct_val = (price - lookback_high) / lookback_high * 100

    # IV rank
    iv_val = current_iv if current_iv else rv_val * 1.2
    iv_hist = iv_history if iv_history is not None and len(iv_history) > 0 else np.array([iv_val])
    ivr = iv_rank(iv_val, iv_hist)
    rv_iv = rv_val / iv_val if iv_val > 0 else 1.0

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTOR 1: MOMENTUM
    # ═══════════════════════════════════════════════════════════════════════════
    momentum_score = 0.0

    # EMA crossover (fast > slow = bullish)
    ema_cross_bull = ema_fast_val > ema_slow_val
    if ema_cross_bull:
        momentum_score += 0.30

    # EMA slope (accelerating)
    if len(ema_f) > 5:
        slope_5d = float(ema_f.iloc[-1] - ema_f.iloc[-5])
        if slope_5d > 0:
            momentum_score += 0.15

    # Price above trend EMA
    if price > ema_trend_val:
        momentum_score += 0.15

    # Breakout above recent high
    if breakout_pct_val > 0:
        momentum_score += min(0.25, breakout_pct_val / 3.0 * 0.25)

    # Higher lows pattern (3 consecutive)
    lows_5d = low.iloc[-15:].resample("5D").min() if hasattr(low.index, 'freq') else low.iloc[-15::5]
    if len(lows_5d) >= 3:
        if all(lows_5d.iloc[i] > lows_5d.iloc[i-1] for i in range(1, min(3, len(lows_5d)))):
            momentum_score += 0.15

    momentum_score = min(1.0, momentum_score)

    # Gate: minimum momentum required
    if momentum_score < cfg_mom["min_score_threshold"]:
        return None
    if not ema_cross_bull:
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTOR 2: VOLATILITY REGIME
    # ═══════════════════════════════════════════════════════════════════════════
    volatility_score = 0.0

    if ivr <= cfg_vol["iv_rank_ideal_max"]:
        volatility_score = 1.0
    elif ivr <= 50:
        volatility_score = 0.65
    elif ivr <= cfg_vol["iv_rank_reject_above"]:
        volatility_score = 0.30
    else:
        volatility_score = 0.05  # IV too expensive, penalize heavily

    # RV > IV bonus (options underpricing realized movement)
    if rv_iv > cfg_vol["rv_vs_iv_threshold"]:
        volatility_score = min(1.0, volatility_score + 0.2)

    # Reject if IV is in extreme high territory
    if ivr > cfg_vol["iv_rank_reject_above"]:
        warnings_list = ["IV_RANK_HIGH"]
    else:
        warnings_list = []

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTOR 3: VOLUME / FLOW
    # ═══════════════════════════════════════════════════════════════════════════
    flow_score = 0.0

    if vol_ratio >= cfg_flow["volume_surge_threshold"]:
        flow_score += min(0.6, (vol_ratio - 1.0) / 1.5 * 0.6)

    # OBV trend confirmation
    if len(obv_series) > 10:
        obv_slope = float(obv_series.iloc[-1] - obv_series.iloc[-10])
        if obv_slope > 0:
            flow_score += 0.3

    # Base credit for normal volume
    flow_score = max(0.15, min(1.0, flow_score))

    # Volume on up-days vs down-days (accumulation detection)
    if len(close) > 20:
        up_days = close.diff() > 0
        up_vol = float(volume[up_days].iloc[-20:].mean()) if up_days.iloc[-20:].any() else 0
        down_vol = float(volume[~up_days].iloc[-20:].mean()) if (~up_days).iloc[-20:].any() else 1
        if up_vol > down_vol * 1.2:
            flow_score = min(1.0, flow_score + 0.15)

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTOR 4: RSI REGIME
    # ═══════════════════════════════════════════════════════════════════════════
    rsi_score = 0.0

    if cfg_rsi["rsi_momentum_zone_low"] <= rsi_val <= cfg_rsi["rsi_momentum_zone_high"]:
        rsi_score = 1.0  # ideal momentum zone
    elif rsi_val < cfg_rsi["rsi_momentum_zone_low"]:
        rsi_score = 0.3  # too weak, not enough momentum
    elif rsi_val <= cfg_rsi["rsi_overbought_reject"]:
        rsi_score = 0.5  # getting overbought but not rejected
    else:
        rsi_score = 0.0  # overbought reject
        warnings_list.append("RSI_OVERBOUGHT")

    # Hard reject if extremely overbought
    if rsi_val > cfg_rsi["rsi_overbought_reject"]:
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # FACTOR 5: RELATIVE STRENGTH
    # ═══════════════════════════════════════════════════════════════════════════
    rs_score = 0.0

    if benchmark_hist is not None and len(benchmark_hist) >= 20:
        bench_close = benchmark_hist["Close"].astype(float)
        stock_ret_20d = pct_20d
        bench_ret_20d = float((bench_close.iloc[-1] / bench_close.iloc[-21] - 1) * 100)
        rs_20d = stock_ret_20d - bench_ret_20d

        if rs_20d >= cfg_rs["min_outperformance_pct"]:
            rs_score = min(1.0, rs_20d / 5.0)
        elif rs_20d >= 0:
            rs_score = 0.4
        else:
            rs_score = 0.1
    else:
        rs_score = 0.5  # neutral if no benchmark data
        rs_20d = 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPOSITE ALPHA
    # ═══════════════════════════════════════════════════════════════════════════
    composite = (
        cfg_mom["weight"] * momentum_score
        + cfg_vol["weight"] * volatility_score
        + cfg_flow["weight"] * flow_score
        + cfg_rsi["weight"] * rsi_score
        + cfg_rs["weight"] * rs_score
    )

    if composite < 0.40:
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # OPTION PARAMETERIZATION
    # ═══════════════════════════════════════════════════════════════════════════
    from greeks import full_greeks, delta_to_strike, black_scholes

    opt_cfg = STRATEGY["option_selection"]
    target_dte = opt_cfg["target_dte_ideal"]
    T = target_dte / 365.0
    r = 0.043

    strike = delta_to_strike("call", price, T, r, iv_val, opt_cfg["target_delta"])
    strike = round(strike)  # round to nearest dollar

    greeks = full_greeks("call", price, strike, T, r, iv_val)
    premium = greeks.theoretical_price

    if premium <= 0.01:
        return None

    # Position sizing (half-Kelly)
    exit_cfg = STRATEGY["exits"]
    win_rate_est = 0.35  # conservative estimate
    payoff_ratio = abs(exit_cfg["profit_target_pct"] / exit_cfg["stop_loss_pct"])
    kelly = (win_rate_est * payoff_ratio - (1 - win_rate_est)) / payoff_ratio
    kelly_half = max(0.005, kelly * RISK["kelly_fraction"])
    position_pct = min(kelly_half * 100, RISK["max_position_pct"])
    max_loss = (RISK["initial_capital"] * position_pct / 100) * abs(exit_cfg["stop_loss_pct"] / 100)

    # Rationale
    rationale_parts = []
    if ema_cross_bull:
        rationale_parts.append(f"EMA{cfg_mom['ema_fast']}/{cfg_mom['ema_slow']} bullish")
    if breakout_pct_val > 0:
        rationale_parts.append(f"breakout +{breakout_pct_val:.1f}%")
    if vol_ratio > 1.5:
        rationale_parts.append(f"volume {vol_ratio:.1f}x")
    if ivr < 30:
        rationale_parts.append(f"IV rank {ivr:.0f}% (cheap)")
    if rs_20d > 2:
        rationale_parts.append(f"RS +{rs_20d:.1f}% vs SPY")

    return AlphaSignal(
        ticker=ticker,
        date=(signal_date or dt.date.today()).isoformat(),
        signal_type="LONG_CALL",
        composite_score=round(composite, 4),
        price=round(price, 2),
        price_1d_chg_pct=round(pct_1d, 2),
        price_5d_chg_pct=round(pct_5d, 2),
        price_20d_chg_pct=round(pct_20d, 2),
        momentum_score=round(momentum_score, 4),
        volatility_score=round(volatility_score, 4),
        flow_score=round(flow_score, 4),
        rsi_score=round(rsi_score, 4),
        relative_strength_score=round(rs_score, 4),
        ema_fast=round(ema_fast_val, 2),
        ema_slow=round(ema_slow_val, 2),
        ema_trend=round(ema_trend_val, 2),
        rsi=round(rsi_val, 2),
        atr=round(atr_val, 2),
        atr_pct=round(atr_pct_val, 2),
        volume_ratio=round(vol_ratio, 2),
        iv_rank=round(ivr, 2),
        realized_vol=round(rv_val, 4),
        implied_vol=round(iv_val, 4),
        rv_iv_ratio=round(rv_iv, 3),
        relative_strength_20d=round(rs_20d, 2) if benchmark_hist is not None else 0.0,
        breakout_pct=round(breakout_pct_val, 2),
        suggested_strike=round(strike, 2),
        suggested_dte=target_dte,
        estimated_delta=round(greeks.delta, 3),
        estimated_premium=round(premium, 2),
        estimated_leverage=round(greeks.leverage, 1),
        target_pnl_pct=exit_cfg["profit_target_pct"],
        stop_loss_pct=exit_cfg["stop_loss_pct"],
        risk_reward_ratio=round(payoff_ratio, 2),
        position_size_pct=round(position_pct, 2),
        max_loss_dollars=round(max_loss, 2),
        sector=sector,
        rationale="; ".join(rationale_parts),
        warnings=", ".join(warnings_list) if warnings_list else "",
    )
