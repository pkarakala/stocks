import React from 'react'

function ActionCard({ action, kind }) {
  const colors = {
    BUY: { border: 'var(--green)', bg: 'var(--green-bg)', label: 'BUY' },
    SELL: { border: 'var(--red)', bg: 'var(--red-bg)', label: 'SELL' },
  }
  const c = colors[kind]

  return (
    <div className="card" style={{ borderLeft: `3px solid ${c.border}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span className={`badge ${kind === 'BUY' ? 'green' : 'red'}`} style={{ fontWeight: 700, fontSize: 12 }}>
              {c.label}
            </span>
            <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent-blue)' }}>{action.ticker}</span>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{action.sector}</span>
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)', maxWidth: 640, lineHeight: 1.6 }}>
            {action.explanation}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
          {kind === 'SELL' && (
            <>
              <div style={{
                fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: action.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)'
              }}>
                {action.pnl_pct >= 0 ? '+' : ''}{action.pnl_pct?.toFixed(1)}%
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                ${action.pnl_dollars?.toLocaleString()} · {action.days_held}d held
              </div>
            </>
          )}
          {kind === 'BUY' && (
            <>
              <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                ${action.strike?.toFixed(0)} C
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {action.dte_at_entry} DTE · ~${action.entry_premium?.toFixed(2)}
              </div>
            </>
          )}
        </div>
      </div>
      {/* Trade specifics strip */}
      <div style={{
        display: 'flex', gap: 20, marginTop: 12, paddingTop: 12,
        borderTop: '1px solid var(--border-subtle)', fontSize: 12, fontFamily: 'var(--font-mono)',
        color: 'var(--text-secondary)', flexWrap: 'wrap'
      }}>
        <span>Stock: ${(action.current_underlying ?? action.entry_underlying)?.toFixed(2)}</span>
        <span>Contracts: {action.contracts}</span>
        {kind === 'BUY' && <span>Score: {(action.signal_score * 100)?.toFixed(0)}/100</span>}
        {kind === 'BUY' && <span style={{ color: 'var(--green)' }}>Target: +40%</span>}
        {kind === 'BUY' && <span style={{ color: 'var(--red)' }}>Stop: -50%</span>}
        {kind === 'SELL' && <span>Entry: ${action.entry_premium?.toFixed(2)} → Exit: ${action.exit_premium?.toFixed(2)}</span>}
      </div>
    </div>
  )
}

function HoldRow({ h }) {
  return (
    <tr>
      <td className="ticker">{h.ticker}</td>
      <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{h.sector}</td>
      <td className="right">${h.strike?.toFixed(0)} C</td>
      <td className="right">${h.entry_premium?.toFixed(2)}</td>
      <td className="right">${h.current_premium?.toFixed(2) ?? '—'}</td>
      <td className="right" style={{ color: (h.pnl_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
        {h.pnl_pct != null ? `${h.pnl_pct >= 0 ? '+' : ''}${h.pnl_pct.toFixed(1)}%` : '—'}
      </td>
      <td className="right">{h.days_held ?? 0}d</td>
      <td className="right">{h.dte_remaining ?? '—'}</td>
    </tr>
  )
}

export default function Today({ data }) {
  const actions = data.actions || { buys: [], sells: [], holds: [] }
  const regime = data.regime || {}
  const port = data.portfolio || {}

  return (
    <div>
      {/* Market regime banner — plain English */}
      <div className="card" style={{
        borderLeft: `3px solid ${regime.new_entries_allowed ? 'var(--green)' : 'var(--yellow)'}`,
        display: 'flex', alignItems: 'center', gap: 14
      }}>
        <span style={{ fontSize: 24 }}>{regime.new_entries_allowed ? '🟢' : '🟡'}</span>
        <div>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>
            Market Conditions: {regime.status === 'BULLISH' ? 'Favorable' : 'Unfavorable'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{regime.explanation}</div>
        </div>
      </div>

      {/* Portfolio snapshot */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Open Positions</div>
          <div className="stat-value neutral">{port.open_positions ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Unrealized P&L</div>
          <div className={`stat-value ${(port.unrealized_pnl ?? 0) >= 0 ? 'positive' : 'negative'}`}>
            {(port.unrealized_pnl ?? 0) >= 0 ? '+' : ''}${(port.unrealized_pnl ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Realized P&L</div>
          <div className={`stat-value ${(port.realized_pnl ?? 0) >= 0 ? 'positive' : 'negative'}`}>
            {(port.realized_pnl ?? 0) >= 0 ? '+' : ''}${(port.realized_pnl ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Closed Trades</div>
          <div className="stat-value neutral">{port.closed_trades ?? 0}</div>
          <div className="stat-change">{port.win_rate_pct ?? 0}% winners</div>
        </div>
      </div>

      {/* SELLS — most urgent, shown first */}
      {actions.sells?.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '20px 0 10px', color: 'var(--red)' }}>
            🔻 Sell Today ({actions.sells.length})
          </h3>
          {actions.sells.map((a, i) => <ActionCard key={i} action={a} kind="SELL" />)}
        </>
      )}

      {/* BUYS */}
      {actions.buys?.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '20px 0 10px', color: 'var(--green)' }}>
            🔺 Buy Today ({actions.buys.length})
          </h3>
          {actions.buys.map((a, i) => <ActionCard key={i} action={a} kind="BUY" />)}
        </>
      )}

      {!actions.buys?.length && !actions.sells?.length && (
        <div className="card empty-state" style={{ padding: 40 }}>
          <h2>No trades today</h2>
          <p>
            {regime.new_entries_allowed
              ? 'Nothing passed the screen and no open position hit an exit rule. Patience is a position.'
              : 'New entries are paused because market conditions are unfavorable. Existing positions are still being managed.'}
          </p>
        </div>
      )}

      {/* HOLDS */}
      {actions.holds?.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Holding ({actions.holds.length})</div>
              <div className="card-subtitle">Open positions being managed — no action needed today</div>
            </div>
          </div>
          <table className="signals-table">
            <thead>
              <tr>
                <th>Ticker</th><th>Sector</th>
                <th className="right">Contract</th>
                <th className="right">Entry</th>
                <th className="right">Now</th>
                <th className="right">P&L</th>
                <th className="right">Held</th>
                <th className="right">DTE</th>
              </tr>
            </thead>
            <tbody>
              {actions.holds.map((h, i) => <HoldRow key={i} h={h} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
