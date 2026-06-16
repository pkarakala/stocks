// screener.js — pure, browser-side port of the OpsScreener scoring + filter logic.
// Mirrors 01_ARCHITECTURE.md sections 4 (Scoring) and 5 (Filters & thresholds).
// No network calls — everything here is deterministic math on the inputs you give it.

// Tier-keyed thresholds. These are the ONLY place numbers live (matches config.py intent).
window.THRESHOLDS = {
  safe: {
    minScore: 0.8, // iv_adj_score must be greater than this
    minUpsidePct: 12, // mean analyst upside %
    minAnalysts: 5, // numberOfAnalystOpinions
    minCapB: 10, // market cap floor, in $B
    earningsWindowDays: 14, // flagged is deferred if earnings within this many days
  },
  risky: {
    minScore: 0.6,
    minUpsidePct: 20,
    minAnalysts: 4,
    minCapB: 2,
    earningsWindowDays: 14,
  },
};

// Status values match the Python tool's `status` column (section 6A).
window.STATUS = {
  FLAGGED: "flagged",
  PASSED_NO_FLAG: "passed_no_flag",
  DEFERRED_EARNINGS: "deferred_earnings",
  NO_OPTIONS: "no_options",
};

/**
 * upsidePct — consensus upside of a target vs current price, as a percentage.
 * (target - price) / price * 100
 */
window.upsidePct = function upsidePct(target, price) {
  if (price == null || price <= 0 || target == null) return null;
  return ((target - price) / price) * 100;
};

/**
 * scoreTicker — given one ticker's inputs, compute upside, the IV-adjusted score,
 * evaluate every filter, and return a result object the UI can render directly.
 *
 * Inputs (numbers unless noted):
 *   tier            "safe" | "risky"
 *   price           current price
 *   meanTarget      analyst mean target  (drives the headline score)
 *   lowTarget       analyst low target   (optional, for the range)
 *   highTarget      analyst high target  (optional, for the range)
 *   ivPct           6-month ATM implied volatility, as a PERCENT (e.g. 35 = 35%).
 *                   Leave blank/null to represent "no options data".
 *   analystCount    number of analyst opinions
 *   marketCapB      market cap in $B
 *   ma50            50-day moving average
 *   daysToEarnings  days until next earnings (null = unknown / not soon)
 */
window.scoreTicker = function scoreTicker(input) {
  const t = window.THRESHOLDS[input.tier] || window.THRESHOLDS.safe;
  const S = window.STATUS;

  const price = num(input.price);
  const meanTarget = num(input.meanTarget);
  const ivPct = num(input.ivPct); // null => no options data
  const ma50 = num(input.ma50);
  const marketCapB = num(input.marketCapB);
  const analystCount = num(input.analystCount);
  const daysToEarnings = num(input.daysToEarnings);

  const meanUpside = window.upsidePct(meanTarget, price);
  const lowUpside = window.upsidePct(num(input.lowTarget), price);
  const highUpside = window.upsidePct(num(input.highTarget), price);

  // iv_adj_score = mean_upside_pct / iv_pct   (ivPct is iv*100 from the spec)
  const hasOptions = ivPct != null && ivPct > 0;
  const ivAdjScore =
    hasOptions && meanUpside != null ? meanUpside / ivPct : null;

  const aboveMa = price != null && ma50 != null ? price > ma50 : null;
  const earningsSoon =
    daysToEarnings != null &&
    daysToEarnings >= 0 &&
    daysToEarnings <= t.earningsWindowDays;

  // Each filter as a pass/fail check the UI can list out.
  const checks = [
    {
      label: `IV-adjusted score > ${t.minScore}`,
      value: fmt(ivAdjScore, 2),
      pass: ivAdjScore != null && ivAdjScore > t.minScore,
    },
    {
      label: `Mean upside > ${t.minUpsidePct}%`,
      value: meanUpside != null ? fmt(meanUpside, 1) + "%" : "—",
      pass: meanUpside != null && meanUpside > t.minUpsidePct,
    },
    {
      label: `Analyst count ≥ ${t.minAnalysts}`,
      value: analystCount != null ? String(analystCount) : "—",
      pass: analystCount != null && analystCount >= t.minAnalysts,
    },
    {
      label: `Market cap > $${t.minCapB}B`,
      value: marketCapB != null ? "$" + fmt(marketCapB, 1) + "B" : "—",
      pass: marketCapB != null && marketCapB > t.minCapB,
    },
    {
      label: "Price > 50-day MA",
      value: aboveMa == null ? "—" : aboveMa ? "yes" : "no",
      pass: aboveMa === true,
    },
    {
      label: `Earnings not within ${t.earningsWindowDays} days`,
      value: daysToEarnings != null ? daysToEarnings + "d" : "unknown",
      pass: !earningsSoon,
    },
  ];

  // Determine status, following section 5/6 of the architecture.
  let status;
  if (!hasOptions) {
    status = S.NO_OPTIONS; // can never flag without IV
  } else {
    const nonEarnings = checks.filter(
      (c) => c.label.indexOf("Earnings") === -1
    );
    const allNonEarningsPass = nonEarnings.every((c) => c.pass);
    if (allNonEarningsPass && earningsSoon) {
      status = S.DEFERRED_EARNINGS; // would flag, but earnings too close
    } else if (checks.every((c) => c.pass)) {
      status = S.FLAGGED;
    } else {
      status = S.PASSED_NO_FLAG;
    }
  }

  return {
    tier: input.tier,
    price,
    meanTarget,
    meanUpside,
    lowUpside,
    highUpside,
    ivPct: hasOptions ? ivPct : null,
    ivAdjScore,
    analystCount,
    marketCapB,
    aboveMa,
    daysToEarnings,
    hasOptions,
    earningsSoon,
    checks,
    status,
    thresholds: t,
  };
};

// --- small helpers ---
function num(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : parseFloat(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}
function fmt(v, d) {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(d);
}
window.OPS_fmt = fmt;
