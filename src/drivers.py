"""
Stage 7a: key-driver analysis, fair brand ranking and what-if scenarios.

1. Key drivers (OLS regression)
   rating ~ negative mention of each theme + positive mention of each theme + brand
   The coefficient on neg_<theme> = average stars lost when a review complains
   about that theme, holding the other themes and the brand constant.
   This fixes a weakness of the simple "with vs without" gap (SQL q04): reviews
   that complain about service often complain about reliability too, so the
   raw gaps double-count.

2. Impact-weighted priority
   stars lost per 100 reviews = 100 x (share of reviews with that complaint) x |coefficient|
   It answers: "how much higher would the average rating be if this complaint vanished?"

3. Fair brand ranking (empirical-Bayes shrinkage)
   A brand with 98 reviews and a 4.15 average is not proven better than one with
   2,000 reviews and 3.9. Shrinkage pulls small samples toward the overall mean
   in proportion to how little data they have.

4. What-if scenarios with explicit assumptions (no invented revenue).

Output  outputs/driver_coefficients.csv, outputs/theme_priority.csv,
        outputs/brand_ranking.csv, outputs/scenarios.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
THEMES = ["service", "price", "maintenance", "reliability", "comfort", "mileage"]


def ols(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Ordinary least squares with classic standard errors (numpy only, so every step is visible)."""
    Xm = np.column_stack([np.ones(len(X)), X.to_numpy(float)])
    beta, *_ = np.linalg.lstsq(Xm, y.to_numpy(float), rcond=None)
    resid = y.to_numpy(float) - Xm @ beta
    dof = len(y) - Xm.shape[1]
    sigma2 = resid @ resid / dof
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(Xm.T @ Xm)))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) ** 2).sum()
    res = pd.DataFrame({"term": ["intercept", *X.columns], "coef": beta, "se": se})
    res["ci_low"], res["ci_high"] = res["coef"] - 1.96 * res["se"], res["coef"] + 1.96 * res["se"]
    res.attrs["r2"] = r2
    return res


def key_drivers(df: pd.DataFrame) -> pd.DataFrame:
    X = df[[f"neg_{t}" for t in THEMES] + [f"pos_{t}" for t in THEMES]].copy()
    brands = pd.get_dummies(df["brand"], prefix="brand", drop_first=True, dtype=int)
    res = ols(pd.concat([X, brands], axis=1), df["rating"])
    print(f"key-driver regression R^2 = {res.attrs['r2']:.3f}")
    return res


def theme_priority(df: pd.DataFrame, coefs: pd.DataFrame) -> pd.DataFrame:
    c = coefs.set_index("term")
    rows = []
    for t in THEMES:
        share = df[f"neg_{t}"].mean()
        coef = c.loc[f"neg_{t}", "coef"]
        rows.append({
            "theme": t,
            "pct_reviews_complaining": round(100 * share, 1),
            "stars_lost_per_complaint": round(coef, 2),
            "ci_low": round(c.loc[f"neg_{t}", "ci_low"], 2),
            "ci_high": round(c.loc[f"neg_{t}", "ci_high"], 2),
            "volume_x_negativity_score": round(100 * share, 2),          # the naive score
            "stars_lost_per_100_reviews": round(100 * share * -coef, 1),  # impact-weighted
        })
    p = pd.DataFrame(rows)
    p["naive_rank"] = p["volume_x_negativity_score"].rank(ascending=False).astype(int)
    p["impact_rank"] = p["stars_lost_per_100_reviews"].rank(ascending=False).astype(int)
    return p.sort_values("impact_rank")


