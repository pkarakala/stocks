// Sample data for development / when pipeline hasn't run yet.
// This showcases all views with realistic synthetic data.

const today = new Date().toISOString().slice(0, 10)

function generateEquityCurve() {
  const points = []
  let equity = 100000
  const start = new Date()
  start.setFullYear(start.getFullYear() - 2)

  for (let i = 0; i < 504; i++) {
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    const dailyReturn = (Math.random() - 0.47) * 0.015
    equity *= (1 + dailyReturn)
    points.push({
      date: d.toISOString().slice(0, 10),
      equity: Math.round(equity * 100) / 100
    })
  }
  return points
}

function generateMonthlyReturns() {
  const months = []
  const start = new Date()
  start.setFullYear(start.getFullYear() - 2)
  for (let i = 0; i < 24; i++) {
    const d = new Date(start)
    d.setMonth(d.getMonth() + i)
    months.push({
      month: d.toISOString().slice(0, 7),
      return_pct: Math.round((Math.random() - 0.4) * 15 * 100) / 100
    })
  }
  return months
}

function generateDrawdownCurve() {
  const equity = generateEquityCurve()
  let peak = equity[0].equity
  return equity.map(p => {
    if (p.equity > peak) peak = p.equity
    const dd = ((peak - p.equity) / peak) * 100
    return { date: p.date, drawdown_pct: Math.round(dd * 100) / 100 }
  })
}

function generatePnlDistribution() {
  const bins = []
  for (let i = -100; i < 200; i += 6) {
    const center = i + 3
    let count
    if (center < -50) count = Math.round(Math.random() * 100 + 200)
    else if (center < 0) count = Math.round(Math.random() * 150 + 100)
    else if (center < 40) count = Math.round(Math.random() * 200 + 150)
    else if (center < 80) count = Math.round(Math.random() * 150 + 50)
    else count = Math.round(Math.random() * 50 + 10)

    bins.push({
      bin_start: i,
      bin_end: i + 6,
      count,
      pct: Math.round(count / 100 * 100) / 100
    })
  }
  return bins
}

function generateSamplePaths() {
  const paths = []
  for (let p = 0; p < 50; p++) {
    const path = [150]
    for (let d = 1; d <= 30; d++) {
      const prev = path[d - 1]
      const change = prev * (Math.random() - 0.48) * 0.025
      path.push(Math.round((prev + change) * 100) / 100)
    }
    paths.push(path)
  }
  return paths
}

