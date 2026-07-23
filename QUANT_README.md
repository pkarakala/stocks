# Quant Console

Institutional-grade options swing trading system. Multi-factor alpha model with Monte Carlo simulation, walk-forward backtesting, and a real-time dark-mode console.

**Strategy:** Buy OTM calls (0.20–0.35 delta, 35–50 DTE) on momentum breakouts. Target 40% return within 30 days. Half-Kelly position sizing.

## Quick Start

```bash
cd ~/Desktop/quant-console
./run.sh
```

This installs dependencies (first run only) and opens the console at `http://localhost:3000`.

## Architecture

```
quant-console/
├── engine/              # Python quantitative engine
│   ├── config.py        # All strategy parameters (delta, DTE, exits, Kelly)
│   ├── greeks.py        # BSM pricing + full Greeks (delta through charm)
│   ├── alpha.py         # 5-factor alpha model (momentum, vol, flow, RSI, RS)
│   ├── monte_carlo.py   # Student-t jump-diffusion path simulation
│   ├── backtester.py    # Walk-forward backtest with synthetic option pricing
│   └── pipeline.py      # Daily signal generation pipeline
│
├── console/             # React dashboard (Vite + Recharts)
│   └── src/
│       ├── views/Dashboard.jsx   # Equity curve, KPIs, monthly returns
│       ├── views/Signals.jsx     # Signal scanner with factor decomposition
│       ├── views/Backtest.jsx    # Full backtest with drawdown + trade scatter
│       └── views/MonteCarlo.jsx  # P&L distribution, paths, exit timing
│
├── data/                # JSON output from pipeline (consumed by console)
├── watchlist.csv        # 100-name AI/tech universe
└── run.sh              # One-command launcher
```

## Running the Signal Pipeline

After the console is running, generate live signals from market data:

```bash
cd engine
venv/bin/python pipeline.py
```

This fetches 2 years of data for all 100 tickers, computes the alpha model, runs Monte Carlo on the top signals, executes a full backtest, and writes `data/latest.json`. The console auto-loads it on refresh.

## Daily Automation (cron)

```bash
# Run at 4:35 PM ET every weekday (after market close)
35 16 * * 1-5 cd ~/Desktop/quant-console/engine && venv/bin/python pipeline.py >> ../data/run.log 2>&1
```

## Strategy Parameters

All tunable in `engine/config.py`:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Delta range | 0.20–0.35 | Optimal leverage vs probability (research-backed) |
| DTE at entry | 35–50 days | Theta/gamma efficiency sweet spot |
| Profit target | +40% | Sufficient leverage at 0.27 delta |
| Stop loss | -50% | Half-Kelly aligned, limits ruin |
| Trailing stop | 60% of gains (after +25%) | Lets winners run |
| Time stop | Exit if DTE < 14 | Avoids theta acceleration |
| Max position | 4% of capital | Half-Kelly with 35% win rate |
| Max positions | 8 concurrent | Diversification |
| Regime filter | SPY > 50 EMA + VIX < 25 | Daniel & Moskowitz (2016) |

## Alpha Model (5 Factors)

| Factor | Weight | Source |
|--------|--------|--------|
| Momentum | 30% | EMA cross, breakout, slope (Jegadeesh & Titman 1993) |
| Volatility Regime | 25% | IV rank < 30% = cheap options (Goyal & Saretto 2009) |
| Volume/Flow | 20% | Surge detection, OBV trend (Chordia & Swaminathan 2000) |
| RSI Zone | 15% | 45–70 continuation zone (Chong & Ng 2008) |
| Relative Strength | 10% | Outperformance vs SPY 20d |

## Monte Carlo Model

- Student-t distribution (df=5) for fat tails
- Poisson jump diffusion (8% daily jump probability)
- 10,000 paths per simulation
- Full exit-rule simulation with intra-path repricing
- Outputs: P(target), VaR, CVaR, Kelly fraction, exit timing

## Research References

1. Jegadeesh & Titman (1993) — Momentum factor
2. Moskowitz, Ooi & Pedersen (2012) — Time series momentum
3. Broadie, Chernov & Johannes (2009) — OTM option return distributions
4. Goyal & Saretto (2009) — IV vs RV predicting option returns
5. Daniel & Moskowitz (2016) — Momentum crashes / regime filters
6. Brock, Lakonishok & LeBaron (1992) — Technical trading rules
7. Thorp (2006) — Kelly criterion in practice
8. Bates (1996) — Jump diffusion models

---

*Research tool. Not financial advice. Past performance does not guarantee future results.*
