import React from 'react'

const SECTIONS = [
  {
    title: 'What this console does',
    body: `Every weeknight after the market closes, our system scans ~100 AI and tech stocks looking for a specific setup: a stock that's breaking out with strong momentum, where the options market is charging relatively little for call options. When it finds one, it recommends buying a call option that expires about 6 weeks out. The goal on every trade is +40% on the option within 30 days. Trades that go wrong are cut at -50%. It's a numbers game: we expect to lose more often than we win, but winners are bigger than losers.`,
  },
  {
    title: 'How to use it each morning',
    body: `Open the Today tab. If there's a SELL card, that position hit an exit rule overnight — the card says exactly why in plain English. If there's a BUY card, it names the exact option contract (ticker, strike, expiration, rough price) and why the system likes it. If there's nothing, there's nothing to do — most days that's the right answer. The Holding table is your open book; green is winning, red is losing, and the system watches all exits automatically.`,
  },
  {
    title: 'What is a call option? (60-second version)',
    body: `A call option is a contract that goes up in value when the stock goes up — but faster. Buying the NVDA $155 call for $4.85 means you pay $485 (options cover 100 shares) for the right to profit from NVDA rising above $155 before expiration. If NVDA jumps 8%, that option might gain 40-80%. If NVDA goes nowhere, the option slowly loses value every day (that's "time decay" — the reason we never hold past 14 days to expiration). Maximum loss is only what you paid — never more.`,
  },
  {
    title: 'Reading the key numbers',
    body: `ALPHA SCORE (0-100): how strongly the setup matches our criteria — above 70 is rare and strong. IV RANK: how expensive options are vs the past year — we buy when it's LOW (under 30%) because we're buying, not selling. RSI: momentum thermometer — 55-70 is the sweet spot, above 78 means overheated and we skip it. DELTA (~0.27): roughly the market's odds the option finishes in the money; also how much the option moves per $1 of stock move. DTE: days to expiration.`,
  },
  {
    title: 'The risk rules (why they exist)',
    body: `Max 4% of capital per trade — one blown trade can't hurt the account. Max 8 positions at once, max 3 in the same sector — diversification. No new trades when VIX is above 25 or the S&P is below its 50-day trend — momentum strategies historically lose money in fearful markets (this is the "regime filter" banner on the Today tab). Never hold through the last 14 days before expiration — time decay accelerates and eats winners.`,
  },
  {
    title: 'What the Monte Carlo tab shows',
    body: `Before recommending a trade, we simulate it 10,000 times using a statistical model of how the stock could move (including rare crash days). The rings show the odds: chance of any profit, chance of hitting our +40% target, chance of getting stopped out. The histogram shows every simulated outcome — the tall bars left of zero are why we size positions small, and the long right tail is where the strategy makes its money.`,
  },
  {
    title: 'Honest limitations',
    body: `Prices and volatility come from free end-of-day data (Yahoo), so entries/exits assume you trade near the next day's open. Historical options prices are estimated with a pricing model, not real quotes — real fills will be somewhat worse due to bid-ask spreads. The paper portfolio is a simulation, not a brokerage account. Past performance, simulated or real, doesn't guarantee anything. This is research tooling, not financial advice.`,
  },
]

export default function Guide() {
  return (
    <div style={{ maxWidth: 780 }}>
      {SECTIONS.map((s, i) => (
        <div className="card" key={i}>
          <div className="card-title" style={{ marginBottom: 8 }}>{s.title}</div>
          <div style={{ fontSize: 14, lineHeight: 1.75, color: 'var(--text-secondary)' }}>{s.body}</div>
        </div>
      ))}
    </div>
  )
}
