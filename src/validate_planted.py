"""
Pipeline validation: did the analysis recover what was planted in the data?

This is the one script allowed to read data/synthetic_truth/. Every analysis
step before it ran blind. With a real dataset this step would be replaced by
hand-labelling ~200 reviews and comparing them the same way.

Output  docs/pipeline_validation.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
THEMES = ["service", "price", "maintenance", "reliability", "comfort", "mileage"]


def main():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv")
    truth = pd.read_csv(ROOT / "data" / "synthetic_truth" / "review_truth.csv")
    cfg = json.loads((ROOT / "data" / "synthetic_truth" / "generator_config.json").read_text())
    d = df.merge(truth, on="review_id", how="left")
    checks = []

    def check(signal, planted, found, ok):
        checks.append((signal, planted, found, "PASS" if ok else "MISS"))

    # P1 service is the most damaging theme; Norvik service worsening
    pr = pd.read_csv(OUT / "theme_priority.csv").set_index("theme")
    top = pr["impact_rank"].idxmin()
    check("P1a. Most damaging theme",
          f"service: largest rating penalty x frequency (planted effect {cfg['rating_effects']['service'][0]})",
          f"impact rank #1 = {top}; {pr.loc[top, 'stars_lost_per_100_reviews']} stars lost per 100 reviews",
          top == "service")
    q05 = pd.read_csv(OUT / "query_results" / "q05_theme_negativity_trend_yoy.csv")
    nv = d[d["brand"] == "Norvik"].groupby("review_year")["neg_service"].mean()
    check("P1b. Norvik service deteriorating",
          "negative-service probability rises every year 2020 -> 2025",
          f"share of Norvik reviews with a service complaint: {nv.iloc[0]:.0%} ({nv.index[0]}) -> "
          f"{nv.iloc[-1]:.0%} ({nv.index[-1]})", nv.iloc[-1] > 2 * nv.iloc[0])

    # P2 Velora Strato MY2022 defect
    q09 = pd.read_csv(OUT / "query_results" / "q09_worst_model_year_cohorts.csv")
    worst = q09.iloc[0]
    check("P2a. Defective cohort found by SQL",
          "Velora Strato MY2022 (and partly MY2023): transmission defect from Sep 2022",
          f"q09 worst cohort = {worst['brand']} {worst['model']} {worst['model_year']} "
          f"(avg {worst['avg_rating']}, {worst['pct_negative']}% negative)",
          (worst["brand"], worst["model"], int(worst["model_year"])) == ("Velora", "Strato", 2022))
    al = pd.read_csv(OUT / "alerts.csv")
    v = al[(al["brand"] == "Velora") & (al["metric"] == "reliability")]
    lt = pd.read_csv(OUT / "alert_lead_time.csv")
    others = len(lt) - len(v)
    check("P2b. Early-warning alert",
          "defect starts 2022-09 (2022Q3)",
          f"Velora reliability alert in {v['period'].min() if len(v) else 'none'}; 1-2 star share never "
          f"triggered an alert; {others} other alert(s) were false alarms",
          len(v) > 0 and v["period"].min() <= "2022Q4")

    # P3 price: most frequent complaint, smallest penalty
    check("P3. 'Most common' != 'most damaging'",
          f"price: most frequent complaint, smallest rating effect ({cfg['rating_effects']['price'][0]})",
          f"price naive rank #{pr.loc['price', 'naive_rank']}, impact rank #{pr.loc['price', 'impact_rank']} "
          f"({pr.loc['price', 'stars_lost_per_complaint']} stars per complaint)",
          pr.loc["price", "naive_rank"] == 1 and pr.loc["price", "impact_rank"] >= 4)

    # P4 newer model years more reliable
    q06 = pd.read_csv(OUT / "query_results" / "q06_model_year_quality.csv")
    old, new = q06.iloc[:3]["pct_reliability_complaints"].mean(), q06.iloc[-3:]["pct_reliability_complaints"].mean()
    check("P4. Newer model years more reliable",
          "negative-reliability probability falls 3 points per model year",
          f"reliability complaints: {old:.1f}% (3 oldest MYs) -> {new:.1f}% (3 newest)", new < old)

    # P5 small brand needs uncertainty
    br = pd.read_csv(OUT / "brand_ranking.csv").set_index("brand")
    b = br.loc["Brixton"]
    width = b["ci_high"] - b["ci_low"]
    med = (br["ci_high"] - br["ci_low"]).median()
    check("P5. Small-sample brand handled with uncertainty",
          "Brixton: ~1% of reviews, genuinely +0.5 stars",
          f"{int(b['reviews'])} reviews, CI {width / med:.1f}x wider than a typical brand; "
          f"shrunk {b['avg_rating']:.2f} -> {b['shrunk_mean']:.2f}, still #{int(b['fair_rank'])}",
          width > 2 * med and b["fair_rank"] == 1)

    # P6 Tamaru mileage
    tm = d.groupby("brand")["pos_mileage"].mean()
    check("P6. Tamaru praised for mileage",
          "Tamaru: mileage mentioned 50%, negative only 8%",
          f"positive mileage mentions: Tamaru {tm['Tamaru']:.0%} vs others avg "
          f"{tm.drop('Tamaru').mean():.0%}", tm.idxmax() == "Tamaru")

    # Extra: region
    q10 = pd.read_csv(OUT / "query_results" / "q10_service_negativity_by_region.csv")
    check("Extra. East region dealers",
          "East: +15 points negative-service probability",
          f"worst region = {q10.iloc[0]['dealer_region']} ({q10.iloc[0]['pct_negative']}% negative vs "
          f"{q10.iloc[1:]['pct_negative'].mean():.1f}% elsewhere)", q10.iloc[0]["dealer_region"] == "East")

    # Theme tagger quality vs truth
    tag_rows = []
    for t in THEMES:
        tr = d[f"true_{t}"].notna()
        pr_ = d[f"has_{t}"] == 1
        tp = (tr & pr_).sum()
        both = tr & pr_
        pol_ok = ((d.loc[both, f"true_{t}"] == "neg") == (d.loc[both, f"neg_{t}"] == 1)).mean()
        direct = d[f"direct_{t}"].astype(str) == "True"
        tag_rows.append({"theme": t, "precision": tp / pr_.sum(), "recall": tp / tr.sum(),
                         "recall_direct_phrasing": (tr & pr_ & direct).sum() / (tr & direct).sum(),
                         "recall_indirect_phrasing": (tr & pr_ & ~direct).sum() / max((tr & ~direct).sum(), 1),
                         "polarity_accuracy": pol_ok})
    tags = pd.DataFrame(tag_rows).round(3)
    tags.to_csv(OUT / "theme_tagger_validation.csv", index=False)

    # Sarcasm / label-noise share of model errors
    err = pd.read_csv(OUT / "error_cases.csv").merge(truth, on="review_id")
    test = d[d["in_test_set"] == 1]
    sarc_rate_err = err["sarcastic"].mean()
    noise_rate_err = err["label_noise"].mean()
    sarc = d[d["sarcastic"] == True]  # noqa: E712
    test_ids = set(test["review_id"])
    err_ids = set(err["review_id"])
    sarc_test = sarc[sarc["review_id"].isin(test_ids)]
    sarc_test_acc = 1 - sarc_test["review_id"].isin(err_ids).mean() if len(sarc_test) else float("nan")

    passed = sum(c[3] == "PASS" for c in checks)
    md = ["# Pipeline validation against planted signals", "",
          "_Auto-generated by `src/validate_planted.py`, the only script that reads "
          "`data/synthetic_truth/`. All analysis ran blind to these answers._", "",
          f"**{passed} / {len(checks)} planted signals recovered.**", "",
          "| Signal | What was planted | What the pipeline found | Result |",
          "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | **{r}** |" for a, b, c, r in checks]
    md += ["", "## Theme tagger vs. ground truth", "",
           "Indirect phrasing (\"it spends more time at the workshop than in my driveway\") was "
           "planted on purpose. It is the main reason recall is below precision.", "",
           tags.to_markdown(index=False), "",
           "## Where the sentiment model's errors come from", "",
           f"- Test-set errors: {len(err)} of {len(test)} reviews.",
           f"- Planted rating 'misclicks' (rating contradicts the text): "
           f"{noise_rate_err:.0%} of errors vs {test['review_id'].isin(truth.loc[truth.label_noise, 'review_id']).mean():.0%} of all test reviews.",
           f"- Planted sarcasm: {sarc_rate_err:.0%} of errors vs "
           f"{test['review_id'].isin(truth.loc[truth.sarcastic, 'review_id']).mean():.0%} of all test reviews.",
           "- Misclicks are heavily over-represented among errors: a large part of the 'error' "
           "is in the weak labels, not the model.", "",
           "## Sarcasm: an honest caveat", "",
           f"- VADER scores **{(sarc['vader_compound'] >= 0.4).mean():.0%}** of the {len(sarc)} sarcastic "
           "reviews as positive. A lexicon sees 'fantastic' and 'love' and cannot see irony.",
           f"- TF-IDF + logistic regression classifies **{sarc_test_acc:.0%}** of sarcastic test reviews "
           "correctly. **Do not quote this as a sarcasm result.** The generator reuses six sarcastic "
           "sentences, so the model memorised them. Real sarcasm is not templated; expect this to "
           "fall sharply on real data.", "",
           "## What this proves, and what it does not", "",
           "- It proves the **method** finds the kinds of problems it claims to find, at roughly the "
           "strength they were planted.",
           "- It does **not** prove anything about a real car market. The data is synthetic.",
           "- With real data, replace this file with a hand-labelled sample of ~200 reviews and "
           "report the same precision / recall table."]
    (ROOT / "docs" / "pipeline_validation.md").write_text("\n".join(md) + "\n")
    for c in checks:
        print(f"{c[3]:<5} {c[0]}: {c[2]}")
    print(tags.to_string(index=False))
    print(f"errors: {len(err)}; misclick share {noise_rate_err:.0%}; sarcasm share {sarc_rate_err:.0%}")


if __name__ == "__main__":
    main()
