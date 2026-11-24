"""
Build the project showcase page from the pipeline's outputs.

    python site/build_site.py          (standard library only)

Writes site/data.js (every number on the page) and copies the images the page
uses into site/images/. Dashboard screenshots appear automatically once these
files exist in images/:
    dashboard_overview.png, dashboard_themes.png, dashboard_drilldown.png
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = ROOT / "outputs"

# ---- edit these -----------------------------------------------------------
REPO_URL = "https://github.com/rahulsuxsena1/Data-analyst"
BRANCH = "main"
AUTHOR = ""          # e.g. "Your Name" (shown in the footer when set)
LINKEDIN = ""        # e.g. "https://www.linkedin.com/in/your-profile"
# --------------------------------------------------------------------------

SHOTS = [
    ("dashboard_overview.png", "1 · Overview",
     "KPI cards, 3-month rolling rating trend, sample-size-adjusted brand ranking."),
    ("dashboard_themes.png", "2 · Complaint Themes",
     "How often vs how much it costs, brand × theme matrix, theme trend, service by region."),
    ("dashboard_drilldown.png", "3 · Drill-down & Early Warning",
     "Six slicers, the reviews themselves, the Velora control chart and every alert."),
]


def rows(name: str) -> list[dict]:
    with open(OUT / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x: str) -> float | None:
    return float(x) if x not in ("", None) else None


def main():
    pr = rows("theme_priority.csv")
    priority = [{"theme": r["theme"], "often": num(r["pct_reviews_complaining"]),
                 "perComplaint": -num(r["stars_lost_per_complaint"]),
                 "cost": num(r["stars_lost_per_100_reviews"]),
                 "naiveRank": int(r["naive_rank"]), "impactRank": int(r["impact_rank"])} for r in pr]

    cc = rows("control_chart_data.csv")

    def series(brand, metric):
        out = {}
        for r in cc:
            if r["brand"] == brand and r["metric"] == metric and r["period"] >= "2021Q1":
                tested = r["tested"] == "True"
                out[r["period"]] = {"rate": num(r["rate"]), "limit": num(r["upper_limit"]) if tested else None,
                                    "baseline": num(r["baseline"]), "alert": r["alert"] == "True", "n": int(r["n"])}
        return out

    rel, low = series("Velora", "reliability"), series("Velora", "low_rating")
    velora = [{"period": p, "rel": rel[p], "low": low[p]} for p in sorted(rel)]

    brands = [{"brand": r["brand"], "reviews": int(r["reviews"]), "avg": num(r["avg_rating"]),
               "adjusted": num(r["shrunk_mean"]), "lo": num(r["ci_low"]), "hi": num(r["ci_high"])}
              for r in rows("brand_ranking.csv")]
    norvik = [{"year": int(r["review_year"]), "norvik": num(r["Norvik"]), "others": num(r["All other brands"])}
              for r in rows("service_trend_norvik.csv")]
    models = [{"model": r["model"], "accuracy": num(r["accuracy"]), "f1": num(r["macro_f1"])}
              for r in rows("model_metrics.csv")]
    checks = rows("validation_checks.csv")
    tagger = [{"theme": r["theme"], "precision": num(r["precision"]), "recall": num(r["recall"])}
              for r in rows("theme_tagger_validation.csv")]
    cleaning = [{"step": r["step"], "before": int(r["rows_before"]), "after": int(r["rows_after"]),
                 "note": r["note"]} for r in rows("cleaning_steps.csv")]
    scen = [{"scenario": r["scenario"], "before": num(r["scope_avg_before"]), "after": num(r["scope_avg_after"]),
             "removed": int(r["complaints_removed"])} for r in rows("scenarios.csv")]
    alerts = [r for r in rows("alerts.csv") if r["metric"] != "low_rating"]
    tests = sum(1 for r in cc if r["metric"] != "low_rating" and r["tested"] == "True")
    q09 = rows("query_results/q09_worst_model_year_cohorts.csv")
    region = rows("query_results/q10_service_negativity_by_region.csv")
    n_queries = sum(1 for _ in (OUT / "query_results").glob("q*.csv"))

    (SITE / "images").mkdir(exist_ok=True)
    shots = []
    for file, title, caption in SHOTS:
        src = ROOT / "images" / file
        if src.exists():
            shutil.copy2(src, SITE / "images" / file)
        shots.append({"file": f"images/{file}" if src.exists() else None, "title": title, "caption": caption})

    data = {
        "repo": REPO_URL, "blob": f"{REPO_URL}/blob/{BRANCH}", "author": AUTHOR, "linkedin": LINKEDIN,
        "meta": {"rawRows": cleaning[0]["before"], "cleanRows": cleaning[-1]["after"],
                 "brands": len(brands), "queries": n_queries, "tests": tests, "alerts": len(alerts),
                 "realAlerts": sum(1 for a in alerts if a["brand"] == "Velora" and a["metric"] == "reliability"),
                 "checksPassed": sum(c["result"] == "PASS" for c in checks), "checksTotal": len(checks)},
        "priority": priority, "velora": velora, "brands": brands, "norvik": norvik, "models": models,
        "checks": checks, "tagger": tagger, "cleaning": cleaning, "scenarios": scen, "shots": shots,
        "worstCohort": q09[0], "region": region,
    }
    (SITE / "data.js").write_text("// Generated by site/build_site.py from outputs/. Do not edit by hand.\n"
                                  "window.AV = " + json.dumps(data, indent=1) + ";\n", encoding="utf-8")
    print(f"site/data.js written; screenshots found: {sum(1 for s in shots if s['file'])}/3")


if __name__ == "__main__":
    main()
