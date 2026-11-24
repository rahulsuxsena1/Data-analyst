"""
Stage 6: model-ready tables for Power BI (a star schema).

    fact_reviews ──< bridge_review_theme
        │
        ├── dim_brand_model   (brand, model)
        └── dim_date          (date, year, quarter, month)
    + theme_priority, brand_ranking, alerts, control_chart  (pre-computed analysis tables)

Why a star schema? Power BI filters flow from dimension tables to fact tables.
One fact table + small dimensions = simple relationships, fast slicers, and
DAX measures that behave predictably.

Output  powerbi_data/*.csv   (load with Get Data -> Text/CSV, see docs/DASHBOARD_GUIDE.md)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi_data"


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv", parse_dates=["review_date"])
    themes = pd.read_csv(ROOT / "data" / "clean" / "review_themes.csv")

    bm = df[["brand", "model"]].drop_duplicates().sort_values(["brand", "model"]).reset_index(drop=True)
    bm.insert(0, "model_key", range(1, len(bm) + 1))
    bm.to_csv(OUT / "dim_brand_model.csv", index=False)

    dates = pd.DataFrame({"date": pd.date_range(df["review_date"].min().replace(day=1), "2025-12-31")})
    dates["year"] = dates["date"].dt.year
    dates["quarter"] = "Q" + dates["date"].dt.quarter.astype(str)
    dates["year_quarter"] = dates["year"].astype(str) + "-" + dates["quarter"]
    dates["month_start"] = dates["date"].dt.to_period("M").dt.start_time
    dates["month_name"] = dates["date"].dt.strftime("%b")
    dates["month_num"] = dates["date"].dt.month
    dates.to_csv(OUT / "dim_date.csv", index=False, date_format="%Y-%m-%d")

    f = df.merge(bm, on=["brand", "model"])
    f["date"] = f["review_date"].dt.strftime("%Y-%m-%d")
    f["is_negative"] = (f["rating"] <= 2).astype(int)
    fact = f[["review_id", "model_key", "date", "model_year", "rating", "sentiment_label",
              "predicted_sentiment", "dealer_region", "verified_purchase", "word_count", "n_themes",
              "mixed_flag", "text_rating_conflict", "is_negative", "review_title", "review_text"]]
    fact.to_csv(OUT / "fact_reviews.csv", index=False)

    bridge = themes.copy()
    bridge["is_negative_mention"] = (bridge["theme_polarity"] == "negative").astype(int)
    bridge.to_csv(OUT / "bridge_review_theme.csv", index=False)

    pd.read_csv(ROOT / "outputs" / "theme_priority.csv").to_csv(OUT / "theme_priority.csv", index=False)
    pd.read_csv(ROOT / "outputs" / "brand_ranking.csv").to_csv(OUT / "brand_ranking.csv", index=False)
    pd.read_csv(ROOT / "outputs" / "alerts.csv").to_csv(OUT / "alerts.csv", index=False)
    pd.read_csv(ROOT / "outputs" / "control_chart_data.csv").to_csv(OUT / "control_chart.csv", index=False)
    pd.read_csv(ROOT / "outputs" / "scenarios.csv").to_csv(OUT / "scenarios.csv", index=False)
    for p in sorted(OUT.glob("*.csv")):
        print(f"powerbi_data/{p.name:<26} {sum(1 for _ in open(p)) - 1:>7,} rows")


if __name__ == "__main__":
    main()