const sampleSignals = [
  {
    ticker: 'NVDA', date: today, signal_type: 'LONG_CALL', composite_score: 0.82,
    price: 142.50, price_1d_chg_pct: 2.3, price_5d_chg_pct: 5.8, price_20d_chg_pct: 12.4,
    momentum_score: 0.91, volatility_score: 0.78, flow_score: 0.85, rsi_score: 0.72, relative_strength_score: 0.88,
    ema_fast: 139.20, ema_slow: 135.80, rsi: 62.5, atr: 4.20, atr_pct: 2.95,
    volume_ratio: 1.8, iv_rank: 22, realized_vol: 0.32, implied_vol: 0.38, rv_iv_ratio: 0.84,
    breakout_pct: 3.2, suggested_strike: 155, suggested_dte: 42,
    estimated_delta: 0.28, estimated_premium: 4.85, estimated_leverage: 8.2,
    target_pnl_pct: 40, stop_loss_pct: -50, risk_reward_ratio: 0.8,
    position_size_pct: 3.5, max_loss_dollars: 1750,
    sector: 'semiconductors', rationale: 'EMA9/21 bullish; breakout +3.2%; volume 1.8x; IV rank 22% (cheap)',
    warnings: ''
  },
  {
    ticker: 'PLTR', date: today, signal_type: 'LONG_CALL', composite_score: 0.74,
    price: 78.30, price_1d_chg_pct: 1.5, price_5d_chg_pct: 4.2, price_20d_chg_pct: 8.7,
    momentum_score: 0.78, volatility_score: 0.82, flow_score: 0.65, rsi_score: 0.68, relative_strength_score: 0.72,
    ema_fast: 76.50, ema_slow: 74.20, rsi: 58.3, atr: 2.80, atr_pct: 3.58,
    volume_ratio: 1.4, iv_rank: 18, realized_vol: 0.42, implied_vol: 0.48, rv_iv_ratio: 0.875,
    breakout_pct: 1.8, suggested_strike: 85, suggested_dte: 42,
    estimated_delta: 0.26, estimated_premium: 3.20, estimated_leverage: 6.4,
    target_pnl_pct: 40, stop_loss_pct: -50, risk_reward_ratio: 0.8,
    position_size_pct: 3.2, max_loss_dollars: 1600,
    sector: 'software', rationale: 'EMA9/21 bullish; breakout +1.8%; IV rank 18% (cheap); RS +4.2% vs SPY',
    warnings: ''
  },
  {
    ticker: 'AVGO', date: today, signal_type: 'LONG_CALL', composite_score: 0.71,
    price: 198.40, price_1d_chg_pct: 0.9, price_5d_chg_pct: 3.1, price_20d_chg_pct: 7.5,
    momentum_score: 0.72, volatility_score: 0.75, flow_score: 0.68, rsi_score: 0.70, relative_strength_score: 0.65,
    ema_fast: 195.80, ema_slow: 192.40, rsi: 56.8, atr: 5.50, atr_pct: 2.77,
    volume_ratio: 1.3, iv_rank: 28, realized_vol: 0.28, implied_vol: 0.34, rv_iv_ratio: 0.82,
    breakout_pct: 2.1, suggested_strike: 215, suggested_dte: 42,
    estimated_delta: 0.27, estimated_premium: 6.40, estimated_leverage: 8.4,
    target_pnl_pct: 40, stop_loss_pct: -50, risk_reward_ratio: 0.8,
    position_size_pct: 3.0, max_loss_dollars: 1500,
    sector: 'semiconductors', rationale: 'EMA9/21 bullish; breakout +2.1%; volume 1.3x',
    warnings: ''
  },
  {
    ticker: 'CRWD', date: today, signal_type: 'LONG_CALL', composite_score: 0.68,
    price: 385.20, price_1d_chg_pct: 1.2, price_5d_chg_pct: 2.8, price_20d_chg_pct: 9.1,
    momentum_score: 0.70, volatility_score: 0.65, flow_score: 0.72, rsi_score: 0.65, relative_strength_score: 0.68,
    ema_fast: 380.00, ema_slow: 372.50, rsi: 61.2, atr: 12.80, atr_pct: 3.32,
    volume_ratio: 1.6, iv_rank: 35, realized_vol: 0.35, implied_vol: 0.42, rv_iv_ratio: 0.83,
    breakout_pct: 1.4, suggested_strike: 410, suggested_dte: 42,
    estimated_delta: 0.25, estimated_premium: 12.50, estimated_leverage: 7.7,
    target_pnl_pct: 40, stop_loss_pct: -50, risk_reward_ratio: 0.8,
    position_size_pct: 2.8, max_loss_dollars: 1400,
    sector: 'software', rationale: 'EMA9/21 bullish; volume 1.6x; breakout +1.4%',
    warnings: ''
  },
  {
    ticker: 'ANET', date: today, signal_type: 'LONG_CALL', composite_score: 0.65,
    price: 112.80, price_1d_chg_pct: 0.7, price_5d_chg_pct: 2.5, price_20d_chg_pct: 6.3,
    momentum_score: 0.68, volatility_score: 0.70, flow_score: 0.58, rsi_score: 0.62, relative_strength_score: 0.60,
    ema_fast: 111.20, ema_slow: 108.90, rsi: 55.7, atr: 3.40, atr_pct: 3.01,
    volume_ratio: 1.2, iv_rank: 25, realized_vol: 0.30, implied_vol: 0.36, rv_iv_ratio: 0.83,
    breakout_pct: 0.8, suggested_strike: 120, suggested_dte: 42,
    estimated_delta: 0.30, estimated_premium: 4.10, estimated_leverage: 8.2,
    target_pnl_pct: 40, stop_loss_pct: -50, risk_reward_ratio: 0.8,
    position_size_pct: 3.0, max_loss_dollars: 1500,
    sector: 'infrastructure', rationale: 'EMA9/21 bullish; IV rank 25% (cheap)',
    warnings: ''
  },
]

