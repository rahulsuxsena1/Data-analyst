"""
Stage 3a: load the cleaned, tagged and scored data into SQLite.

Output  autovoice.db
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "autovoice.db"


def main():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv")
    themes = pd.read_csv(ROOT / "data" / "clean" / "review_themes.csv")

    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript((ROOT / "sql" / "schema.sql").read_text())

    brands = pd.DataFrame({"brand": sorted(df["brand"].unique())})
    brands["brand_id"] = range(1, len(brands) + 1)
    models = df[["brand", "model"]].drop_duplicates().merge(brands, on="brand") \
        .sort_values(["brand", "model"]).reset_index(drop=True)
    models["model_id"] = range(1, len(models) + 1)

    brands[["brand_id", "brand"]].to_sql("brands", con, if_exists="append", index=False)
    models[["model_id", "brand_id", "model"]].to_sql("models", con, if_exists="append", index=False)

    r = df.merge(models[["brand", "model", "model_id"]], on=["brand", "model"])
    r["review_date"] = pd.to_datetime(r["review_date"]).dt.strftime("%Y-%m-%d")
    r["verified_purchase"] = r["verified_purchase"].astype(int)
    cols = ["review_id", "model_id", "model_year", "review_date", "review_year", "review_month",
            "rating", "sentiment_label", "predicted_sentiment", "dealer_region", "verified_purchase",
            "word_count", "mixed_flag", "text_rating_conflict", "review_text"]
    r[cols].to_sql("reviews", con, if_exists="append", index=False)
    themes.to_sql("review_themes", con, if_exists="append", index=False)
    con.commit()

    for t in ["brands", "models", "reviews", "review_themes"]:
        print(f"{t:<14} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>7,} rows")
    con.close()


if __name__ == "__main__":
    main()
