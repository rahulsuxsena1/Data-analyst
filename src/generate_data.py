"""
Stage 1 (Route B): generate a SYNTHETIC automotive review dataset.

Everything produced here is fictional: brands, models, reviewers and reviews.
The data is deliberately messy (duplicates, typos, mixed date formats, invalid
ratings, HTML junk) so the cleaning stage has real work to do.

It also plants known business problems ("planted signals"). The ground truth
is written to data/synthetic_truth/ and is NEVER read by the analysis code.
Only src/validate_planted.py reads it, to check whether the pipeline recovers
what was planted. With real data this folder simply would not exist.

Outputs
    data/raw/reviews.csv                      messy raw export
    data/synthetic_truth/review_truth.csv     true themes / polarity / sarcasm per review
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_REVIEWS = 12_000
START, END = date(2020, 1, 1), date(2025, 12, 31)

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "reviews.csv"
TRUTH_DIR = ROOT / "data" / "synthetic_truth"

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------
# Fictional market
# --------------------------------------------------------------------------
BRANDS = {
    #  brand      share  rating effect  models
    "Aurex":   (0.18,  0.10, ["Sprint", "Atlas", "Nova"]),
    "Kestrel": (0.17,  0.00, ["K3", "K5", "Ridge"]),
    "Solano":  (0.15,  0.05, ["Breeze", "Mesa", "Vista"]),
    "Tamaru":  (0.14,  0.15, ["Kai", "Hoshi"]),
    "Norvik":  (0.13,  0.00, ["Fjord", "Tundra"]),
    "Velora":  (0.12, -0.10, ["Strato", "Lumen"]),
    "Zephyr":  (0.10, -0.05, ["Gale", "Drift"]),
    "Brixton": (0.01,  0.50, ["Regent"]),          # tiny sample, high mean (P5)
}
REGIONS = ["North", "South", "East", "West", "Central"]
THEMES = ["service", "price", "maintenance", "reliability", "comfort", "mileage"]

# base probability that a review mentions a theme, and that a mention is negative
MENTION = {"service": .30, "price": .36, "maintenance": .22,
           "reliability": .28, "comfort": .30, "mileage": .25}
NEGATIVE = {"service": .38, "price": .66, "maintenance": .55,
            "reliability": .35, "comfort": .25, "mileage": .30}
# effect of a mention on the latent rating: (if negative, if positive)
EFFECT = {"service": (-1.45, .40), "price": (-.30, .15), "maintenance": (-.80, .20),
          "reliability": (-1.60, .35), "comfort": (-.50, .25), "mileage": (-.50, .30)}

# --------------------------------------------------------------------------
# Sentence pools. "direct" phrases use vocabulary a keyword tagger can catch;
# "indirect" ones describe the same issue without the obvious keywords, so the
# tagger's recall can be measured honestly.
# --------------------------------------------------------------------------
P = {
    ("service", "neg", "direct"): [
        "The dealer staff were rude and kept me waiting for {h} hours.",
        "Service at the dealership was a nightmare, nobody returned my calls.",
        "Booked a service appointment and they still lost my paperwork.",
        "The service advisor tried to upsell me on things I did not need.",
        "Customer support took {w} weeks to answer a simple warranty claim.",
        "Dealership staff seemed clueless about their own cars.",
        "The salesperson promised things the dealer later denied.",
        "Terrible after-sales service, I had to chase them every single time.",
    ],
    ("service", "neg", "indirect"): [
        "Nobody at the place I bought it from ever calls back.",
        "I was treated like an inconvenience the moment I signed the papers.",
        "Spent an entire Saturday waiting for someone to look at my car.",
    ],
    ("service", "pos", "direct"): [
        "The dealer staff were friendly and explained everything clearly.",
        "Service appointments are quick and the advisor keeps me updated.",
        "Great experience at the dealership, no pressure at all.",
        "Customer support sorted out my warranty claim within a day.",
    ],
    ("service", "pos", "indirect"): [
        "The team that looks after my car treats me like family.",
    ],
    ("price", "neg", "direct"): [
        "Way too expensive for what you get.",
        "The final price was ${amt} higher than the quote.",
        "Overpriced compared to rivals in the same class.",
        "Honestly not good value for money at this price point.",
        "Financing and insurance cost far more than I expected.",
        "Pricey for a car with such basic features.",
    ],
    ("price", "neg", "indirect"): [
        "Felt like I was paying luxury rates for an economy car.",
        "My wallet is still recovering from the purchase.",
    ],
    ("price", "pos", "direct"): [
        "Priced fairly for the features you get.",
        "Great value for money.",
        "Affordable and very well equipped.",
        "Got a good deal on it.",
    ],
    ("price", "pos", "indirect"): [
        "Lots of car for the outlay.",
    ],
    ("maintenance", "neg", "direct"): [
        "Maintenance costs are much higher than my last car.",
        "Every oil change seems to come with a surprise add-on.",
        "Spare parts take weeks to arrive and are very costly.",
        "Brake pads needed replacing at only {k}k miles.",
        "The repair bill after the warranty ended was painful.",
        "Scheduled maintenance is a lot more expensive than advertised.",
    ],
    ("maintenance", "neg", "indirect"): [
        "Every trip to the workshop ends with a four-figure invoice.",
        "Keeping it on the road is draining my savings.",
    ],
    ("maintenance", "pos", "direct"): [
        "Maintenance is cheap and simple.",
        "Routine oil changes are inexpensive.",
        "Spare parts are easy to find and reasonably priced.",
    ],
    ("maintenance", "pos", "indirect"): [
        "Running costs at the workshop have been minimal.",
    ],
    ("reliability", "neg", "direct"): [
        "The transmission started slipping at {k}k miles.",
        "Check engine light came on three times in the first year.",
        "It broke down on the highway with my kids in the car.",
        "Not reliable at all, it has been in the shop four times.",
        "The engine stalls at traffic lights randomly.",
        "Got a recall notice for a defect they still have not fixed.",
    ],
    ("reliability", "neg", "indirect"): [
        "It spends more time at the workshop than in my driveway.",
        "Towed twice in six months.",
        "I never know if it will start in the morning.",
    ],
    ("reliability", "pos", "direct"): [
        "Super reliable, not a single issue in {y} years.",
        "The engine is bulletproof.",
        "Very reliable car, never let me down.",
    ],
    ("reliability", "pos", "indirect"): [
        "Starts every morning without fail, even in winter.",
    ],
    ("comfort", "neg", "direct"): [
        "The seats are hard and my back hurts on long drives.",
        "Too much road noise in the cabin.",
        "The ride is harsh over bumps.",
        "Legroom in the back is a joke.",
    ],
    ("comfort", "neg", "indirect"): [
        "Long trips leave me stiff and tired.",
    ],
    ("comfort", "pos", "direct"): [
        "Very comfortable seats, great for road trips.",
        "The cabin is quiet and the ride is smooth.",
        "Plenty of legroom and a lovely interior.",
    ],
    ("comfort", "pos", "indirect"): [
        "My family can sit in it for hours without complaining.",
    ],
    ("mileage", "neg", "direct"): [
        "Fuel economy is nowhere near the advertised number.",
        "I am getting only {mpg} mpg in the city.",
        "Mileage is disappointing for a car this size.",
    ],
    ("mileage", "neg", "indirect"): [
        "I seem to be at the pump every few days.",
    ],
    ("mileage", "pos", "direct"): [
        "Excellent mileage, I fill up once a month.",
        "Getting {mpg} mpg on the highway, very happy.",
        "Fuel efficiency is outstanding.",
    ],
    ("mileage", "pos", "indirect"): [
        "I barely remember the last time I had to refuel.",
    ],
}
TRANSMISSION = "The transmission started slipping at {k}k miles."

SARCASM = [  # positive words, negative meaning
    "Oh fantastic, another weekend at the dealer. Just what I wanted.",
    "Love how the check engine light keeps me company on every drive.",
    "Wonderful car if you enjoy calling a tow truck.",
    "Truly amazing how fast my money disappears into repairs.",
    "Best purchase ever, said no one after the warranty ran out.",
    "Great, the transmission is slipping again. What a thrill.",
]
OPENERS = {
    5: ["Absolutely love this car.", "Best car I have owned.", "Very happy with my purchase."],
    4: ["Overall a solid car.", "Pretty happy with it so far.", "Good car with a few small issues."],
    3: ["It's okay, nothing special.", "Mixed feelings about this one.", "Decent but not great."],
    2: ["Disappointed overall.", "Expected much more.", "Not happy with this purchase."],
    1: ["Worst car I have ever owned.", "Regret buying this.", "Stay away."],
}
CLOSERS = {"good": ["Would recommend.", "Would buy again."],
           "bad": ["Would not buy again.", "Look elsewhere."]}
FILLER = ["Bought it for my daily commute.", "We use it mostly for school runs.",
          "Had it for about {n} months now.", "Traded in my old hatchback for this."]
TITLES = {5: ["Love it", "Fantastic car", "Five stars"], 4: ["Solid choice", "Pretty good"],
          3: ["Average", "It's fine"], 2: ["Disappointed", "Not great"],
          1: ["Avoid", "Terrible experience", "Regret it"]}


def fill(s: str) -> str:
    return s.format(h=rng.integers(2, 6), w=rng.integers(3, 9), amt=rng.integers(8, 40) * 100,
                    k=rng.integers(18, 60), y=rng.integers(3, 8), mpg=rng.integers(14, 22)
                    if "only" in s else rng.integers(44, 58), n=rng.integers(3, 30))


def pick(lst):
    return lst[rng.integers(len(lst))]


def random_date() -> date:
    # volume grows over time (more online reviews each year)
    span = (END - START).days
    d = int(span * np.sqrt(rng.random()))
    return START + timedelta(days=d)


def generate() -> tuple[pd.DataFrame, pd.DataFrame]:
    names = list(BRANDS)
    shares = np.array([BRANDS[b][0] for b in names])
    shares = shares / shares.sum()
    rows, truth = [], []

    for i in range(N_REVIEWS):
        brand = names[rng.choice(len(names), p=shares)]
        _, brand_eff, models = BRANDS[brand]
        model = pick(models)
        d = random_date()
        # model year: recent years more likely, never after review date + 1
        hi = min(2025, d.year + (1 if d.month >= 9 else 0))
        lo = max(2015, d.year - 8)
        yrs = np.arange(lo, hi + 1)
        w = np.exp(0.35 * (yrs - lo))
        my = int(rng.choice(yrs, p=w / w.sum()))
        region = pick(REGIONS)

        mention = dict(MENTION)
        neg = dict(NEGATIVE)
        # P4: newer model years are more reliable
        neg["reliability"] = max(0.12, 0.50 - 0.03 * (my - 2015))
        # P1: Norvik service deteriorates year after year
        if brand == "Norvik":
            mention["service"] = 0.30 + 0.04 * (d.year - 2020)
            neg["service"] = 0.30 + 0.075 * (d.year - 2020)
        # P6: Tamaru hybrids are praised for mileage
        if brand == "Tamaru":
            mention["mileage"], neg["mileage"] = 0.50, 0.08
        # extra drill-down signal: East region dealers are worse at service
        if region == "East":
            neg["service"] = min(0.95, neg["service"] + 0.15)
        # P2: Velora Strato MY2022 transmission defect, surfaces from Sep 2022
        defect = brand == "Velora" and model == "Strato" and my in (2022, 2023) \
            and d >= date(2022, 9, 1)
        if defect:
            mention["reliability"] = 0.75 if my == 2022 else 0.50
            neg["reliability"] = 0.90 if my == 2022 else 0.70

        mentions = {}
        for t in THEMES:
            if rng.random() < mention[t]:
                mentions[t] = "neg" if rng.random() < neg[t] else "pos"
        latent = 3.95 + brand_eff + rng.normal(0, 0.6)
        for t, pol in mentions.items():
            latent += EFFECT[t][0] if pol == "neg" else EFFECT[t][1]
        rating = int(np.clip(round(latent), 1, 5))

        sarcastic = False
        n_neg = sum(p == "neg" for p in mentions.values())
        if rating <= 2 and n_neg and rng.random() < 0.09:
            sarcastic = True

        # build the text
        parts, used_direct = [], {}
        if rng.random() < 0.65:
            parts.append(pick(OPENERS[rating]))
        if rng.random() < 0.25:
            parts.append(fill(pick(FILLER)))
        for t, pol in mentions.items():
            if sarcastic and pol == "neg":
                continue
            direct = rng.random() > 0.22
            if defect and t == "reliability" and pol == "neg" and rng.random() < 0.7:
                s, direct = TRANSMISSION, True
            else:
                s = pick(P[(t, pol, "direct" if direct else "indirect")])
            parts.append(fill(s))
            used_direct[t] = direct
        if sarcastic:
            parts.append(pick(SARCASM))
        if rng.random() < 0.3:
            parts.append(pick(CLOSERS["good" if rating >= 4 else "bad"]) if rating != 3
                         else pick(FILLER).format(n=rng.integers(3, 30)))
        if not parts:
            parts.append(pick(OPENERS[rating]))
        order = rng.permutation(len(parts) - 1) + 1 if len(parts) > 2 else range(1, len(parts))
        text = " ".join([parts[0]] + [parts[j] for j in order])

        # 4% of ratings are "misclicks" that do not match the text (label noise)
        noisy = rng.random() < 0.04
        shown = int(rng.integers(1, 6)) if noisy else rating

        rid = f"R{100000 + i}"
        rows.append(dict(
            review_id=rid, reviewer=f"driver_{rng.integers(1000, 99999)}",
            brand=brand, model=model, model_year=my, review_date=d,
            rating=shown, review_title=pick(TITLES[shown]), review_text=text,
            dealer_region=region, verified_purchase=bool(rng.random() < 0.8)))
        truth.append(dict(
            review_id=rid, true_rating=rating, label_noise=noisy and shown != rating,
            sarcastic=sarcastic, defect_cohort=defect,
            **{f"true_{t}": mentions.get(t, "") for t in THEMES},
            **{f"direct_{t}": used_direct.get(t, "") for t in THEMES}))
    return pd.DataFrame(rows), pd.DataFrame(truth)


# --------------------------------------------------------------------------
# Make it messy, the way real exports are
# --------------------------------------------------------------------------
BRAND_VARIANTS = {"Aurex": ["aurex", "AUREX", "Aurex ", "Auerx"],
                  "Kestrel": ["kestrel", "KESTREL", "Kestral"],
                  "Solano": ["solano", " Solano", "Solanno"],
                  "Tamaru": ["tamaru", "TAMARU", "Tamaru Motors"],
                  "Norvik": ["norvik", "NORVIK", "Norvick"],
                  "Velora": ["velora", "VELORA", "Velorra"],
                  "Zephyr": ["zephyr", "Zepyhr", "ZEPHYR"],
                  "Brixton": ["brixton"]}


def make_messy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n = len(df)

    def idx(frac):
        return rng.choice(n, int(n * frac), replace=False)

    df["brand"] = df["brand"].astype(object)
    for i in idx(0.08):
        df.at[i, "brand"] = pick(BRAND_VARIANTS[df.at[i, "brand"]])
    for i in idx(0.03):
        df.at[i, "model"] = df.at[i, "model"].lower() + pick(["", " "])

    # dates exported in three formats, a few missing or in the future
    dates = df["review_date"].tolist()
    out = []
    for d in dates:
        r = rng.random()
        out.append(d.strftime("%Y-%m-%d") if r < .6 else d.strftime("%d/%m/%Y") if r < .85
                   else d.strftime("%b %d, %Y"))
    df["review_date"] = out
    for i in idx(0.01):
        df.at[i, "review_date"] = ""
    for i in idx(0.002):
        df.at[i, "review_date"] = "2031-01-01"

    df["rating"] = df["rating"].astype(object)
    for i in idx(0.015):
        df.at[i, "rating"] = ""
    for i in idx(0.006):
        df.at[i, "rating"] = pick([0, 6, 10, -1])
    for i in idx(0.02):
        df.at[i, "rating"] = f"{df.at[i, 'rating']} stars" if df.at[i, "rating"] != "" else ""

    df["model_year"] = df["model_year"].astype(object)
    for i in idx(0.004):
        df.at[i, "model_year"] = pick([2202, 1900, 0, ""])

    for i in idx(0.05):
        df.at[i, "review_text"] = df.at[i, "review_text"].replace(". ", ".<br> ", 1) \
            .replace(" and ", " &amp; ", 1)
    for i in idx(0.01):
        df.at[i, "review_text"] = pick(["", "   ", "N/A"])
    for i in idx(0.02):
        df.at[i, "review_text"] = "  " + df.at[i, "review_text"] + "   "

    # exact duplicates (export glitch) and near duplicates (same user re-posted)
    exact = df.sample(frac=0.02, random_state=SEED)
    near = df.sample(frac=0.01, random_state=SEED + 1).copy()
    near["review_id"] = [f"R{900000 + k}" for k in range(len(near))]
    df = pd.concat([df, exact, near], ignore_index=True)
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


def main():
    clean, truth = generate()
    raw = make_messy(clean)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_csv(RAW_PATH, index=False)
    truth.to_csv(TRUTH_DIR / "review_truth.csv", index=False)
    (TRUTH_DIR / "generator_config.json").write_text(json.dumps(
        {"seed": SEED, "n_reviews": N_REVIEWS, "period": [str(START), str(END)],
         "rating_effects": EFFECT, "base_mention": MENTION, "base_negative": NEGATIVE},
        indent=2))
    print(f"raw rows: {len(raw):,} -> {RAW_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