const sampleSimulation = {
  ticker: 'NVDA',
  n_paths: 10000,
  model: 'student_t_jump',
  mean_return_pct: 8.5,
  median_return_pct: -12.3,
  std_return_pct: 62.4,
  skewness: 1.82,
  kurtosis: 4.31,
  prob_profit: 0.38,
  prob_target_hit: 0.28,
  prob_double: 0.12,
  prob_total_loss: 0.18,
  prob_stop_hit: 0.35,
  var_95: -72.5,
  var_99: -92.1,
  cvar_95: -84.3,
  cvar_99: -96.8,
  max_drawdown_avg: -38.2,
  avg_hold_days: 18.4,
  median_hold_days: 15,
  avg_days_to_target: 12.8,
  percentiles: { 5: -72.5, 10: -55.2, 25: -32.1, 50: -12.3, 75: 28.5, 90: 68.4, 95: 112.3 },
  pnl_distribution: generatePnlDistribution(),
  paths_sample: generateSamplePaths(),
  exit_day_distribution: Array.from({ length: 30 }, (_, i) => ({
    day: i + 1, count: Math.round(Math.random() * 400 + (i < 5 ? 100 : i > 20 ? 300 : 200))
  })),
  expected_value_per_trade: 8.5,
  kelly_optimal_fraction: 0.045,
  edge_per_trade_pct: 8.5,
}

const equityCurve = generateEquityCurve()
const finalEquity = equityCurve[equityCurve.length - 1].equity

function makeSparkline(start, drift) {
  const points = [start]
  for (let i = 1; i < 18; i++) {
    points.push(Math.round((points[i - 1] * (1 + (Math.random() - 0.5 + drift) * 0.03)) * 100) / 100)
  }
  return points
}

const sampleExplorer = sampleSignals.map(s => ({
  ticker: s.ticker,
  sector: s.sector,
  tier: 'core',
  price: s.price,
  pct_1d: s.price_1d_chg_pct,
  pct_5d: s.price_5d_chg_pct,
  pct_20d: s.price_20d_chg_pct,
  ema9: s.ema_fast,
  ema21: s.ema_slow,
  ema50: s.ema_slow * 0.97,
  above_trend: true,
  rsi: s.rsi,
  iv_rank: s.iv_rank,
  implied_vol: s.implied_vol,
  realized_vol: s.realized_vol,
  volume_ratio: s.volume_ratio,
  has_signal: true,
  signal_score: s.composite_score,
  fail_reason: '',
  sparkline: makeSparkline(s.price * 0.9, 0.05),
  summary: `${s.ticker} is moving up — it closed at $${s.price.toFixed(2)}. It's gained ${s.price_20d_chg_pct.toFixed(0)}% over the past month, which is strong. Buying pressure is healthy but not overheated — the zone where trends tend to continue. Options on it are cheap relative to the past year — good time to be a buyer of calls if the trend holds. ✅ VERDICT: This one passes our screen today — see the trade card for exact strike and size.`,
}))

