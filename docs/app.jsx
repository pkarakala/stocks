// app.jsx — the OpsScreener calculator UI, in React (no build step; Babel
// transpiles this in the browser). Logic lives in screener.js; data in watchlist.js.

const { useState, useMemo } = React;

const STATUS_LABEL = {
  flagged: "FLAGGED — passes all filters",
  passed_no_flag: "Passed, not flagged",
  deferred_earnings: "Deferred — earnings within window",
  no_options: "No options data — cannot flag",
};

// A single labelled input.
function Field({ label, hint, value, onChange, type = "number", placeholder, step }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        step={step}
        onChange={(e) => onChange(e.target.value)}
      />
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}

function App() {
  const watchlist = window.WATCHLIST || [];

  const [tier, setTier] = useState("safe");
  const [ticker, setTicker] = useState("");
  const [theme, setTheme] = useState("");
  const [form, setForm] = useState({
    price: "",
    meanTarget: "",
    lowTarget: "",
    highTarget: "",
    ivPct: "",
    analystCount: "",
    marketCapB: "",
    ma50: "",
    daysToEarnings: "",
  });

  const set = (key) => (v) => setForm((f) => ({ ...f, [key]: v }));

  // Picking a name from the watchlist prefills tier + theme (the data we know
  // offline). The market numbers you still type in from your data source.
  function onPickTicker(sym) {
    setTicker(sym);
    const row = watchlist.find((r) => r.ticker === sym);
    if (row) {
      setTier(row.tier);
      setTheme(row.theme);
    }
  }

  const result = useMemo(
    () => window.scoreTicker({ tier, ...form }),
    [tier, form]
  );

  const fmt = window.OPS_fmt;

  return (
    <div className="wrap">
      <header>
        <h1>OpsScreener Calculator</h1>
        <p className="sub">
          IV-adjusted upside scoring for the AI names universe. Enter a ticker's
          numbers and see whether it would flag under the {tier} tier rules.
        </p>
        <div className="formula">
          iv_adj_score = mean_upside_% / IV_% &nbsp;·&nbsp; flag if score, upside,
          analysts, cap, momentum &amp; earnings all pass
        </div>
      </header>

      <div className="layout">
        {/* ---------- INPUTS ---------- */}
        <div className="card">
          <h2>Inputs</h2>

          <div className="field">
            <label>Ticker (optional — prefills tier &amp; theme)</label>
            <select value={ticker} onChange={(e) => onPickTicker(e.target.value)}>
              <option value="">— pick from watchlist —</option>
              {watchlist.map((r) => (
                <option key={r.ticker} value={r.ticker}>
                  {r.ticker} · {r.tier} · {r.theme}
                </option>
              ))}
            </select>
            {theme ? <div className="hint">{theme}</div> : null}
          </div>

          <div className="field">
            <label>Tier</label>
            <div className="tier-toggle">
              <button
                className={tier === "safe" ? "active" : ""}
                onClick={() => setTier("safe")}
              >
                Safe
              </button>
              <button
                className={tier === "risky" ? "active" : ""}
                onClick={() => setTier("risky")}
              >
                Risky
              </button>
            </div>
          </div>

          <div className="grid2">
            <Field label="Current price" value={form.price} onChange={set("price")} step="0.01" />
            <Field label="50-day MA" value={form.ma50} onChange={set("ma50")} step="0.01" />
          </div>

          <div className="grid2">
            <Field label="Mean target" value={form.meanTarget} onChange={set("meanTarget")} step="0.01" />
            <Field
              label="6-mo ATM IV (%)"
              hint="blank = no options data"
              value={form.ivPct}
              onChange={set("ivPct")}
              step="0.1"
            />
          </div>

          <div className="grid2">
            <Field label="Low target" value={form.lowTarget} onChange={set("lowTarget")} step="0.01" />
            <Field label="High target" value={form.highTarget} onChange={set("highTarget")} step="0.01" />
          </div>

          <div className="grid2">
            <Field label="Analyst count" value={form.analystCount} onChange={set("analystCount")} step="1" />
            <Field label="Market cap ($B)" value={form.marketCapB} onChange={set("marketCapB")} step="0.1" />
          </div>

          <Field
            label="Days to earnings"
            hint="blank/unknown = treated as not soon"
            value={form.daysToEarnings}
            onChange={set("daysToEarnings")}
            step="1"
          />
        </div>

        {/* ---------- RESULT ---------- */}
        <div className="card">
          <h2>Result {ticker ? "· " + ticker : ""}</h2>

          <div className={"status-badge status-" + result.status}>
            {STATUS_LABEL[result.status]}
          </div>

          <div className="score-big">
            {result.ivAdjScore != null ? fmt(result.ivAdjScore, 2) : "—"}
            <span className="unit"> iv-adj score</span>
          </div>

          <div className="metrics">
            <div className="metric">
              <div className="k">Mean upside</div>
              <div className="v">
                {result.meanUpside != null ? fmt(result.meanUpside, 1) + "%" : "—"}
              </div>
            </div>
            <div className="metric">
              <div className="k">Upside range (low–high)</div>
              <div className="v">
                {result.lowUpside != null ? fmt(result.lowUpside, 0) + "%" : "—"} –{" "}
                {result.highUpside != null ? fmt(result.highUpside, 0) + "%" : "—"}
              </div>
            </div>
            <div className="metric">
              <div className="k">IV</div>
              <div className="v">{result.ivPct != null ? fmt(result.ivPct, 1) + "%" : "—"}</div>
            </div>
            <div className="metric">
              <div className="k">Above 50-day MA</div>
              <div className="v">
                {result.aboveMa == null ? "—" : result.aboveMa ? "yes" : "no"}
              </div>
            </div>
          </div>

          <ul className="checks">
            {result.checks.map((c, i) => (
              <li key={i} className={c.pass ? "pass" : "fail"}>
                <span>
                  <span className="mark">{c.pass ? "✓" : "✗"}</span>
                  {c.label}
                </span>
                <span className="val">{c.value}</span>
              </li>
            ))}
          </ul>

          <div className="note">
            Thresholds shown reflect the <b>{tier}</b> tier. A name is flagged only
            when every check passes. Research tool, not financial advice.
          </div>
        </div>
      </div>

      <footer>
        OpsScreener · client-side calculator · logic ported from 01_ARCHITECTURE.md
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
