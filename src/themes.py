"""
Stage 5a: theme tagging + theme-level ("aspect") sentiment.

Method (kept deliberately explainable):
  1. split each review into sentences
  2. tag a sentence with a theme if it contains one of the theme's keywords
  3. score that sentence with VADER (+ a small car-domain lexicon) to get the
     sentiment of THAT theme in THAT review

Why sentence-level? "Comfortable seats but the dealer was rude" is one review
with two opposite opinions. Whole-review sentiment would blur them together.

Output  data/clean/review_themes.csv   one row per (review, theme)
        data/clean/reviews_tagged.csv  reviews + has_<theme>, neg_<theme>, flags
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "reviews_clean.csv"

THEME_KEYWORDS: dict[str, list[str]] = {
    "service": ["service", "dealer", "dealership", "staff", "advisor", "customer support",
                "appointment", "salesperson", "after-sales", "warranty claim"],
    "price": ["price", "priced", "pricey", "expensive", "overpriced", "cost", "value for money",
              "affordable", "deal", "financing", "quote"],
    "maintenance": ["maintenance", "oil change", "oil changes", "spare parts", "repair bill",
                    "brake pads", "upkeep", "running costs"],
    "reliability": ["reliable", "reliability", "broke down", "breakdown", "engine", "transmission",
                    "check engine", "recall", "stalls", "defect", "in the shop", "never let me down"],
    "comfort": ["comfort", "comfortable", "seats", "ride", "cabin", "road noise", "legroom",
                "interior", "suspension"],
    "mileage": ["mileage", "mpg", "fuel economy", "fuel efficiency", "fuel", "fill up"],
}
THEMES = list(THEME_KEYWORDS)

# Words VADER does not know but car owners use to complain or praise.
DOMAIN_LEXICON = {
    "expensive": -1.5, "overpriced": -2.2, "pricey": -1.2, "slipping": -1.8, "stalls": -1.8,
    "stall": -1.5, "broke": -1.8, "defect": -2.0, "recall": -1.2, "rude": -2.2, "clueless": -1.8,
    "upsell": -1.4, "harsh": -1.6, "noise": -1.0, "towed": -1.8, "nightmare": -2.5,
    "disappointing": -2.0, "costly": -1.5, "chase": -1.0, "joke": -1.2, "bulletproof": 2.0,
    "affordable": 1.8, "inexpensive": 1.5, "cheap": 1.0, "quiet": 1.2, "smooth": 1.5,
    "outstanding": 2.5, "reliable": 2.0, "denied": -1.5, "lost": -1.2, "waiting": -0.8,
    "nowhere": -1.0, "hurts": -1.8,
}

_PATTERNS = {t: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b")
             for t, kws in THEME_KEYWORDS.items()}
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def make_analyzer(domain: bool = True) -> SentimentIntensityAnalyzer:
    sia = SentimentIntensityAnalyzer()
    if domain:
        sia.lexicon.update(DOMAIN_LEXICON)
    return sia


def tag_sentence(sentence: str) -> list[str]:
    s = sentence.lower()
    return [t for t, pat in _PATTERNS.items() if pat.search(s)]


def polarity(compound: float) -> str:
    return "negative" if compound <= -0.05 else "positive" if compound >= 0.05 else "neutral"


def tag_reviews(df: pd.DataFrame, sia: SentimentIntensityAnalyzer | None = None) -> pd.DataFrame:
    """Return one row per (review_id, theme) with the theme's sentence-level sentiment."""
    sia = sia or make_analyzer()
    out = []
    for rid, text in zip(df["review_id"], df["review_text"]):
        found: dict[str, list[float]] = {}
        for sent in _SENT_SPLIT.split(text):
            themes = tag_sentence(sent)
            if themes:
                c = sia.polarity_scores(sent)["compound"]
                for t in themes:
                    found.setdefault(t, []).append(c)
        for t, scores in found.items():
            c = sum(scores) / len(scores)
            out.append((rid, t, round(c, 4), polarity(c)))
    return pd.DataFrame(out, columns=["review_id", "theme", "theme_sentiment", "theme_polarity"])


def main():
    df = pd.read_csv(CLEAN)
    sia = make_analyzer()
    rt = tag_reviews(df, sia)
    rt.to_csv(ROOT / "data" / "clean" / "review_themes.csv", index=False)

    wide_has = pd.crosstab(rt["review_id"], rt["theme"]).clip(upper=1)
    wide_neg = pd.crosstab(rt["review_id"], rt["theme"],
                           values=(rt["theme_polarity"] == "negative").astype(int), aggfunc="max")
    wide_pos = pd.crosstab(rt["review_id"], rt["theme"],
                           values=(rt["theme_polarity"] == "positive").astype(int), aggfunc="max")
    for t in THEMES:
        df[f"has_{t}"] = df["review_id"].map(wide_has.get(t, pd.Series(dtype=int))).fillna(0).astype(int)
        df[f"neg_{t}"] = df["review_id"].map(wide_neg.get(t, pd.Series(dtype=float))).fillna(0).astype(int)
        df[f"pos_{t}"] = df["review_id"].map(wide_pos.get(t, pd.Series(dtype=float))).fillna(0).astype(int)
    df["n_themes"] = df[[f"has_{t}" for t in THEMES]].sum(axis=1)

    # whole-review VADER score, used for flags and as baseline model 1
    df["vader_compound"] = [sia.polarity_scores(t)["compound"] for t in df["review_text"]]
    any_neg = df[[f"neg_{t}" for t in THEMES]].sum(axis=1) > 0
    any_pos = df[[f"pos_{t}" for t in THEMES]].sum(axis=1) > 0
    df["mixed_flag"] = (any_neg & any_pos).astype(int)
    # text reads clearly positive but the customer gave 1-2 stars: sarcasm or misclick
    df["text_rating_conflict"] = ((df["vader_compound"] >= 0.5) & (df["rating"] <= 2)).astype(int)
    df.to_csv(ROOT / "data" / "clean" / "reviews_tagged.csv", index=False)

    cov = (df["n_themes"] > 0).mean()
    print(f"theme rows: {len(rt):,}; reviews with >=1 theme: {cov:.1%}; "
          f"mixed: {df['mixed_flag'].mean():.1%}; text/rating conflict: {df['text_rating_conflict'].sum()}")
    print(rt.groupby("theme")["theme_polarity"].value_counts(normalize=True).unstack().round(2))


if __name__ == "__main__":
    main()
