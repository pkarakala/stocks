import React, { useState, useEffect } from 'react'
import Today from './views/Today'
import Dashboard from './views/Dashboard'
import Signals from './views/Signals'
import Explorer from './views/Explorer'
import Backtest from './views/Backtest'
import MonteCarlo from './views/MonteCarlo'
import Guide from './views/Guide'
import sampleData from './sampleData'

const TABS = [
  { id: 'today', label: 'Today' },
  { id: 'signals', label: 'Signals' },
  { id: 'explorer', label: 'Explorer' },
  { id: 'dashboard', label: 'Performance' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'montecarlo', label: 'Monte Carlo' },
  { id: 'guide', label: 'Guide' },
]

// How stale is the data? Team should know if the nightly job silently died.
function dataAge(generatedAt) {
  if (!generatedAt) return { label: 'sample data', stale: true }
  const hours = Math.floor((Date.now() - new Date(generatedAt).getTime()) / 3600000)
  const days = Math.floor(hours / 24)
  const label = hours < 1 ? 'updated just now'
    : hours < 24 ? `updated ${hours}h ago`
    : days === 1 ? 'updated yesterday'
    : `updated ${days} days ago`
  return { label, stale: days >= 4 }
}

export default function App() {
  const [activeTab, setActiveTab] = useState('today')
  const [data, setData] = useState(null)

  useEffect(() => {
    // Relative path works both on the dev server and GitHub Pages subpaths.
    // Cache-bust so the nightly refresh shows up without a hard reload.
    fetch(`data/latest.json?t=${Date.now()}`)
      .then(r => r.ok ? r.json() : null)
      .catch(() => null)
      .then(d => setData(d || sampleData))
  }, [])

  if (!data) {
    return (
      <div className="app">
        <div className="empty-state">
          <h2>Loading Quant Console...</h2>
          <p>Initializing data feeds and signal engine.</p>
        </div>
      </div>
    )
  }

  const regime = data.regime || {}
  const age = dataAge(data.generated_at)

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">Quant Console</div>
          <span className={`regime-badge ${regime.status === 'BULLISH' ? 'bullish' : 'bearish'}`}>
            <span className="dot"></span>
            {regime.status || 'UNKNOWN'}
          </span>
          <span
            className="badge"
            style={{
              background: age.stale ? 'var(--yellow-bg)' : 'var(--bg-card)',
              color: age.stale ? 'var(--yellow)' : 'var(--text-tertiary)',
            }}
            title={age.stale ? 'Data may be stale — check the GitHub Actions tab' : ''}
          >
            {age.stale ? '⚠ ' : ''}{age.label}
          </span>
        </div>
        <div className="header-meta">
          <span>VIX {regime.vix?.toFixed(1) || '—'}</span>
          <span>|</span>
          <span>{data.signal_count || 0} signals</span>
          <span>|</span>
          <span>{data.date || 'no data'}</span>
        </div>
      </header>

      {/* Navigation */}
      <nav className="nav">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <main className="main">
        {activeTab === 'today' && <Today data={data} />}
        {activeTab === 'signals' && <Signals data={data} />}
        {activeTab === 'explorer' && <Explorer data={data} />}
        {activeTab === 'dashboard' && <Dashboard data={data} />}
        {activeTab === 'backtest' && <Backtest data={data} />}
        {activeTab === 'montecarlo' && <MonteCarlo data={data} />}
        {activeTab === 'guide' && <Guide />}
      </main>
    </div>
  )
}
