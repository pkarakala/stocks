"""
Portfolio Tracker — Daily Buys/Sells State Machine

Persists open positions across daily pipeline runs and emits explicit
BUY / SELL / HOLD actions each day, so the console can show
"what to do today" — not just raw signals.

State file: data/positions.json
  {
    "open": [ {position}, ... ],
    "closed": [ {position + exit info}, ... ]
  }

Daily flow:
  1. Load open positions.
  2. Mark to market with today's prices; re-evaluate all exit rules.
  3. Positions hitting an exit rule -> SELL action (with reason, in plain English).
  4. Fresh alpha signals not already held -> BUY action (respecting risk limits).
  5. Everything else -> HOLD with updated P&L.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional

from config import STRATEGY, RISK, OUTPUT_DIR
from greeks import black_scholes, full_greeks

POSITIONS_PATH = os.path.join(OUTPUT_DIR, "positions.json")


def _load_state() -> dict:
    if os.path.exists(POSITIONS_PATH):
        with open(POSITIONS_PATH) as f:
            return json.load(f)
    return {"open": [], "closed": []}


def _save_state(state: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(POSITIONS_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


# Plain-English exit reasons for non-traders
EXIT_EXPLANATIONS = {
    "PROFIT_TARGET": "Hit the +40% profit target — take the win",
    "STOP_LOSS": "Lost half its value — cutting the loss before it gets worse",
    "TIME_STOP": "Under 14 days to expiration — time decay accelerates from here, exit regardless of P&L",
    "TRAILING_STOP": "Gave back too much of its gains — locking in what's left",
    "MAX_HOLD": "Held 30 days — the trade thesis has expired",
    "MOMENTUM_FLIP": "The momentum that justified the trade has reversed",
}


def evaluate_positions(
    prices: dict[str, float],
    ivs: dict[str, float],
    today: Optional[dt.date] = None,
    r: float = 0.043,
) -> tuple[list[dict], list[dict]]:
    """
    Mark all open positions to market and apply exit rules.
    Returns (sells, holds) — each a list of action dicts for the console.
    Mutates and saves state.
    """
    today = today or dt.date.today()
    state = _load_state()
    exits_cfg = STRATEGY["exits"]

    sells, holds = [], []
    still_open = []

    for pos in state["open"]:
        ticker = pos["ticker"]
        S = prices.get(ticker)
        if S is None:
            # no price today — hold as-is
            still_open.append(pos)
            holds.append({**pos, "action": "HOLD", "note": "No price data today"})
            continue

        entry_date = dt.date.fromisoformat(pos["entry_date"])
        days_held = (today - entry_date).days
        dte_now = pos["dte_at_entry"] - days_held
        T_now = max(dte_now, 0) / 365.0
        sigma_now = ivs.get(ticker, pos["entry_iv"])

        if T_now > 0:
            value = black_scholes("call", S, pos["strike"], T_now, r, sigma_now)
        else:
            value = max(0.0, S - pos["strike"])
        value_net = value * (1 - RISK["slippage_pct"] / 100.0)
        ret = (value_net - pos["entry_premium"]) / pos["entry_premium"]
        pos["high_water"] = max(pos.get("high_water", 0.0), ret)
        pos["current_premium"] = round(value_net, 4)
        pos["current_underlying"] = round(S, 2)
        pos["pnl_pct"] = round(ret * 100, 2)
        pos["pnl_dollars"] = round((value_net - pos["entry_premium"]) * 100 * pos["contracts"], 2)
        pos["days_held"] = days_held
        pos["dte_remaining"] = dte_now

        # IV-crush check
        iv_chg_pct = (sigma_now - pos["entry_iv"]) / pos["entry_iv"] * 100 if pos["entry_iv"] else 0

        exit_reason = None
        if ret >= exits_cfg["profit_target_pct"] / 100.0:
            exit_reason = "PROFIT_TARGET"
        elif ret <= exits_cfg["stop_loss_pct"] / 100.0:
            exit_reason = "STOP_LOSS"
        elif dte_now <= exits_cfg["time_stop_dte"]:
            exit_reason = "TIME_STOP"
        elif pos["high_water"] >= exits_cfg["trailing_activation_pct"] / 100.0:
            floor = pos["high_water"] * (1 - exits_cfg["trailing_stop_pct"] / 100.0)
            if ret < floor:
                exit_reason = "TRAILING_STOP"
        elif days_held >= STRATEGY["max_hold_days"]:
            exit_reason = "MAX_HOLD"

        if exit_reason:
            pos["exit_date"] = today.isoformat()
            pos["exit_reason"] = exit_reason
            pos["exit_premium"] = round(value_net, 4)
            state["closed"].append(pos)
            sells.append({
                **pos,
                "action": "SELL",
                "explanation": EXIT_EXPLANATIONS.get(exit_reason, exit_reason),
            })
        else:
            still_open.append(pos)
            holds.append({
                **pos,
                "action": "HOLD",
                "note": f"{'+' if ret >= 0 else ''}{ret*100:.1f}% · {dte_now} DTE left",
            })

    state["open"] = still_open
    _save_state(state)
    return sells, holds


def open_new_positions(signals: list, today: Optional[dt.date] = None) -> list[dict]:
    """
    Convert today's top alpha signals into BUY actions, respecting
    position limits and sector concentration. Mutates and saves state.
    """
    today = today or dt.date.today()
    state = _load_state()
    buys = []

    held_tickers = {p["ticker"] for p in state["open"]}
    slots = RISK["max_concurrent_positions"] - len(state["open"])

    for sig in signals:
        if slots <= 0:
            break
        if sig.ticker in held_tickers:
            continue
        sector_count = sum(1 for p in state["open"] if p.get("sector") == sig.sector)
        if sector_count >= RISK["max_sector_concentration"]:
            continue

        position_capital = RISK["initial_capital"] * (sig.position_size_pct / 100.0)
        contracts = max(1, int(position_capital / (sig.estimated_premium * 100)))

        pos = {
            "ticker": sig.ticker,
            "sector": sig.sector,
            "entry_date": today.isoformat(),
            "entry_underlying": sig.price,
            "strike": sig.suggested_strike,
            "dte_at_entry": sig.suggested_dte,
            "entry_premium": sig.estimated_premium,
            "entry_iv": sig.implied_vol,
            "entry_delta": sig.estimated_delta,
            "contracts": contracts,
            "signal_score": sig.composite_score,
            "position_size_pct": sig.position_size_pct,
            "high_water": 0.0,
            "rationale": sig.rationale,
        }
        state["open"].append(pos)
        held_tickers.add(sig.ticker)
        slots -= 1

        buys.append({
            **pos,
            "action": "BUY",
            "explanation": (
                f"Buy {contracts}x {sig.ticker} ${sig.suggested_strike:.0f} call, "
                f"{sig.suggested_dte} days out, ~${sig.estimated_premium:.2f}/contract. "
                f"Why: {sig.rationale}"
            ),
        })

    _save_state(state)
    return buys


def portfolio_summary() -> dict:
    """Aggregate stats for the console header."""
    state = _load_state()
    open_pos = state["open"]
    closed = state["closed"]

    open_pnl = sum(p.get("pnl_dollars", 0) for p in open_pos)
    realized = sum(
        (p.get("exit_premium", 0) - p["entry_premium"]) * 100 * p["contracts"]
        for p in closed
    )
    wins = [p for p in closed if p.get("exit_premium", 0) > p["entry_premium"]]

    return {
        "open_positions": len(open_pos),
        "closed_trades": len(closed),
        "unrealized_pnl": round(open_pnl, 2),
        "realized_pnl": round(realized, 2),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
        "positions": open_pos,
        "recent_closed": closed[-10:],
    }