def brand_ranking(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("brand")["rating"].agg(["count", "mean", "var"])
    grand = df["rating"].mean()
    within = df["rating"].var()                     # noise in a single rating
    between = max(g["mean"].var() - (within / g["count"]).mean(), 1e-6)  # real brand spread
    k = within / between                            # "prior strength" in reviews
    g["shrunk_mean"] = (g["count"] * g["mean"] + k * grand) / (g["count"] + k)
    g["ci_low"] = g["mean"] - 1.96 * np.sqrt(g["var"] / g["count"])
    g["ci_high"] = g["mean"] + 1.96 * np.sqrt(g["var"] / g["count"])
    g["raw_rank"] = g["mean"].rank(ascending=False).astype(int)
    g["fair_rank"] = g["shrunk_mean"].rank(ascending=False).astype(int)
    g.attrs["k"] = k
    print(f"shrinkage prior strength k = {k:.0f} reviews")
    return g.rename(columns={"count": "reviews", "mean": "avg_rating"}).round(3) \
        .sort_values("fair_rank").reset_index()


def scenarios(df: pd.DataFrame, coefs: pd.DataFrame) -> pd.DataFrame:
    """What happens to the average rating if a share of complaints is fixed?
    Assumption: each fixed complaint gains the regression coefficient, nothing else changes."""
    c = coefs.set_index("term")["coef"]
    base = df["rating"].mean()
    rows = []
    specs = [
        ("Cut negative service reviews by 10%", "all", "service", 0.10),
        ("Cut negative service reviews by 25%", "all", "service", 0.25),
        ("Cut negative reliability reviews by 10%", "all", "reliability", 0.10),
        ("Cut negative price reviews by 10%", "all", "price", 0.10),
        ("Norvik: halve negative service reviews", "Norvik", "service", 0.50),
        ("Velora Strato MY2022-23: fix the transmission issue (-70% reliability complaints)",
         "velora_strato", "reliability", 0.70),
    ]
    for name, scope, theme, cut in specs:
        if scope == "all":
            sub = df
        elif scope == "velora_strato":
            sub = df[(df["brand"] == "Velora") & (df["model"] == "Strato") & df["model_year"].isin([2022, 2023])]
        else:
            sub = df[df["brand"] == scope]
        n_fixed = sub[f"neg_{theme}"].sum() * cut
        gain_scope = n_fixed * -c[f"neg_{theme}"] / len(sub)
        gain_total = n_fixed * -c[f"neg_{theme}"] / len(df)
        rows.append({"scenario": name, "scope_reviews": len(sub),
                     "complaints_removed": int(round(n_fixed)),
                     "scope_avg_before": round(sub["rating"].mean(), 3),
                     "scope_avg_after": round(sub["rating"].mean() + gain_scope, 3),
                     "portfolio_avg_change": round(gain_total, 3),
                     "assumption": f"each removed complaint adds {-c[f'neg_{theme}']:.2f} stars (regression coefficient)"})
    out = pd.DataFrame(rows)
    out.attrs["base"] = base
    return out


def main():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv")
    coefs = key_drivers(df)
    coefs.round(4).to_csv(OUT / "driver_coefficients.csv", index=False)
    pr = theme_priority(df, coefs)
    pr.to_csv(OUT / "theme_priority.csv", index=False)
    print(pr[["theme", "pct_reviews_complaining", "stars_lost_per_complaint",
              "stars_lost_per_100_reviews", "naive_rank", "impact_rank"]].to_string(index=False))
    br = brand_ranking(df)
    br.to_csv(OUT / "brand_ranking.csv", index=False)
    print(br[["brand", "reviews", "avg_rating", "shrunk_mean", "raw_rank", "fair_rank"]].to_string(index=False))
    trend = df.assign(group=np.where(df["brand"] == "Norvik", "Norvik", "All other brands")) \
        .groupby(["review_year", "group"])["neg_service"].mean().unstack().round(4)
    trend.reset_index().to_csv(OUT / "service_trend_norvik.csv", index=False)
    sc = scenarios(df, coefs)
    sc.to_csv(OUT / "scenarios.csv", index=False)
    print(sc[["scenario", "complaints_removed", "scope_avg_before", "scope_avg_after", "portfolio_avg_change"]].to_string(index=False))


if __name__ == "__main__":
    main()
