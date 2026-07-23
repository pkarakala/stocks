import React, { useState } from 'react'

function FactorBar({ name, value, color }) {
  const pct = Math.round(value * 100)
  return (
    <div className="factor-row">
      <div className="factor-name">{name}</div>
      <div className="factor-bar">
        <div
          className="factor-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="factor-value">{pct}%</div>
    </div>
  )
}

function SignalDetail({ signal }) {
  if (!signal) return null

  const factors = [
    { name: 'Momentum', value: signal.momentum_score, color: '#3b82f6' },
    { name: 'Volatility', value: signal.volatility_score, color: '#8b5cf6' },
    { name: 'Flow', value: signal.flow_score, color: '#06b6d4' },
    { name: 'RSI', value: signal.rsi_score, color: '#10b981' },
    { name: 'Rel Strength', value: signal.relative_strength_score, color: '#f59e0b' },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title" style={{ fontSize: 18 }}>
            <span style={{ color: 'var(--accent-blue)' }}>{signal.ticker}</span>
            {' '}&mdash;{' '}
            <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{signal.sector}</span>
          </div>
          <div className="card-subtitle">{signal.rationale}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>
            {(signal.composite_score * 100).toFixed(0)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Alpha Score</div>
        </div>
      </div>

      <div className="grid-3" style={{ marginBottom: 20 }}>
        {/* Price Context */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Price Action
          </div>
          <div style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
            ${signal.price?.toFixed(2)}
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 12 }}>
            <span style={{ color: signal.price_1d_chg_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
              1D: {signal.price_1d_chg_pct >= 0 ? '+' : ''}{signal.price_1d_chg_pct}%
            </span>
            <span style={{ color: signal.price_5d_chg_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
              5D: {signal.price_5d_chg_pct >= 0 ? '+' : ''}{signal.price_5d_chg_pct}%
            </span>
            <span style={{ color: signal.price_20d_chg_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
              20D: {signal.price_20d_chg_pct >= 0 ? '+' : ''}{signal.price_20d_chg_pct}%
            </span>
          </div>
        </div>

        {/* Option Setup */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Option Setup
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Strike</span> <span style={{ fontFamily: 'var(--font-mono)' }}>${signal.suggested_strike}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>DTE</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.suggested_dte}d</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Delta</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.estimated_delta}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Premium</span> <span style={{ fontFamily: 'var(--font-mono)' }}>${signal.estimated_premium}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Leverage</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.estimated_leverage}x</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>IV Rank</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.iv_rank}%</span></div>
          </div>
        </div>

        {/* Risk */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Risk Management
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Target</span> <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>+{signal.target_pnl_pct}%</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Stop</span> <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{signal.stop_loss_pct}%</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>R:R</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.risk_reward_ratio}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Size</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{signal.position_size_pct}%</span></div>
            <div style={{ gridColumn: 'span 2' }}>
              <span style={{ color: 'var(--text-tertiary)' }}>Max Loss</span>{' '}
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>${signal.max_loss_dollars?.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Factor Decomposition */}
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 }}>
        Factor Decomposition
      </div>
      <div className="factor-bars">
        {factors.map(f => (
          <FactorBar key={f.name} name={f.name} value={f.value} color={f.color} />
        ))}
      </div>

      {signal.warnings && (
        <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--yellow-bg)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--yellow)' }}>
          Warning: {signal.warnings}
        </div>
      )}
    </div>
  )
}

export default function Signals({ data }) {
  const signals = data.signals || []
  const [selected, setSelected] = useState(signals[0] || null)

  if (!signals.length) {
    return (
      <div className="empty-state">
        <h2>No Active Signals</h2>
        <p>The alpha engine hasn't generated any signals that meet the minimum threshold. This happens during bearish regimes or when no tickers show sufficient momentum.</p>
      </div>
    )
  }

  return (
    <div>
      {/* Signal Scanner Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Signal Scanner</div>
            <div className="card-subtitle">
              {signals.length} signals ranked by composite alpha score — click for details
            </div>
          </div>
          <div className="badge green">{signals.length} active</div>
        </div>

        <table className="signals-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Sector</th>
              <th className="right">Price</th>
              <th className="right">1D</th>
              <th className="right">Score</th>
              <th className="right">Strike</th>
              <th className="right">DTE</th>
              <th className="right">Delta</th>
              <th className="right">IV Rank</th>
              <th className="right">Size</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((sig, i) => (
              <tr
                key={sig.ticker}
                onClick={() => setSelected(sig)}
                style={{ cursor: 'pointer', background: selected?.ticker === sig.ticker ? 'var(--bg-elevated)' : undefined }}
              >
                <td className="ticker">{sig.ticker}</td>
                <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{sig.sector}</td>
                <td className="right">${sig.price?.toFixed(2)}</td>
                <td className="right" style={{ color: sig.price_1d_chg_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {sig.price_1d_chg_pct >= 0 ? '+' : ''}{sig.price_1d_chg_pct}%
                </td>
                <td className="right">
                  <span className="score-bar">
                    <span style={{ fontWeight: 600 }}>{(sig.composite_score * 100).toFixed(0)}</span>
                    <span className="score-bar-fill">
                      <span
                        className="score-bar-fill-inner"
                        style={{
                          width: `${sig.composite_score * 100}%`,
                          background: sig.composite_score > 0.7 ? 'var(--green)' : sig.composite_score > 0.5 ? 'var(--yellow)' : 'var(--red)'
                        }}
                      />
                    </span>
                  </span>
                </td>
                <td className="right">${sig.suggested_strike}</td>
                <td className="right">{sig.suggested_dte}d</td>
                <td className="right">{sig.estimated_delta}</td>
                <td className="right">{sig.iv_rank}%</td>
                <td className="right">{sig.position_size_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Selected Signal Detail */}
      <SignalDetail signal={selected} />
    </div>
  )
}
