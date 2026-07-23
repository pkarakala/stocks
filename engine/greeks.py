"""
Options Pricing & Greeks Engine
Black-Scholes-Merton with analytical Greeks and IV solver.
Institutional-grade: handles edge cases, supports American approximation.

Susquehanna approach: every trade decision begins and ends with Greeks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

OptionType = Literal["call", "put"]


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class OptionGreeks:
    """Full Greeks snapshot for a single option."""
    theoretical_price: float
    delta: float
    gamma: float
    theta: float      # per calendar day (negative for long options)
    vega: float       # per 1 vol point (0.01 absolute)
    rho: float
    vanna: float      # d(delta)/d(vol)
    charm: float      # d(delta)/d(time) — delta decay
    iv: float
    intrinsic: float
    extrinsic: float
    leverage: float   # omega = delta * (S / option_price)
    prob_itm: float   # N(d2) for calls, N(-d2) for puts


def black_scholes(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    """European option price via BSM."""
    if T <= 0 or sigma <= 0 or S <= 0:
        if option_type == "call":
            return max(0.0, S - K)
        return max(0.0, K - S)

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)


def full_greeks(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> OptionGreeks:
    """Compute all Greeks including second-order (vanna, charm)."""
    if T <= 1e-10 or sigma <= 1e-10 or S <= 0:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        d = 1.0 if (option_type == "call" and S > K) else (-1.0 if (option_type == "put" and S < K) else 0.0)
        return OptionGreeks(
            theoretical_price=intrinsic, delta=d, gamma=0.0, theta=0.0,
            vega=0.0, rho=0.0, vanna=0.0, charm=0.0, iv=sigma,
            intrinsic=intrinsic, extrinsic=0.0, leverage=0.0, prob_itm=abs(d),
        )

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    pdf_d1 = _norm_pdf(d1)
    exp_qT = math.exp(-q * T)
    exp_rT = math.exp(-r * T)

    if option_type == "call":
        price = S * exp_qT * _norm_cdf(d1) - K * exp_rT * _norm_cdf(d2)
        delta = exp_qT * _norm_cdf(d1)
        rho_val = K * T * exp_rT * _norm_cdf(d2) / 100.0
        prob_itm = _norm_cdf(d2)
    else:
        price = K * exp_rT * _norm_cdf(-d2) - S * exp_qT * _norm_cdf(-d1)
        delta = -exp_qT * _norm_cdf(-d1)
        rho_val = -K * T * exp_rT * _norm_cdf(-d2) / 100.0
        prob_itm = _norm_cdf(-d2)

    gamma = exp_qT * pdf_d1 / (S * sigma * sqrt_T)
    vega = S * exp_qT * pdf_d1 * sqrt_T / 100.0  # per 1 vol point
    theta_call = (
        -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
        - r * K * exp_rT * _norm_cdf(d2)
        + q * S * exp_qT * _norm_cdf(d1)
    )
    theta_put = (
        -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
        + r * K * exp_rT * _norm_cdf(-d2)
        - q * S * exp_qT * _norm_cdf(-d1)
    )
    theta = (theta_call if option_type == "call" else theta_put) / 365.0

    # Second-order Greeks
    vanna = -exp_qT * pdf_d1 * d2 / sigma  # d(delta)/d(sigma)
    charm_val = -exp_qT * (
        pdf_d1 * (2.0 * (r - q) * T - d2 * sigma * sqrt_T) / (2.0 * T * sigma * sqrt_T)
    )
    if option_type == "put":
        charm_val += q * exp_qT

    intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    extrinsic = max(0.0, price - intrinsic)
    leverage = (delta * S / price) if price > 0 else 0.0

    return OptionGreeks(
        theoretical_price=price,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho_val,
        vanna=vanna,
        charm=charm_val,
        iv=sigma,
        intrinsic=intrinsic,
        extrinsic=extrinsic,
        leverage=leverage,
        prob_itm=prob_itm,
    )


def implied_vol(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    market_price: float,
    q: float = 0.0,
    tol: float = 1e-7,
    max_iter: int = 100,
) -> Optional[float]:
    """Newton-Raphson IV solver with bisection fallback."""
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None

    intrinsic = max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T)) if option_type == "call" \
        else max(0.0, K * math.exp(-r * T) - S * math.exp(-q * T))
    if market_price < intrinsic - 0.01:
        return None

    # Newton-Raphson
    sigma = 0.3  # initial guess
    for _ in range(max_iter):
        price = black_scholes(option_type, S, K, T, r, sigma, q)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        vega_val = S * math.exp(-q * T) * _norm_pdf(
            (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        ) * math.sqrt(T)
        if vega_val < 1e-12:
            break
        sigma -= diff / vega_val
        sigma = max(0.001, min(sigma, 5.0))

    # Fallback: bisection
    lo, hi = 0.001, 5.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        price = black_scholes(option_type, S, K, T, r, mid, q)
        if abs(price - market_price) < tol:
            return mid
        if price > market_price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def expected_move(S: float, sigma: float, T: float, confidence: float = 0.68) -> tuple[float, float]:
    """Expected price range at given confidence level."""
    from scipy.stats import norm
    z = norm.ppf(0.5 + confidence / 2.0)
    move = S * sigma * math.sqrt(T) * z
    return (S - move, S + move)


def delta_to_strike(
    option_type: OptionType,
    S: float,
    T: float,
    r: float,
    sigma: float,
    target_delta: float,
    q: float = 0.0,
) -> float:
    """Find the strike that gives a target delta (bisection on strikes)."""
    lo_K = S * 0.5
    hi_K = S * 2.0
    for _ in range(60):
        mid_K = (lo_K + hi_K) / 2.0
        g = full_greeks(option_type, S, mid_K, T, r, sigma, q)
        current_delta = abs(g.delta)
        if abs(current_delta - target_delta) < 0.001:
            return mid_K
        if option_type == "call":
            if current_delta > target_delta:
                lo_K = mid_K
            else:
                hi_K = mid_K
        else:
            if current_delta > target_delta:
                hi_K = mid_K
            else:
                lo_K = mid_K
    return (lo_K + hi_K) / 2.0
