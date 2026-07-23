import React, { useState, useMemo } from 'react'

function Sparkline({ data, width = 120, height = 32 }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x},${y}`
  }).join(' ')
  const up = data[data.length - 1] >= data[0]

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline
        points={points}
        fill="none"
        stroke={up ? 'var(--green)' : 'var(--red)'}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function GaugeBar({ label, value, min, max, goodLow, formatValue }) {
  // Position of value on the [min, max] scale, clamped
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
          {formatValue ? formatValue(value) : value}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, background: 'var(--bg-elevated)', borderRadius: 3 }}>
        <div style={{
          position: 'absolute', left: `${pct}%`, top: -2, width: 3, height: 10,
          background: 'var(--text-primary)', borderRadius: 2, transform: 'translateX(-50%)'
        }} />
        <div style={{
          height: '100%', borderRadius: 3, width: '100%',
          background: goodLow
            ? 'linear-gradient(90deg, var(--green) 0%, var(--yellow) 55%, var(--red) 100%)'
            : 'linear-gradient(90deg, var(--red) 0%, var(--yellow) 45%, var(--green) 100%)',
          opacity: 0.35
        }} />
      </div>
    </div>
  )
}

function TickerDetail({ t }) {
  if (!t) return null
  return (
    <div className="card" style={{ borderLeft: `3px solid ${t.has_signal ? 'var(--green)' : 'var(--border)'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-blue)' }}>{t.ticker}</span>
            <span className="badge blue">{t.sector}</span>
            {t.has_signal
              ? <span className="badge green">✓ passes screen</span>
              : <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>not a buy</span>}
          </div>
          <div style={{ fontSize: 26, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 6 }}>
            ${t.price?.toFixed(2)}
            <span style={{
              fontSize: 14, marginLeft: 10,
              color: t.pct_1d >= 0 ? 'var(--green)' : 'var(--red)'
            }}>
              {t.pct_1d >= 0 ? '+' : ''}{t.pct_1d}% today
            </span>
          </div>
        </div>
        <Sparkline data={t.sparkline} width={180} height={48} />
      </div>

      {/* Plain-English summary — the centerpiece */}
      <div style={{
        padding: '14px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
        fontSize: 14, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 16,
        border: '1px solid var(--border-subtle)'
      }}>
        {t.summary}
      </div>

      <div className="grid-2">
        <div>
          <GaugeBar label="Momentum (RSI)" value={t.rsi} min={0} max={100} goodLow={false}
            formatValue={v => `${v} ${v > 70 ? '(overheated)' : v > 55 ? '(healthy)' : v > 45 ? '(neutral)' : '(weak)'}`} />
          <GaugeBar label="Option cost (IV Rank)" value={t.iv_rank} min={0} max={100} goodLow={true}
            formatValue={v => `${v}% ${v < 30 ? '(cheap ✓)' : v < 60 ? '(fair)' : '(expensive ✗)'}`} />
          <GaugeBar label="Volume vs normal" value={Math.min(t.volume_ratio, 3)} min={0} max={3} goodLow={false}
            formatValue={() => `${t.volume_ratio}x`} />
        </div>
        <div style={{ fontSize: 13 }}>
          <table className="signals-table">
            <tbody>
              <tr><td style={{ color: 'var(--text-secondary)' }}>1-week move</td>
                <td className="right" style={{ color: t.pct_5d >= 0 ? 'var(--green)' : 'var(--red)' }}>{t.pct_5d >= 0 ? '+' : ''}{t.pct_5d}%</td></tr>
              <tr><td style={{ color: 'var(--text-secondary)' }}>1-month move</td>
                <td className="right" style={{ color: t.pct_20d >= 0 ? 'var(--green)' : 'var(--red)' }}>{t.pct_20d >= 0 ? '+' : ''}{t.pct_20d}%</td></tr>
              <tr><td style={{ color: 'var(--text-secondary)' }}>Short trend (EMA9/21)</td>
                <td className="right">{t.ema9 > t.ema21 ? '↑ bullish' : '↓ bearish'}</td></tr>
              <tr><td style={{ color: 'var(--text-secondary)' }}>Long trend (above EMA50)</td>
                <td className="right">{t.above_trend ? '↑ yes' : '↓ no'}</td></tr>
              <tr><td style={{ color: 'var(--text-secondary)' }}>Annualized volatility</td>
                <td className="right">{(t.realized_vol * 100).toFixed(0)}%</td></tr>
              {t.signal_score != null && (
                <tr><td style={{ color: 'var(--text-secondary)' }}>Alpha score</td>
                  <td className="right" style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>{(t.signal_score * 100).toFixed(0)}/100</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function Explorer({ data }) {
  const explorer = data.explorer || []
  const [query, setQuery] = useState('')
  const [sectorFilter, setSectorFilter] = useState('all')
  const [selected, setSelected] = useState(null)

  const sectors = useMemo(
    () => ['all', ...new Set(explorer.map(t => t.sector).filter(Boolean))],
    [explorer]
  )

  const filtered = useMemo(() => {
    let rows = explorer
    if (query) {
      const q = query.toUpperCase()
      rows = rows.filter(t => t.ticker.includes(q) || t.sector?.toUpperCase().includes(q))
    }
    if (sectorFilter !== 'all') {
      rows = rows.filter(t => t.sector === sectorFilter)
    }
    return rows
  }, [explorer, query, sectorFilter])

  const shown = selected || filtered[0]

  if (!explorer.length) {
    return (
      <div className="empty-state">
        <h2>No explorer data yet</h2>
        <p>Run the pipeline (or wait for tonight's automatic refresh) to populate per-stock quant data.</p>
      </div>
    )
  }

  return (
    <div>
      {/* Search bar */}
      <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', padding: 14 }}>
        <input
          type="text"
          placeholder="Search ticker or sector…  (e.g. NVDA, chips)"
          value={query}
          onChange={e => { setQuery(e.target.value); setSelected(null) }}
          style={{
            flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--text-primary)',
            fontSize: 14, fontFamily: 'var(--font-sans)', outline: 'none'
          }}
        />
        <select
          value={sectorFilter}
          onChange={e => { setSectorFilter(e.target.value); setSelected(null) }}
          style={{
            background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--text-primary)',
            fontSize: 13, outline: 'none'
          }}
        >
          {sectors.map(s => <option key={s} value={s}>{s === 'all' ? 'All sectors' : s}</option>)}
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
          {filtered.length} names
        </span>
      </div>

      {/* Selected detail */}
      <TickerDetail t={shown} />

      {/* Results table */}
      <div className="card">
        <table className="signals-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Sector</th>
              <th className="right">Price</th>
              <th className="right">1D</th>
              <th className="right">1M</th>
              <th className="right">RSI</th>
              <th className="right">IV Rank</th>
              <th>Trend</th>
              <th>Screen</th>
              <th className="right">Chart</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <tr
                key={t.ticker}
                onClick={() => setSelected(t)}
                style={{ cursor: 'pointer', background: shown?.ticker === t.ticker ? 'var(--bg-elevated)' : undefined }}
              >
                <td className="ticker">{t.ticker}</td>
                <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{t.sector}</td>
                <td className="right">${t.price?.toFixed(2)}</td>
                <td className="right" style={{ color: t.pct_1d >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {t.pct_1d >= 0 ? '+' : ''}{t.pct_1d}%
                </td>
                <td className="right" style={{ color: t.pct_20d >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {t.pct_20d >= 0 ? '+' : ''}{t.pct_20d}%
                </td>
                <td className="right">{t.rsi}</td>
                <td className="right">{t.iv_rank}%</td>
                <td>{t.ema9 > t.ema21 ? <span style={{ color: 'var(--green)' }}>↑</span> : <span style={{ color: 'var(--red)' }}>↓</span>}</td>
                <td>
                  {t.has_signal
                    ? <span className="badge green">buy</span>
                    : <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>}
                </td>
                <td className="right"><Sparkline data={t.sparkline} width={80} height={22} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
