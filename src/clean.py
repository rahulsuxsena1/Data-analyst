"""
Stage 2: clean the raw export and log every decision.

Input   data/raw/reviews.csv
Output  data/clean/reviews_clean.csv
        docs/cleaning_log.md   (auto-generated, before/after counts per step)
"""
from __future__ import annotations

import difflib
import html
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "reviews.csv"
OUT = ROOT / "data" / "clean" / "reviews_clean.csv"
LOG = ROOT / "docs" / "cleaning_log.md"

CANONICAL_BRANDS = ["Aurex", "Kestrel", "Solano", "Tamaru", "Norvik", "Velora", "Zephyr", "Brixton"]
BRAND_ALIASES = {"tamaru motors": "Tamaru"}          # known trading-name variants
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"]  # source exports DD/MM, documented
EXTRACTION_DATE = pd.Timestamp("2025-12-31")
EMPTY_TEXT = {"", "n/a", "na", "none", "null", "-"}


class Log:
    def __init__(self):
        self.rows: list[tuple[str, int, int, str]] = []

    def step(self, name: str, before: int, after: int, note: str):
        self.rows.append((name, before, after, note))
        print(f"{name:<45} {before:>6,} -> {after:>6,}  {note}")


def canon_brand(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    key = re.sub(r"\s+", " ", raw.strip()).lower()
    if key in BRAND_ALIASES:
        return BRAND_ALIASES[key]
    lower = {b.lower(): b for b in CANONICAL_BRANDS}
    if key in lower:
        return lower[key]
    match = difflib.get_close_matches(key, lower, n=1, cutoff=0.8)  # catches typos
    return lower[match[0]] if match else None


def parse_rating(x) -> float | None:
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(x))
    return float(m.group(1)) if m else None


def parse_date(x) -> pd.Timestamp:
    if not isinstance(x, str) or not x.strip():
        return pd.NaT
    for fmt in DATE_FORMATS:
        try:
            return pd.Timestamp(datetime.strptime(x.strip(), fmt))
        except ValueError:
            continue
    return pd.NaT


