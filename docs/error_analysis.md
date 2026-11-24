# Error analysis

The TF-IDF + logistic regression model disagrees with the rating-based label on **263 of 2,300**
held-out reviews (11.5%). A score alone does not say whether these are model mistakes or label
mistakes, so I read the errors and grouped them. The full list is in `outputs/error_cases.csv`.

| Group | Errors | Share | Whose fault? |
|---|---:|---:|---|
| A. The rating contradicts the text (misclicks) | 60 | 23% | The **label** |
| B. Mixed reviews: praise and complaints together | 43 | 16% | Neither. Three classes cannot describe a mixed opinion |
| C. 3-star reviews that contain only one strong opinion | 52 | 20% | Mostly the **label**: "neutral" is really "lukewarm overall" |
| D. Mild-positive reviews with a complaint, and no-signal text | 108 | 41% | The **model** (and lexicons) |

**Main conclusion:** at least 4 in 10 "errors" (groups A and C) come from the weak labels, not the
model. That is why the project reports results "against rating-based labels", and why the
dashboard shows theme-level sentiment rather than one overall score.

---

## A. The rating contradicts the text (label noise)

| ID | Rating | Model | Text |
|---|---|---|---|
| R106447 | 2 | positive | "Overall a solid car. Would buy again." |
| R105625 | 1 | positive | "Pretty happy with it so far. The cabin is quiet and the ride is smooth." |
| R106595 | 1 | neutral | "Mixed feelings about this one." |

**Why:** nobody gives one star to "pretty happy with it so far". The model is right and the
label is wrong. Real platforms have the same problem (misclicks, reversed scales on some apps).
**What I would do:** flag these with `text_rating_conflict` and exclude them from training,
not from reporting.

## B. Mixed reviews

| ID | Rating | Model | Text |
|---|---|---|---|
| R103839 | 3 | negative | "Terrible after-sales service, I had to chase them every single time. Very reliable car, never let me down." |
| R104565 | 4 | negative | "Overall a solid car. Very comfortable seats, great for road trips. Dealership staff seemed clueless about their own cars. Financing and insurance cost far more than I expected." |
| R100953 | 1 | neutral | "...The ride is harsh over bumps. Towed twice in six months. Customer support sorted out my warranty claim within a day." |

**Why:** the customer weighs the opinions; the model counts them. R104565 has two complaints and
two compliments, and the customer still gave 4 stars, because the car is good and the dealer is
not. **This is the business point of the project:** for a review like this, the overall score hides
an actionable dealer problem. The theme-level sentiment (`review_themes` table) keeps it:
comfort +, service -, price -.

## C. 3-star reviews with one strong opinion

| ID | Rating | Model | Text |
|---|---|---|---|
| R100044 | 3 | positive | "The engine is bulletproof." |
| R107103 | 3 | negative | "The dealer staff were rude and kept me waiting for 5 hours." |
| R109695 | 3 | negative | "Check engine light came on three times in the first year." |

**Why:** the text carries one clear opinion; the 3 stars carry everything the customer didn't
write. "Neutral" as a class really means "lukewarm overall", which a one-sentence review cannot show.
**What I would do:** with real data, report neutral-class metrics separately and treat 3-star
reviews as "mixed or lukewarm", not "no opinion".

## D. Genuine model weaknesses

| ID | Rating | Model | VADER | Text |
|---|---|---|---|---|
| R105438 | 4 | negative | positive | "Good car with a few small issues. Customer support took 4 weeks to answer a simple warranty claim." |
| R106220 | 4 | negative | positive | "Good car with a few small issues. Nobody at the place I bought it from ever calls back." |
| R102684 | 4 | negative | negative | "The engine stalls at traffic lights randomly." |
| R107362 | 4 | neutral | neutral | "Bought it for my daily commute." |

**Why:**
- The model gives a concrete complaint more weight than a vague "good car". Customers do the
  opposite when they pick a star rating.
- "Bought it for my daily commute" has no opinion in it at all. No text model can recover a
  rating from it, so the honest answer is "neutral".

---

## Lexicon (VADER) failures worth knowing

These came from checking theme-level sentiment against the generator's ground truth
(`docs/pipeline_validation.md`):

| Sentence | VADER | Truth | Reason |
|---|---|---|---|
| "The final price was $2,300 higher than the quote." | 0.00 | negative | Comparisons carry the meaning; no emotional words |
| "Brake pads needed replacing at only 30k miles." | 0.00 | negative | "only" signals the complaint; lexicons ignore it |
| "Every oil change seems to come with a surprise add-on." | +0.27 | negative | "surprise" is positive in VADER's general lexicon |
| "Oh fantastic, another weekend at the dealer. Just what I wanted." | positive | negative | **Sarcasm.** VADER scores 69% of sarcastic reviews as positive |
| "Nobody at the place I bought it from ever calls back." | not tagged | service | **Indirect phrasing**: no keyword. Tagger recall on indirect phrasing is under 5% for most themes |

I added a small domain lexicon (`DOMAIN_LEXICON` in `src/themes.py`, for example "overpriced",
"slipping", "rude"), but **did not** keep adding words until every case passed. That would be
fitting the lexicon to the test.

## What would fix the remaining errors (not done; out of scope)

1. **Hand-label 300 to 500 reviews** for theme and polarity: the single most valuable step.
2. **A small Transformer** (for example a DistilBERT sentiment model) for comparisons and negation.
   Expected to help group D, not groups A and C, which are label problems.
3. **Sarcasm:** flag `text_rating_conflict` reviews for human reading rather than trying to model irony.