const sampleActions = {
  buys: [
    {
      ticker: 'NVDA', sector: 'semiconductors', action: 'BUY',
      entry_date: today, entry_underlying: 142.50, strike: 155, dte_at_entry: 42,
      entry_premium: 4.85, entry_iv: 0.38, entry_delta: 0.28, contracts: 7,
      signal_score: 0.82, position_size_pct: 3.5,
      explanation: 'Buy 7x NVDA $155 call, 42 days out, ~$4.85/contract. Why: EMA9/21 bullish; breakout +3.2%; volume 1.8x; IV rank 22% (cheap)',
    },
  ],
  sells: [
    {
      ticker: 'PLTR', sector: 'software', action: 'SELL',
      entry_date: '2026-07-01', entry_underlying: 72.10, strike: 80, dte_at_entry: 42,
      entry_premium: 2.90, exit_premium: 4.12, current_underlying: 79.85,
      contracts: 10, pnl_pct: 42.1, pnl_dollars: 1220, days_held: 16,
      exit_reason: 'PROFIT_TARGET',
      explanation: 'Hit the +40% profit target — take the win',
    },
  ],
  holds: [
    {
      ticker: 'AVGO', sector: 'semiconductors', action: 'HOLD',
      strike: 215, entry_premium: 6.40, current_premium: 7.05,
      pnl_pct: 10.2, pnl_dollars: 325, days_held: 8, dte_remaining: 34,
      note: '+10.2% · 34 DTE left',
    },
    {
      ticker: 'CRWD', sector: 'software', action: 'HOLD',
      strike: 410, entry_premium: 12.50, current_premium: 11.20,
      pnl_pct: -10.4, pnl_dollars: -260, days_held: 5, dte_remaining: 37,
      note: '-10.4% · 37 DTE left',
    },
  ],
}

const samplePortfolio = {
  open_positions: 3,
  closed_trades: 24,
  unrealized_pnl: 1285,
  realized_pnl: 6420,
  win_rate_pct: 41.7,
  positions: [],
  recent_closed: [],
}

export default {
  generated_at: new Date().toISOString(),
  date: today,
  regime: {
    status: 'BULLISH',
    vix: 16.8,
    spy_above_50ema: true,
    new_entries_allowed: true,
    explanation: 'Market trend is up and volatility is calm — good conditions for this strategy.',
  },
  actions: sampleActions,
  portfolio: samplePortfolio,
  explorer: sampleExplorer,
  signals: sampleSignals,
  simulations: [sampleSimulation],
  backtest: {
    strategy_name: 'Momentum_OTM_Calls',
    start_date: new Date(Date.now() - 730 * 86400000).toISOString().slice(0, 10),
    end_date: today,
    initial_capital: 100000,
    final_capital: finalEquity,
    total_return_pct: Math.round((finalEquity / 100000 - 1) * 10000) / 100,
    cagr_pct: 28.4,
    sharpe_ratio: 0.82,
    sortino_ratio: 1.24,
    calmar_ratio: 0.95,
    max_drawdown_pct: 29.8,
    max_drawdown_days: 42,
    avg_drawdown_pct: 8.5,
    total_trades: 187,
    winning_trades: 68,
    losing_trades: 119,
    win_rate_pct: 36.4,
    avg_win_pct: 72.5,
    avg_loss_pct: -38.2,
    largest_win_pct: 285.0,
    largest_loss_pct: -95.0,
    avg_hold_days: 14.8,
    profit_factor: 1.45,
    payoff_ratio: 1.90,
    expectancy_pct: 2.12,
    avg_position_size_pct: 3.2,
    max_concurrent_positions: 8,
    kelly_fraction: 0.5,
    monthly_returns: generateMonthlyReturns(),
    equity_curve: equityCurve,
    drawdown_curve: generateDrawdownCurve(),
    trades: [],
    benchmark_return_pct: 22.5,
    benchmark_sharpe: 0.65,
    alpha_pct: 5.9,
    beta: 0.72,
    information_ratio: 0.45,
  },
  strategy_config: {
    name: 'Momentum_OTM_Calls',
    target_return_pct: 40,
    max_hold_days: 30,
    delta_range: [0.20, 0.35],
    dte_range: [35, 50],
  },
  universe_size: 95,
  signal_count: 5,
}