def clean_text(x) -> str:
    if not isinstance(x, str):
        return ""
    x = html.unescape(x)
    x = re.sub(r"<[^>]+>", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def main() -> pd.DataFrame:
    log = Log()
    df = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    n0 = len(df)
    log.step("Load raw export", n0, n0, f"{df.shape[1]} columns")

    # 1. exact duplicates (all columns identical, including review_id)
    b = len(df)
    df = df.drop_duplicates()
    log.step("Drop exact duplicate rows", b, len(df), "export glitch: identical rows")

    # 2. trim whitespace everywhere
    for c in df.columns:
        df[c] = df[c].str.strip()

    # 3. brands
    b = len(df)
    raw_brands = df["brand"].copy()
    df["brand"] = df["brand"].map(canon_brand)
    fixed = int((raw_brands != df["brand"]).sum())
    unknown = int(df["brand"].isna().sum())
    df = df[df["brand"].notna()]
    log.step("Standardise brand names", b, len(df),
             f"{fixed:,} variants mapped (case, spacing, typos, aliases); {unknown} unmappable dropped")

    # 4. model names
    before_models = df["model"].nunique()
    df["model"] = df["model"].str.strip().str.title().str.replace(r"^K(\d)$", r"K\1", regex=True)
    log.step("Standardise model names", len(df), len(df),
             f"distinct models {before_models} -> {df['model'].nunique()}")

    # 5. ratings: parse '4 stars', drop missing / out-of-scale
    b = len(df)
    df["rating"] = df["rating"].map(parse_rating)
    missing = int(df["rating"].isna().sum())
    invalid = int((df["rating"].notna() & ~df["rating"].between(1, 5)).sum())
    df = df[df["rating"].between(1, 5)]
    df["rating"] = df["rating"].astype(int)
    log.step("Parse ratings, drop missing/out-of-scale", b, len(df),
             f"{missing} missing, {invalid} outside 1-5 (0, 6, 10, -1). "
             "Dropped: the rating is the target for every question")

    # 6. dates
    b = len(df)
    df["review_date"] = df["review_date"].map(parse_date)
    missing_d = int(df["review_date"].isna().sum())
    future = int((df["review_date"] > EXTRACTION_DATE).sum())
    df = df[df["review_date"].notna() & (df["review_date"] <= EXTRACTION_DATE)]
    log.step("Parse 3 date formats, drop missing/future", b, len(df),
             f"{missing_d} missing, {future} after extraction date. "
             "Dropped: trend questions need a date")

    # 7. model year: numeric, plausible, not after review year + 1
    b = len(df)
    df["model_year"] = pd.to_numeric(df["model_year"], errors="coerce")
    bad = ~df["model_year"].between(2010, 2026) | (df["model_year"] > df["review_date"].dt.year + 1)
    n_bad = int(bad.sum())
    df.loc[bad, "model_year"] = pd.NA
    df["model_year"] = df["model_year"].astype("Int64")
    log.step("Validate model year", b, len(df),
             f"{n_bad} impossible values (2202, 1900, 0, blank) set to null, rows kept")

    # 8. text
    b = len(df)
    df["review_text"] = df["review_text"].map(clean_text)
    empty = df["review_text"].str.lower().isin(EMPTY_TEXT)
    n_empty = int(empty.sum())
    df = df[~empty]
    log.step("Clean text (HTML, entities, spaces), drop empty", b, len(df),
             f"{n_empty} empty or 'N/A' reviews dropped: nothing to analyse")

    # 9. near duplicates: same reviewer, same text, same date, different id
    b = len(df)
    df = df.drop_duplicates(subset=["reviewer", "review_text", "review_date"], keep="first")
    log.step("Drop near-duplicates (re-posts)", b, len(df), "same reviewer + text + date")

    # 10. derived columns
    df["verified_purchase"] = df["verified_purchase"].str.lower().eq("true")
    df["text_lower"] = df["review_text"].str.lower()
    df["review_year"] = df["review_date"].dt.year
    df["review_month"] = df["review_date"].dt.to_period("M").astype(str)
    df["rating_band"] = pd.cut(df["rating"], [0, 2, 3, 5], labels=["1-2 (negative)", "3 (neutral)", "4-5 (positive)"])
    df["sentiment_label"] = df["rating"].map(lambda r: "negative" if r <= 2 else "neutral" if r == 3 else "positive")
    df["word_count"] = df["review_text"].str.split().str.len()
    df["car_age_at_review"] = (df["review_year"] - df["model_year"]).astype("Int64")
    log.step("Add derived columns", len(df), len(df),
             "year, month, rating band, weak sentiment label, word count, car age")

    df = df.sort_values("review_date").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    write_log(log, n0, len(df))
    return df


def write_log(log: Log, n0: int, n1: int):
    lines = [
        "# Cleaning log",
        "",
        "_Auto-generated by `src/clean.py`. Do not edit by hand; re-run the pipeline._",
        "",
        f"**Rows in:** {n0:,} &nbsp; **Rows out:** {n1:,} &nbsp; "
        f"**Removed:** {n0 - n1:,} ({(n0 - n1) / n0:.1%})",
        "",
        "| # | Step | Rows before | Rows after | Change | Decision / note |",
        "|---|------|------------:|-----------:|-------:|-----------------|",
    ]
    for i, (name, b, a, note) in enumerate(log.rows, 1):
        lines.append(f"| {i} | {name} | {b:,} | {a:,} | {a - b:+,} | {note} |")
    lines += [
        "",
        "## Decisions that need a human to agree with them",
        "",
        "- **Dates in `DD/MM/YYYY`** are read day-first because the source system exports that way. "
        "With a new data source, check this before anything else: a wrong guess silently swaps months.",
        "- **Rows with a missing rating or date are dropped, not imputed.** Imputing the target variable "
        "would invent the very thing we are trying to measure.",
        "- **Impossible model years are nulled, not dropped.** The review is still valid for every question "
        "except Q5 (model-year comparison), which filters nulls out.",
        "- **Brand typos are fixed with fuzzy matching (cutoff 0.8)** against a fixed list of known brands, "
        "so a new brand would be dropped, not guessed. Check the 'unmappable' count on new data.",
        "- **The original text is kept** in `review_text` for display; `text_lower` is only used for tagging.",
    ]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines) + "\n")
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    pd.DataFrame(log.rows, columns=["step", "rows_before", "rows_after", "note"]).to_csv(
        out / "cleaning_steps.csv", index=False)


if __name__ == "__main__":
    main()
