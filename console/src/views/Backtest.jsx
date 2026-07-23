import React from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ComposedChart, Line,
  ScatterChart, Scatter, ZAxis
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <div className="label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="value" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : p.value}
        </div>
      ))}
    </div>
  )
}

export default function Backtest({ data }) {
  const bt = data.backtest || {}
  const equityCurve = bt.equity_curve || []
  const drawdown = bt.drawdown_curve || []
  const monthly = bt.monthly_returns || []
  const trades = bt.trades || []

  const chartEquity = equityCurve.filter((_, i) => i % 3 === 0 || i === equityCurve.length - 1)
  const chartDrawdown = drawdown.filter((_, i) => i % 3 === 0 || i === drawdown.length - 1)

  // Trade scatter data
  const tradeScatter = trades.slice(0, 200).map(t => ({
    hold_days: t.hold_days,
    pnl_pct: t.pnl_pct,
    size: Math.abs(t.pnl_total) / 10,
    exit_reason: t.exit_reason,
  }))

  return (
    <div>
      {/* Header Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Return</div>
          <div className={`stat-value ${bt.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
            {bt.total_return_pct >= 0 ? '+' : ''}{bt.total_return_pct?.toFixed(1)}%
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CAGR</div>
          <div className="stat-value positive">{bt.cagr_pct?.toFixed(1)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sharpe</div>
          <div className="stat-value neutral">{bt.sharpe_ratio?.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sortino</div>
          <div className="stat-value neutral">{bt.sortino_ratio?.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Max Drawdown</div>
          <div className="stat-value negative">-{bt.max_drawdown_pct?.toFixed(1)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Win Rate</div>
          <div className="stat-value neutral">{bt.win_rate_pct?.toFixed(1)}%</div>
        </div>
      </div>

      {/* Equity + Drawdown */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Equity Curve & Drawdown</div>
            <div className="card-subtitle">
              {bt.start_date} to {bt.end_date} — ${bt.initial_capital?.toLocaleString()} to ${bt.final_capital?.toLocaleString()}
            </div>
          </div>
        </div>
        <div className="chart-container tall">
          <ResponsiveContainer width="100%" height="70%">
            <AreaChart data={chartEquity} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#2a3441' }} interval={Math.floor(chartEquity.length / 5)} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="equity" name="Equity" stroke="#3b82f6" strokeWidth={2} fill="url(#eqGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height="28%">
            <AreaChart data={chartDrawdown} margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `-${v}%`} reversed />
              <Area type="monotone" dataKey="drawdown_pct" name="Drawdown" stroke="#ef4444" strokeWidth={1.5} fill="url(#ddGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Monthly Returns Heatmap */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Monthly Returns</div>
        </div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthly} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#2a3441' }} interval={1} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="return_pct" name="Return" radius={[3, 3, 0, 0]}>
                {monthly.map((entry, i) => (
                  <Cell key={i} fill={entry.return_pct >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trade Analysis */}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Trade Statistics</div>
          <table className="signals-table" style={{ marginTop: 12 }}>
            <tbody>
              {[
                ['Total Trades', bt.total_trades],
                ['Winners', `${bt.winning_trades} (${bt.win_rate_pct?.toFixed(1)}%)`],
                ['Losers', bt.losing_trades],
                ['Avg Win', `+${bt.avg_win_pct?.toFixed(1)}%`],
                ['Avg Loss', `${bt.avg_loss_pct?.toFixed(1)}%`],
                ['Largest Win', `+${bt.largest_win_pct?.toFixed(1)}%`],
                ['Largest Loss', `${bt.largest_loss_pct?.toFixed(1)}%`],
                ['Profit Factor', bt.profit_factor?.toFixed(2)],
                ['Payoff Ratio', `${bt.payoff_ratio?.toFixed(2)}:1`],
                ['Expectancy', `${bt.expectancy_pct?.toFixed(2)}% / trade`],
                ['Avg Hold', `${bt.avg_hold_days?.toFixed(1)} days`],
              ].map(([k, v], i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-secondary)' }}>{k}</td>
                  <td className="right">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-title">Risk Metrics</div>
          <table className="signals-table" style={{ marginTop: 12 }}>
            <tbody>
              {[
                ['Max Drawdown', `-${bt.max_drawdown_pct?.toFixed(1)}%`],
                ['DD Duration', `${bt.max_drawdown_days} days`],
                ['Avg Drawdown', `-${bt.avg_drawdown_pct?.toFixed(1)}%`],
                ['Calmar Ratio', bt.calmar_ratio?.toFixed(3)],
                ['Kelly Fraction', `${(bt.kelly_fraction * 100)?.toFixed(0)}%`],
                ['Avg Position', `${bt.avg_position_size_pct?.toFixed(1)}%`],
                ['Max Positions', bt.max_concurrent_positions],
                ['─── vs Benchmark ───', ''],
                ['SPY Return', `+${bt.benchmark_return_pct?.toFixed(1)}%`],
                ['SPY Sharpe', bt.benchmark_sharpe?.toFixed(3)],
                ['Alpha', `+${bt.alpha_pct?.toFixed(1)}%`],
              ].map(([k, v], i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-secondary)' }}>{k}</td>
                  <td className="right">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trade Scatter */}
      {tradeScatter.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Trade Distribution (Hold Days vs P&L)</div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
                <XAxis type="number" dataKey="hold_days" name="Hold Days" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={{ stroke: '#2a3441' }} label={{ value: 'Hold Days', position: 'bottom', fill: '#64748b', fontSize: 11 }} />
                <YAxis type="number" dataKey="pnl_pct" name="P&L %" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickFormatter={v => `${v}%`} />
                <ZAxis type="number" dataKey="size" range={[20, 200]} />
                <Tooltip content={<CustomTooltip />} />
                <Scatter name="Trades" data={tradeScatter}>
                  {tradeScatter.map((entry, i) => (
                    <Cell key={i} fill={entry.pnl_pct >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.6} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
