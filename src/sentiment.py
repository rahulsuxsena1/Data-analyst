"""
Stage 4: review-level sentiment models, evaluated against WEAK labels.

Weak labels: rating 1-2 = negative, 3 = neutral, 4-5 = positive.
They are "weak" because a star rating is the customer's overall verdict, not a
careful reading of the text. Some 5-star reviews contain complaints, and some
people misclick. So these scores measure agreement with ratings, not truth.

Models
  0. majority class            the number any model must beat
  1. VADER (rule-based)        no training, fully explainable
  2. TF-IDF + logistic reg.    trained on 80%, tested on the held-out 20%

Output  outputs/model_metrics.csv, outputs/error_cases.csv,
        data/clean/reviews_scored.csv (adds predicted sentiment for the dashboard)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
LABELS = ["negative", "neutral", "positive"]


def vader_label(c: float, lo: float = -0.05, hi: float = 0.5) -> str:
    # 'hi' is higher than VADER's usual 0.05 because most reviews contain
    # some politeness ("good", "happy"); tuned on the TRAIN split only.
    return "negative" if c <= lo else "positive" if c >= hi else "neutral"


def main():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_tagged.csv")
    y = df["sentiment_label"]
    train_idx, test_idx = train_test_split(df.index, test_size=0.2, stratify=y, random_state=7)
    tr, te = df.loc[train_idx], df.loc[test_idx]

    # tune VADER's positive threshold on train only (no peeking at test)
    best_hi = max(np.arange(0.05, 0.9, 0.05),
                  key=lambda h: f1_score(tr["sentiment_label"],
                                         tr["vader_compound"].map(lambda c: vader_label(c, hi=h)),
                                         average="macro"))

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    Xtr = vec.fit_transform(tr["review_text"])
    Xte = vec.transform(te["review_text"])
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0)
    clf.fit(Xtr, tr["sentiment_label"])

    preds = {
        "Majority class": pd.Series("positive", index=te.index),
        "VADER": te["vader_compound"].map(lambda c: vader_label(c, hi=best_hi)),
        "TF-IDF + LogReg": pd.Series(clf.predict(Xte), index=te.index),
    }
    rows = []
    for name, p in preds.items():
        rep = classification_report(te["sentiment_label"], p, labels=LABELS, output_dict=True, zero_division=0)
        rows.append({"model": name,
                     "accuracy": accuracy_score(te["sentiment_label"], p),
                     "macro_f1": f1_score(te["sentiment_label"], p, average="macro"),
                     **{f"{l}_precision": rep[l]["precision"] for l in LABELS},
                     **{f"{l}_recall": rep[l]["recall"] for l in LABELS}})
    metrics = pd.DataFrame(rows).round(3)
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    metrics.to_csv(out / "model_metrics.csv", index=False)
    print(f"VADER positive threshold tuned on train: {best_hi:.2f}")
    print(metrics[["model", "accuracy", "macro_f1"]].to_string(index=False))

    cm = confusion_matrix(te["sentiment_label"], preds["TF-IDF + LogReg"], labels=LABELS)
    pd.DataFrame(cm, index=[f"true_{l}" for l in LABELS], columns=[f"pred_{l}" for l in LABELS]) \
        .to_csv(out / "confusion_matrix_logreg.csv")
    cmv = confusion_matrix(te["sentiment_label"], preds["VADER"], labels=LABELS)
    pd.DataFrame(cmv, index=[f"true_{l}" for l in LABELS], columns=[f"pred_{l}" for l in LABELS]) \
        .to_csv(out / "confusion_matrix_vader.csv")

    # most informative words: what the model actually learned
    names = np.array(vec.get_feature_names_out())
    coefs = pd.DataFrame(clf.coef_.T, index=names, columns=clf.classes_)
    top = {c: coefs[c].sort_values(ascending=False).head(12).index.tolist() for c in clf.classes_}
    pd.DataFrame(top).to_csv(out / "top_words_logreg.csv", index=False)

    # error cases: confident mistakes are the interesting ones
    proba = clf.predict_proba(Xte)
    te = te.assign(pred=preds["TF-IDF + LogReg"], pred_vader=preds["VADER"],
                   confidence=proba.max(axis=1))
    errors = te[te["pred"] != te["sentiment_label"]].sort_values("confidence", ascending=False)
    errors[["review_id", "brand", "model", "rating", "sentiment_label", "pred", "pred_vader",
            "confidence", "vader_compound", "mixed_flag", "text_rating_conflict", "review_text"]] \
        .to_csv(out / "error_cases.csv", index=False)

    # score every review for the dashboard (model refit on all data)
    clf_all = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0)
    X_all = vec.fit_transform(df["review_text"])
    clf_all.fit(X_all, y)
    df["predicted_sentiment"] = clf_all.predict(X_all)
    df["in_test_set"] = df.index.isin(test_idx).astype(int)
    df.to_csv(ROOT / "data" / "clean" / "reviews_scored.csv", index=False)


if __name__ == "__main__":
    main()
