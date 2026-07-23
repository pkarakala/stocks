import React, { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, ReferenceLine, Cell, AreaChart, Area
} from 'recharts'

function ProbRing({ value, label, color }) {
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - value)

  return (
    <div className="prob-ring">
      <svg width="100" height="100">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--bg-elevated)" strokeWidth="6" />
        <circle
          cx="50" cy="50" r={radius} fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div style={{ textAlign: 'center' }}>
        <div className="value" style={{ color }}>{(value * 100).toFixed(0)}%</div>
        <div className="label">{label}</div>
      </div>
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
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </div>
      ))}
    </div>
  )
}

export default function MonteCarlo({ data }) {
  const sims = data.simulations || []
  const [selectedIdx, setSelectedIdx] = useState(0)
  const sim = sims[selectedIdx]

  if (!sim) {
    return (
      <div className="empty-state">
        <h2>No Simulations Available</h2>
        <p>Run the pipeline to generate Monte Carlo simulations for today's top signals.</p>
      </div>
    )
  }

  const pnlDist = sim.pnl_distribution || []
  const exitDist = sim.exit_day_distribution || []
  const paths = sim.paths_sample || []

  // Format paths for line chart
  const pathChartData = []
  if (paths.length > 0) {
    const numDays = paths[0].length
    for (let d = 0; d < numDays; d++) {
      const point = { day: d }
      paths.slice(0, 30).forEach((path, i) => {
        point[`p${i}`] = path[d]
      })
      pathChartData.push(point)
    }
  }

  return (
    <div>
      {/* Simulation selector */}
      {sims.length > 1 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {sims.map((s, i) => (
            <button
              key={i}
              className={`nav-tab ${selectedIdx === i ? 'active' : ''}`}
              onClick={() => setSelectedIdx(i)}
            >
              {s.ticker}
            </button>
          ))}
        </div>
      )}

      {/* Header */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title" style={{ fontSize: 18 }}>
              Monte Carlo Simulation — <span style={{ color: 'var(--accent-blue)' }}>{sim.ticker}</span>
            </div>
            <div className="card-subtitle">
              {sim.n_paths?.toLocaleString()} paths · {sim.model} model · Fat-tailed Student-t with Poisson jumps
            </div>
          </div>
        </div>

        {/* Probability Rings */}
        <div style={{ display: 'flex', justifyContent: 'space-around', padding: '20px 0' }}>
          <ProbRing value={sim.prob_profit} label="Profit" color="var(--green)" />
          <ProbRing value={sim.prob_target_hit} label="Hit 40%" color="var(--accent-blue)" />
          <ProbRing value={sim.prob_double} label="Double" color="var(--accent-purple)" />
          <ProbRing value={sim.prob_stop_hit} label="Stopped" color="var(--red)" />
        </div>
      </div>

      {/* Key Metrics */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Expected Value</div>
          <div className={`stat-value ${sim.expected_value_per_trade >= 0 ? 'positive' : 'negative'}`}>
            {sim.expected_value_per_trade >= 0 ? '+' : ''}{sim.expected_value_per_trade}%
          </div>
          <div className="stat-change">per trade</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Median Return</div>
          <div className={`stat-value ${sim.median_return_pct >= 0 ? 'positive' : 'negative'}`}>
            {sim.median_return_pct >= 0 ? '+' : ''}{sim.median_return_pct}%
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Kelly Fraction</div>
          <div className="stat-value neutral">{(sim.kelly_optimal_fraction * 100).toFixed(1)}%</div>
          <div className="stat-change">optimal sizing</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">VaR (95%)</div>
          <div className="stat-value negative">{sim.var_95}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CVaR (95%)</div>
          <div className="stat-value negative">{sim.cvar_95}%</div>
          <div className="stat-change">tail risk</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Days to Target</div>
          <div className="stat-value neutral">{sim.avg_days_to_target}</div>
          <div className="stat-change">when it hits</div>
        </div>
      </div>

      {/* P&L Distribution */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">P&L Distribution</div>
            <div className="card-subtitle">
              Skewness: {sim.skewness} · Kurtosis: {sim.kurtosis} · Distribution is {sim.skewness > 1 ? 'right-skewed (positive tail)' : 'roughly symmetric'}
            </div>
          </div>
        </div>
        <div className="chart-container tall">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={pnlDist} margin={{ top: 20, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" vertical={false} />
              <XAxis
                dataKey="bin_start"
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2a3441' }}
                tickFormatter={v => `${v}%`}
                interval={4}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                label={{ value: 'Frequency', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine x={0} stroke="var(--text-tertiary)" strokeDasharray="3 3" />
              <ReferenceLine x={40} stroke="var(--accent-blue)" strokeDasharray="5 5" label={{ value: '40% target', fill: 'var(--accent-blue)', fontSize: 10, position: 'top' }} />
              <ReferenceLine x={-50} stroke="var(--red)" strokeDasharray="5 5" label={{ value: 'stop loss', fill: 'var(--red)', fontSize: 10, position: 'top' }} />
              <Bar dataKey="count" name="Paths" radius={[2, 2, 0, 0]}>
                {pnlDist.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.bin_start >= 40 ? 'var(--accent-blue)' : entry.bin_start >= 0 ? 'var(--green)' : entry.bin_start >= -50 ? 'var(--yellow)' : 'var(--red)'}
                    fillOpacity={0.75}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid-2">
        {/* Simulated Paths */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Sample Price Paths (30 of {sim.n_paths?.toLocaleString()})</div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={pathChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
                <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#2a3441' }} label={{ value: 'Days', position: 'bottom', fill: '#64748b', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                {paths.slice(0, 30).map((_, i) => (
                  <Line
                    key={i}
                    type="monotone"
                    dataKey={`p${i}`}
                    stroke={`hsl(${210 + i * 5}, 60%, ${50 + (i % 3) * 10}%)`}
                    strokeWidth={1}
                    dot={false}
                    strokeOpacity={0.4}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Exit Day Distribution */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Exit Timing</div>
              <div className="card-subtitle">When trades close — avg {sim.avg_hold_days} days, median {sim.median_hold_days} days</div>
            </div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={exitDist} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="exitGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
                <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#2a3441' }} label={{ value: 'Day', position: 'bottom', fill: '#64748b', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" name="Exits" stroke="#8b5cf6" strokeWidth={2} fill="url(#exitGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Percentile Table */}
      <div className="card">
        <div className="card-title">Return Percentiles</div>
        <div style={{ display: 'flex', justifyContent: 'space-around', padding: '16px 0', flexWrap: 'wrap', gap: 12 }}>
          {Object.entries(sim.percentiles || {}).map(([pct, val]) => (
            <div key={pct} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>P{pct}</div>
              <div style={{
                fontSize: 16, fontWeight: 600, fontFamily: 'var(--font-mono)',
                color: val >= 40 ? 'var(--accent-blue)' : val >= 0 ? 'var(--green)' : 'var(--red)'
              }}>
                {val >= 0 ? '+' : ''}{val}%
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', textAlign: 'center', padding: '8px 0', borderTop: '1px solid var(--border-subtle)' }}>
          P50 = median outcome if you take this trade 10,000 times · P75+ = where your edge lives
        </div>
      </div>
    </div>
  )
}
