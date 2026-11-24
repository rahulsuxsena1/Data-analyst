"""
Charts for the README and insights report.  Output: images/*.png

Style rules: one accent colour carries the story, everything else is grey;
direct labels instead of legends where possible; light, recessive axes.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
IMG = ROOT / "images"

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#9a9993", "#e5e4df"
BLUE, ORANGE, RED, GREY = "#2a78d6", "#eb6834", "#e34948", "#c9c8c2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.family": "DejaVu Sans",
})


def save(fig, name):
    IMG.mkdir(exist_ok=True)
    fig.savefig(IMG / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"images/{name}")


def footnote(fig, text="Synthetic data. Illustrates the method, not a real market."):
    fig.text(0.01, -0.02, text, fontsize=8, color=MUTED, ha="left")


def chart_priority():
    p = pd.read_csv(OUT / "theme_priority.csv").sort_values("stars_lost_per_100_reviews")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    colors = [ORANGE if t == "price" else BLUE if t in ("service", "reliability") else GREY for t in p["theme"]]
    for ax, col, title, fmt in [
        (axes[0], "pct_reviews_complaining", "How OFTEN it is complained about\n% of reviews (naive priority)", "{:.1f}%"),
        (axes[1], "stars_lost_per_100_reviews", "How much it COSTS the rating\nstars lost per 100 reviews (impact)", "{:.1f}"),
    ]:
        ax.barh(p["theme"], p[col], color=colors, height=0.6)
        ax.set_title(title, fontsize=10.5)
        ax.grid(axis="y", visible=False)
        for y, v in enumerate(p[col]):
            ax.text(v + p[col].max() * 0.02, y, fmt.format(v), va="center", fontsize=9, color=INK2)
        ax.set_xlim(0, p[col].max() * 1.18)
    fig.suptitle("Price is the most common complaint, but service and reliability cost the most",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", y=1.04)
    footnote(fig)
    save(fig, "01_priority_naive_vs_impact.png")


def chart_early_warning():
    c = pd.read_csv(OUT / "control_chart_data.csv")
    v = c[(c["brand"] == "Velora") & (c["period"] >= "2021Q1")]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for ax, metric, title, color in [
        (axes[0], "reliability", "Velora: share of reviews complaining about reliability", BLUE),
        (axes[1], "low_rating", "Velora: share of 1-2 star reviews (what a ratings dashboard watches)", GREY),
    ]:
        m = v[v["metric"] == metric].reset_index(drop=True)
        x = np.arange(len(m))
        ax.plot(x, m["rate"] * 100, color=color if metric == "reliability" else INK2, lw=2, marker="o", ms=4)
        tested = m["tested"]
        ax.plot(x[tested], m.loc[tested, "upper_limit"] * 100, color=MUTED, lw=1.2, ls="--")
        ax.text(x[tested][-1] + 0.2, m.loc[tested, "upper_limit"].iloc[-1] * 100, "alert limit",
                color=MUTED, fontsize=8, va="center")
        for i in np.where(m["alert"])[0]:
            ax.scatter(x[i], m.loc[i, "rate"] * 100, s=110, color=RED, zorder=5, edgecolor=SURFACE, lw=2)
            ax.annotate(f"ALERT {m.loc[i, 'period']}\n{m.loc[i, 'rate']:.0%} vs {m.loc[i, 'baseline']:.0%} baseline",
                        (x[i], m.loc[i, "rate"] * 100), xytext=(12, 4), textcoords="offset points",
                        fontsize=9, color=RED, fontweight="bold")
        ax.set_title(title, fontsize=10.5)
        ax.set_ylabel("% of reviews")
        ax.set_xticks(x, m["period"], rotation=45, fontsize=8)
    axes[1].text(0.99, 0.92, "no alert: the defect is diluted in the overall rating",
                 transform=axes[1].transAxes, ha="right", fontsize=9, color=INK2)
    i22 = list(v[v["metric"] == "reliability"]["period"]).index("2022Q3")
    for ax in axes:
        ax.axvline(i22, color=GRID, lw=6, zorder=0)
    axes[0].text(i22, axes[0].get_ylim()[1] * 0.95, " defect begins", fontsize=8, color=MUTED)
    fig.suptitle("Early warning: theme-level monitoring caught a defect that star ratings never flagged",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    footnote(fig)
    save(fig, "02_early_warning_velora.png")


def chart_brands():
    b = pd.read_csv(OUT / "brand_ranking.csv").sort_values("shrunk_mean")
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(len(b))
    ax.hlines(y, b["ci_low"], b["ci_high"], color=GREY, lw=3)
    ax.scatter(b["avg_rating"], y, color=INK2, s=30, zorder=3, label="raw average")
    ax.scatter(b["shrunk_mean"], y, color=BLUE, s=60, zorder=4, marker="D", label="adjusted for sample size")
    for yi, (_, r) in zip(y, b.iterrows()):
        ax.text(r["ci_high"] + 0.02, yi, f"n={int(r['reviews']):,}", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(y, b["brand"])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("average rating (bar = 95% confidence interval)")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.set_title("Brand ranking with uncertainty: Brixton's lead is real, but its range is 3.6x wider")
    footnote(fig)
    save(fig, "03_brand_ranking_ci.png")


def chart_norvik():
    df = pd.read_csv(ROOT / "data" / "clean" / "reviews_scored.csv")
    df["grp"] = np.where(df["brand"] == "Norvik", "Norvik", "All other brands")
    t = df.groupby(["review_year", "grp"])["neg_service"].mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(t.index, t["All other brands"], color=GREY, lw=2, marker="o", ms=4)
    ax.plot(t.index, t["Norvik"], color=BLUE, lw=2.5, marker="o", ms=5)
    ax.text(t.index[-1] + 0.1, t["Norvik"].iloc[-1], f"Norvik {t['Norvik'].iloc[-1]:.0f}%", color=BLUE,
            va="center", fontweight="bold")
    ax.text(t.index[-1] + 0.1, t["All other brands"].iloc[-1], f"Others {t['All other brands'].iloc[-1]:.0f}%",
            color=INK2, va="center")
    ax.set_xlim(t.index[0] - 0.2, t.index[-1] + 0.9)
    ax.set_ylabel("% of reviews with a service complaint")
    ax.set_title("Norvik's service problem has more than doubled since 2020")
    footnote(fig)
    save(fig, "04_norvik_service_trend.png")


def chart_cohorts():
    q = pd.read_csv(OUT / "query_results" / "q09_worst_model_year_cohorts.csv").sort_values("pct_negative")
    lab = q["brand"] + " " + q["model"] + " MY" + q["model_year"].astype(str)
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [BLUE if b == "Velora" and m == "Strato" else GREY for b, m in zip(q["brand"], q["model"])]
    ax.barh(lab, q["pct_negative"], color=colors, height=0.6)
    for y, v in enumerate(q["pct_negative"]):
        ax.text(v + 0.5, y, f"{v:.0f}%", va="center", fontsize=8.5, color=INK2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% of reviews rated 1-2 stars (cohorts with 40+ reviews)")
    ax.set_title("Worst model-year cohorts: two Velora Strato years stand out")
    footnote(fig)
    save(fig, "05_worst_cohorts.png")


def chart_confusion():
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    m = pd.read_csv(OUT / "model_metrics.csv").set_index("model")
    for ax, f, name in [(axes[0], "confusion_matrix_vader.csv", "VADER"),
                        (axes[1], "confusion_matrix_logreg.csv", "TF-IDF + LogReg")]:
        cm = pd.read_csv(OUT / f, index_col=0)
        norm = cm.div(cm.sum(axis=1), axis=0)
        ax.imshow(norm, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#f1f6fd", "#184f95"]),
                  vmin=0, vmax=1)
        labels = ["negative", "neutral", "positive"]
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{norm.iloc[i, j]:.0%}\n({cm.iloc[i, j]})", ha="center", va="center",
                        fontsize=8.5, color=SURFACE if norm.iloc[i, j] > 0.65 else INK)
        ax.set_xticks(range(3), labels)
        ax.set_yticks(range(3), labels)
        ax.set_xlabel("predicted")
        ax.set_ylabel("rating-based label")
        ax.grid(False)
        ax.set_title(f"{name}: accuracy {m.loc[name, 'accuracy']:.0%}, macro-F1 {m.loc[name, 'macro_f1']:.2f}",
                     fontsize=10)
    fig.suptitle("Sentiment models vs. weak (rating-based) labels, held-out 20% test set",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    footnote(fig)
    save(fig, "06_confusion_matrices.png")


def main():
    chart_priority()
    chart_early_warning()
    chart_brands()
    chart_norvik()
    chart_cohorts()
    chart_confusion()


if __name__ == "__main__":
    main()
