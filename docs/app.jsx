// app.jsx — OpsScreener web UI (no build step; Babel transpiles in-browser).
// Two views:
//   • Daily Scan — loads data/latest.json (refreshed nightly by GitHub Actions)
//     and shows the flagged top buys + the full 100-name table.
//   • Calculator — manual single-ticker scoring (logic in screener.js).

const { useState, useMemo, useEffect } = React;
const fmt = window.OPS_fmt;

const STATUS_LABEL = {
  flagged: "Flagged",
  passed_no_flag: "No flag",
  deferred_earnings: "Deferred",
  no_options: "No options",
  fetch_failed: "Fetch failed",
};

function StatusBadge({ status }) {
  return (
    <span className={"status-badge status-" + status}>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

function n(v, d, suffix) {
  if (v == null) return "—";
  return fmt(v, d) + (suffix || "");
}

// ---------- Daily Scan view ----------

function ScanRowTable({ rows }) {
  return (
    <table className="scan-table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Theme</th>
          <th className="r">Price</th>
          <th className="r">Upside</th>
          <th className="r">IV</th>
          <th className="r">Score</th>
          <th className="r">Analysts</th>
          <th className="r">Earnings</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.ticker} className={"row-" + r.status}>
            <td className="tk">{r.ticker}</td>
            <td className="muted">{r.theme}</td>
            <td className="r">{n(r.price, 2)}</td>
            <td className="r">{n(r.mean_upside_pct, 1, "%")}</td>
            <td className="r">{n(r.iv_pct, 1, "%")}</td>
            <td className="r strong">{n(r.iv_adj_score, 2)}</td>
            <td className="r">{r.analyst_count != null ? r.analyst_count : "—"}</td>
            <td className="r">
              {r.days_to_earnings != null ? r.days_to_earnings + "d" : "—"}
            </td>
            <td><StatusBadge status={r.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DailyScan() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Cache-bust so a fresh nightly commit shows up without a hard refresh.
    fetch("data/latest.json?t=" + Date.now())
      .then((res) => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return <div className="card empty">Couldn't load scan data: {error}</div>;
  }
  if (!data) {
    return <div className="card empty">Loading scan…</div>;
  }

  const hasScan = data.generated_at && data.rows && data.rows.length > 0;

  if (!hasScan) {
    return (
      <div className="card empty">
        <h2>No scan yet</h2>
        <p>
          The nightly job hasn't produced data. Trigger it manually: open the
          repo's <b>Actions</b> tab → <b>Refresh stock data</b> → <b>Run
          workflow</b>. It scans all 100 names (~3 min) and commits the results;
          this page will show them on the next load.
        </p>
      </div>
    );
  }

  const flagged = data.rows
    .filter((r) => r.status === "flagged")
    .sort((a, b) => (b.iv_adj_score || 0) - (a.iv_adj_score || 0));
  const safeFlags = flagged.filter((r) => r.tier === "safe");
  const riskyFlags = flagged.filter((r) => r.tier === "risky");
  const deferred = data.rows
    .filter((r) => r.status === "deferred_earnings")
    .sort((a, b) => (b.iv_adj_score || 0) - (a.iv_adj_score || 0));

  // Full table: flagged first, then by score.
  const order = { flagged: 0, deferred_earnings: 1, passed_no_flag: 2, no_options: 3, fetch_failed: 4 };
  const allRows = [...data.rows].sort((a, b) => {
    const o = (order[a.status] ?? 9) - (order[b.status] ?? 9);
    if (o !== 0) return o;
    return (b.iv_adj_score || 0) - (a.iv_adj_score || 0);
  });

  return (
    <div>
      <div className="scan-meta">
        <div>
          <span className="big">{data.flagged}</span> flagged
          <span className="sep">·</span>
          <span className="big">{data.deferred}</span> deferred
          <span className="sep">·</span>
          {data.scanned} scanned
          {data.failed ? <span className="sep">·</span> : null}
          {data.failed ? <span className="warn">{data.failed} failed</span> : null}
        </div>
        <div className="asof">as of {data.as_of_date}</div>
      </div>

      {data.partial_warning ? (
        <div className="banner-warn">
          ⚠ More than 30% of names failed to fetch — Yahoo may be rate-limiting.
          Results are partial.
        </div>
      ) : null}

      <div className="card">
        <h2>Top buys — Safe ({safeFlags.length})</h2>
        {safeFlags.length ? (
          <ScanRowTable rows={safeFlags} />
        ) : (
          <p className="muted">No safe-tier names flagged today.</p>
        )}
      </div>

      <div className="card">
        <h2>Top buys — Risky ({riskyFlags.length})</h2>
        {riskyFlags.length ? (
          <ScanRowTable rows={riskyFlags} />
        ) : (
          <p className="muted">No risky-tier names flagged today.</p>
        )}
      </div>

      {deferred.length ? (
        <div className="card">
          <h2>Deferred — earnings within 14 days ({deferred.length})</h2>
          <p className="muted">
            These would have flagged, but IV is inflated near earnings. Revisit
            after the print.
          </p>
          <ScanRowTable rows={deferred} />
        </div>
      ) : null}

      <div className="card">
        <h2>Full universe ({allRows.length})</h2>
        <ScanRowTable rows={allRows} />
      </div>
    </div>
  );
}

// ---------- Calculator view (manual) ----------

function Field({ label, hint, value, onChange, step }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(e.target.value)}
      />
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}

function Calculator() {
  const watchlist = window.WATCHLIST || [];
  const [tier, setTier] = useState("safe");
  const [ticker, setTicker] = useState("");
  const [theme, setTheme] = useState("");
  const [form, setForm] = useState({
    price: "", meanTarget: "", lowTarget: "", highTarget: "",
    ivPct: "", analystCount: "", marketCapB: "", ma50: "", daysToEarnings: "",
  });
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  function onPick(sym) {
    setTicker(sym);
    const row = watchlist.find((r) => r.ticker === sym);
    if (row) { setTier(row.tier); setTheme(row.theme); }
  }

  const result = useMemo(() => window.scoreTicker({ tier, ...form }), [tier, form]);

  return (
    <div className="layout">
      <div className="card">
        <h2>Inputs</h2>
        <div className="field">
          <label>Ticker (prefills tier &amp; theme)</label>
          <select value={ticker} onChange={(e) => onPick(e.target.value)}>
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
            <button className={tier === "safe" ? "active" : ""} onClick={() => setTier("safe")}>Safe</button>
            <button className={tier === "risky" ? "active" : ""} onClick={() => setTier("risky")}>Risky</button>
          </div>
        </div>
        <div className="grid2">
          <Field label="Current price" value={form.price} onChange={set("price")} step="0.01" />
          <Field label="50-day MA" value={form.ma50} onChange={set("ma50")} step="0.01" />
        </div>
        <div className="grid2">
          <Field label="Mean target" value={form.meanTarget} onChange={set("meanTarget")} step="0.01" />
          <Field label="6-mo ATM IV (%)" hint="blank = no options data" value={form.ivPct} onChange={set("ivPct")} step="0.1" />
        </div>
        <div className="grid2">
          <Field label="Low target" value={form.lowTarget} onChange={set("lowTarget")} step="0.01" />
          <Field label="High target" value={form.highTarget} onChange={set("highTarget")} step="0.01" />
        </div>
        <div className="grid2">
          <Field label="Analyst count" value={form.analystCount} onChange={set("analystCount")} step="1" />
          <Field label="Market cap ($B)" value={form.marketCapB} onChange={set("marketCapB")} step="0.1" />
        </div>
        <Field label="Days to earnings" hint="blank = treated as not soon" value={form.daysToEarnings} onChange={set("daysToEarnings")} step="1" />
      </div>

      <div className="card">
        <h2>Result {ticker ? "· " + ticker : ""}</h2>
        <StatusBadge status={result.status} />
        <div className="score-big">
          {result.ivAdjScore != null ? fmt(result.ivAdjScore, 2) : "—"}
          <span className="unit"> iv-adj score</span>
        </div>
        <div className="metrics">
          <div className="metric"><div className="k">Mean upside</div><div className="v">{n(result.meanUpside, 1, "%")}</div></div>
          <div className="metric"><div className="k">Upside range</div><div className="v">{n(result.lowUpside, 0, "%")} – {n(result.highUpside, 0, "%")}</div></div>
          <div className="metric"><div className="k">IV</div><div className="v">{n(result.ivPct, 1, "%")}</div></div>
          <div className="metric"><div className="k">Above 50-day MA</div><div className="v">{result.aboveMa == null ? "—" : result.aboveMa ? "yes" : "no"}</div></div>
        </div>
        <ul className="checks">
          {result.checks.map((c, i) => (
            <li key={i} className={c.pass ? "pass" : "fail"}>
              <span><span className="mark">{c.pass ? "✓" : "✗"}</span>{c.label}</span>
              <span className="val">{c.value}</span>
            </li>
          ))}
        </ul>
        <div className="note">Thresholds reflect the <b>{tier}</b> tier. Research tool, not financial advice.</div>
      </div>
    </div>
  );
}

// ---------- Shell ----------

function App() {
  const [tab, setTab] = useState("scan");
  return (
    <div className="wrap">
      <header>
        <h1>OpsScreener</h1>
        <p className="sub">
          IV-adjusted upside screening for 100 AI names. Daily scan refreshes
          nightly after market close.
        </p>
        <div className="formula">iv_adj_score = mean_upside_% / IV_%</div>
      </header>

      <div className="tabs">
        <button className={tab === "scan" ? "active" : ""} onClick={() => setTab("scan")}>Daily Scan</button>
        <button className={tab === "calc" ? "active" : ""} onClick={() => setTab("calc")}>Calculator</button>
      </div>

      {tab === "scan" ? <DailyScan /> : <Calculator />}

      <footer>OpsScreener · static site · data via nightly GitHub Action · research, not advice</footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
