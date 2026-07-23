import React from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'

function StatCard({ label, value, change, positive }) {
  const cls = positive === true ? 'positive' : positive === false ? 'negative' : 'neutral'
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${cls}`}>{value}</div>
      {change && <div className={`stat-change ${cls}`}>{change}</div>}
    </div>
  )
}

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

export default function Dashboard({ data }) {
  const bt = data.backtest || {}
  const signals = data.signals || []
  const regime = data.regime || {}
  const equityCurve = bt.equity_curve || []
  const monthlyReturns = bt.monthly_returns || []

  // Format equity curve for chart (sample every 5th point for performance)
  const chartData = equityCurve.filter((_, i) => i % 3 === 0 || i === equityCurve.length - 1)

  return (
    <div>
      {/* KPI Stats Row */}
      <div className="stats-grid">
        <StatCard
          label="Total Return"
          value={`${bt.total_return_pct >= 0 ? '+' : ''}${bt.total_return_pct?.toFixed(1)}%`}
          positive={bt.total_return_pct > 0}
          change={`vs SPY ${bt.benchmark_return_pct >= 0 ? '+' : ''}${bt.benchmark_return_pct?.toFixed(1)}%`}
        />
        <StatCard
          label="Sharpe Ratio"
          value={bt.sharpe_ratio?.toFixed(2)}
          positive={bt.sharpe_ratio > 1 ? true : bt.sharpe_ratio > 0.5 ? null : false}
        />
        <StatCard
          label="Win Rate"
          value={`${bt.win_rate_pct?.toFixed(1)}%`}
          change={`${bt.total_trades} trades`}
          positive={bt.win_rate_pct > 35}
        />
        <StatCard
          label="Profit Factor"
          value={bt.profit_factor?.toFixed(2)}
          positive={bt.profit_factor > 1.3}
        />
        <StatCard
          label="Max Drawdown"
          value={`-${bt.max_drawdown_pct?.toFixed(1)}%`}
          change={`${bt.max_drawdown_days}d duration`}
          positive={false}
        />
        <StatCard
          label="Active Signals"
          value={signals.length}
          change={regime.new_entries_allowed ? 'entries allowed' : 'entries paused'}
          positive={regime.new_entries_allowed}
        />
      </div>

      {/* Equity Curve */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Portfolio Equity Curve</div>
            <div className="card-subtitle">
              ${bt.initial_capital?.toLocaleString()} initial — ${bt.final_capital?.toLocaleString()} current — {bt.cagr_pct?.toFixed(1)}% CAGR
            </div>
          </div>
          <div className="badge blue">2Y Backtest</div>
        </div>
        <div className="chart-container tall">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2a3441' }}
                interval={Math.floor(chartData.length / 6)}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={v => `$${(v/1000).toFixed(0)}k`}
                domain={['dataMin * 0.95', 'dataMax * 1.02']}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="equity"
                name="Equity"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#equityGradient)"
                dot={false}
                animationDuration={1500}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Monthly Returns */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Monthly Returns</div>
            <div className="card-subtitle">Strategy P&L by calendar month</div>
          </div>
        </div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyReturns} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" vertical={false} />
              <XAxis
                dataKey="month"
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2a3441' }}
                interval={2}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={v => `${v}%`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="return_pct" name="Return" radius={[3, 3, 0, 0]}>
                {monthlyReturns.map((entry, i) => (
                  <Cell key={i} fill={entry.return_pct >= 0 ? '#10b981' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance Comparison */}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Strategy Metrics</div>
          <table className="signals-table" style={{ marginTop: 12 }}>
            <tbody>
              {[
                ['CAGR', `${bt.cagr_pct?.toFixed(1)}%`],
                ['Sharpe', bt.sharpe_ratio?.toFixed(3)],
                ['Sortino', bt.sortino_ratio?.toFixed(3)],
                ['Calmar', bt.calmar_ratio?.toFixed(3)],
                ['Avg Win', `+${bt.avg_win_pct?.toFixed(1)}%`],
                ['Avg Loss', `${bt.avg_loss_pct?.toFixed(1)}%`],
                ['Payoff Ratio', `${bt.payoff_ratio?.toFixed(2)}:1`],
                ['Expectancy', `${bt.expectancy_pct?.toFixed(2)}% per trade`],
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
          <div className="card-title">Strategy Parameters</div>
          <table className="signals-table" style={{ marginTop: 12 }}>
            <tbody>
              {[
                ['Strategy', data.strategy_config?.name || '—'],
                ['Target Return', `${data.strategy_config?.target_return_pct}%`],
                ['Max Hold', `${data.strategy_config?.max_hold_days} days`],
                ['Delta Range', data.strategy_config?.delta_range?.join(' - ')],
                ['DTE Range', data.strategy_config?.dte_range?.join(' - ') + ' days'],
                ['Max Positions', bt.max_concurrent_positions],
                ['Position Size', `${bt.avg_position_size_pct?.toFixed(1)}% avg`],
                ['Kelly Fraction', `${(bt.kelly_fraction * 100)?.toFixed(0)}%`],
                ['Alpha vs SPY', `+${bt.alpha_pct?.toFixed(1)}%`],
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
    </div>
  )
}
