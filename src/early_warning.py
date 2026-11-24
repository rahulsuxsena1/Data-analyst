"""
Stage 7b: complaint early-warning system.

Question: can we spot a new product or service problem from review text BEFORE
it shows up as a drop in star ratings?

Method (one test, easy to explain):
  For every brand x theme, every quarter, compare
      p1 = share of this quarter's reviews that complain about the theme
      p0 = the same share over the previous 4 quarters (the baseline)
  with a one-sided two-proportion z-test:
      z = (p1 - p0) / sqrt( p * (1 - p) * (1/n1 + 1/n0) ),  p = pooled share of both
  ALERT when z > 3 (about a 1-in-740 chance per test if nothing changed).

Guards against false alarms
  * quarterly, brand-level: monthly or model-level series were too small and noisy
  * baseline must hold >= 150 reviews, current quarter >= 30
  * both n1 and n0 appear in the formula, so a noisy baseline widens the limit

How the design was chosen (documented in docs/insights_report.md, "Method notes"): a first version
(model x month, p-chart, baseline treated as exact) alerted on 27 of 108 series,
mostly noise, and still missed the defect. Each change above was a standard
technique, and the false-alarm count is reported, not hidden.

Known limitation: this catches SUDDEN shifts. A slow drift (a few points worse
every year) moves the baseline along with it. Slow drifts are caught by the
year-over-year trend query instead (sql q05 / q11).

Output  outputs/alerts.csv, outputs/control_chart_data.csv, outputs/alert_lead_time.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
THEMES = ["service", "price", "maintenance", "reliability", "comfort", "mileage"]
BASELINE_QUARTERS = 4
MIN_BASELINE = 150
MIN_CURRENT = 30
Z_ALERT = 3.0


def z_chart(q: pd.DataFrame, hits: str) -> pd.DataFrame:
    """q: one row per quarter with columns period, n and a count column `hits`."""
    q = q.sort_values("period").reset_index(drop=True)
    h0 = q[hits].shift(1).rolling(BASELINE_QUARTERS).sum()
    n0 = q["n"].shift(1).rolling(BASELINE_QUARTERS).sum()
    p0 = h0 / n0
    p1 = q[hits] / q["n"]
    pooled = (h0 + q[hits]) / (n0 + q["n"])          # standard two-proportion z-test
    se = np.sqrt((pooled * (1 - pooled)).clip(lower=1e-6) * (1 / q["n"] + 1 / n0))
    out = pd.DataFrame({"period": q["period"], "n": q["n"], "rate": p1, "baseline": p0,
                        "baseline_n": n0, "upper_limit": p0 + Z_ALERT * se, "z": (p1 - p0) / se})
    out["tested"] = (n0 >= MIN_BASELINE) & (q["n"] >= MIN_CURRENT)
    out["alert"] = out["tested"] & (out["z"] > Z_ALERT)
    return out


def main():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv")
    df["period"] = pd.PeriodIndex(df["review_month"], freq="M").asfreq("Q").astype(str)
    df["low_rating"] = (df["rating"] <= 2).astype(int)

    charts = []
    for brand, g in df.groupby("brand"):
        q = g.groupby("period").agg(n=("review_id", "size"), low_rating=("low_rating", "sum"),
                                    **{t: (f"neg_{t}", "sum") for t in THEMES}).reset_index()
        for metric in THEMES + ["low_rating"]:
            c = z_chart(q[["period", "n", metric]], metric)
            c.insert(0, "metric", metric)
            c.insert(0, "brand", brand)
            charts.append(c)
    chart = pd.concat(charts, ignore_index=True)
    chart.round(4).to_csv(OUT / "control_chart_data.csv", index=False)

    alerts = chart[chart["alert"]].copy()
    alerts.round(3).to_csv(OUT / "alerts.csv", index=False)
    theme_tests = chart[(chart["metric"] != "low_rating") & chart["tested"]]
    theme_alerts = alerts[alerts["metric"] != "low_rating"]
    print(f"theme tests run: {len(theme_tests)}; alerts: {len(theme_alerts)} "
          f"(expected by chance at z>3: {len(theme_tests) * 0.00135:.1f})")
    print(alerts[["brand", "metric", "period", "n", "rate", "baseline", "z"]].round(3).to_string(index=False))

    # lead time: for each theme alert, when did the brand's share of 1-2 star
    # reviews move? (a) its own z-test alert, (b) the first quarter where it
    # was even 1 percentage point above its baseline
    rows = []
    low = chart[chart["metric"] == "low_rating"].set_index(["brand", "period"])
    for _, a in theme_alerts.iterrows():
        lr = low.loc[a["brand"]]
        after = lr[lr.index >= a["period"]]
        fired = after[after["alert"]]
        rows.append({"brand": a["brand"], "theme": a["metric"], "theme_alert": a["period"],
                     "theme_rate": round(a["rate"], 3), "theme_baseline": round(a["baseline"], 3),
                     "low_rating_share_same_quarter": round(after.iloc[0]["rate"], 3),
                     "low_rating_baseline": round(after.iloc[0]["baseline"], 3),
                     "low_rating_alert": fired.index.min() if len(fired) else "never fired"})
    lt = pd.DataFrame(rows)
    lt.to_csv(OUT / "alert_lead_time.csv", index=False)
    print(lt.to_string(index=False))


if __name__ == "__main__":
    main()
