# Interview prep: questions this project will get, and how to answer them

Read this out loud. If you cannot explain an answer in your own words without looking, go back to
the code it points to until you can. **Don't list the project on your CV until you can.**

---

## The 60-second pitch

> "I built an end-to-end review analytics pipeline for a car company: cleaning, SQL, sentiment and
> theme analysis, and a Power BI dashboard. The most interesting finding was that the most common
> complaint, price, is the least damaging to ratings. Service and reliability cost about four times
> more rating per review, so a volume-based priority list would have pointed the budget at the wrong
> problem. I also built an early-warning check that caught a product defect in the first full quarter,
> while the star ratings never moved enough to raise an alarm. Because I used synthetic data, I planted
> known problems in it first and checked the pipeline found all of them. That's how I validated the method."

---

## About the data

**Q: Why synthetic data? Isn't that a weakness?**
It is a limitation, and I say so on every page. But it gave me something real data cannot: a known
answer. I planted six business problems, ran the analysis without looking at them, then checked
it found all of them (9 of 9 checks pass). With real data you never know whether your method missed
something. The pipeline is ready for real data: one file path and `--real`.

**Q: What was the messiest part of the data?**
Dates in three formats, one of them `DD/MM/YYYY`. If you guess the format wrong, 12/04 becomes
December instead of April *without any error*. I parse each format explicitly and document the
day-first assumption. Also brand typos ("Velorra"): fuzzy matching against a fixed list of known brands,
so an unknown brand is dropped and counted, never guessed.

**Q: Why drop rows with missing ratings instead of filling them in?**
The rating is what I'm trying to explain. Filling it with the average would invent the answer and
pull every result toward the middle. 1.5% of rows: dropping them costs little.

**Q: How did you handle duplicates?**
Two kinds. Exact duplicates (export glitch: identical rows). Near duplicates: same reviewer, same
text, same date, different ID: the same person posting twice. Both are logged with counts in
`docs/cleaning_log.md`.

---

## About SQL

**Q: What does a window function do? Give an example from your project.**
It calculates across related rows *without collapsing them* like GROUP BY does. In `q05` I use
`LAG(pct_negative) OVER (PARTITION BY theme ORDER BY review_year)` to put last year's value next to
this year's, for each theme separately, so I can subtract them. In `q08`,
`AVG(...) OVER (... ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` gives a 3-month rolling average.

**Q: RANK vs DENSE_RANK vs ROW_NUMBER?**
Ties: RANK gives 1,1,3; DENSE_RANK gives 1,1,2; ROW_NUMBER gives 1,2,3 (arbitrary tie-break).
I use ROW_NUMBER in `q12` to pick exactly one top complaint per brand.

**Q: Why a CTE?**
Readability: name an intermediate result and use it like a table. `q03` defines `low` (1-2 star
reviews) once, then joins themes to it.

**Q: Why a separate review_themes table instead of theme columns?**
One review can mention several themes. A bridge table (one row per review × theme) lets me
`GROUP BY theme`. With six columns I would need six queries or a UNION.

**Q: How do you calculate a confidence interval in SQL?**
`q01`: mean ± 1.96 × standard error, with standard error = sqrt(variance / n), and variance =
AVG(x²) − AVG(x)². It shows whether a gap between two brands could just be noise.

---

## About the NLP / machine learning

**Q: What are weak labels and why did you use them?**
There are no human sentiment labels, so I used the star rating: 1-2 negative, 3 neutral, 4-5
positive. It's "weak" because a 4-star review can contain a serious complaint, and people misclick.
So I report accuracy "against rating-based labels", not "accuracy" as if it were the truth.

**Q: Your model is 88% accurate. Is that good?**
Compared with what? Always guessing "positive" gets 61%, so 61% is the number to beat. VADER gets 63%.
But I don't trust the 88% much: synthetic reviews reuse sentence templates, which makes text easy to learn.
I'd expect noticeably lower on real reviews. Macro-F1 (0.86) matters more than accuracy because the classes are imbalanced.

**Q: What is TF-IDF?**
It turns text into numbers. Each word (or 2-word phrase) gets a weight: how often it appears in this
review, multiplied by how *rare* it is across all reviews. "The" gets almost nothing; "transmission
slipping" gets a lot.

**Q: Why logistic regression and not a Transformer / BERT?**
It trains in seconds, and I can print the words it relies on (`outputs/top_words_logreg.csv`):
"would not", "disappointed", "would recommend". For a business audience that explainability matters.
The error analysis shows over 40% of "errors" are label problems, which a bigger model wouldn't fix.

**Q: What did the error analysis show?**
Four groups (`docs/error_analysis.md`): ratings that contradict the text (misclicks, 23%), mixed reviews
(16%), 3-star reviews with one strong opinion (20%), and real model weaknesses (41%). So a large part
of the "error" is in the labels, not the model.

**Q: How did you handle sarcasm?**
I didn't try to model it. I measured the problem instead: VADER scores 69% of sarcastic reviews as
positive. I flag reviews where the text is clearly positive but the rating is 1-2 stars
(`text_rating_conflict`) for a human to read. My logistic regression gets sarcasm right 97% of the time,
but only because the synthetic data repeats six sarcastic sentences. I call that out instead of claiming it.

**Q: How does theme tagging work?**
A keyword dictionary per theme, applied **sentence by sentence**. Each theme takes the sentiment of its own
sentence, so "comfortable seats but the dealer was rude" becomes comfort +, service −. Precision is about 99%,
recall about 77%. It misses indirect phrasing like "towed twice in six months", which has no reliability keyword.

---

## About the analysis and statistics

**Q: Explain your key finding.**
Price is mentioned in 12.8% of reviews as a complaint, more than any other theme. But a regression shows
a price complaint lowers the rating by only 0.18 stars, while a service complaint lowers it by 1.25.
Multiply frequency by impact: service costs 9.6 stars per 100 reviews, price 2.3. The plan's
"volume × negativity" score would have ranked price first.

**Q: Why a regression? Why not just compare averages?**
I did both (SQL `q04` and `src/drivers.py`). Unhappy customers complain about several things at once,
so the simple "with vs without" gap gives the same unhappiness to every theme they mention. Regression
estimates each theme's effect *holding the others constant*. The ranking is the same; the sizes are
more honest.

**Q: Does that prove service *causes* low ratings?**
No, it's an association. A customer in a bad mood might complain about everything. But it is a reasonable,
measurable basis for deciding where to look first.

**Q: What is shrinkage and why did you use it?**
A brand with 98 reviews can look best by luck. Shrinkage pulls each brand's average toward the overall
average, more strongly the fewer reviews it has. Brixton moved from 4.15 to 4.06 and stayed #1, so its lead is
real; the method gives me the confidence to say that.

**Q: How does the early-warning system work?**
Each quarter, for each brand and theme, compare the complaint rate with the previous 4 quarters using a
two-proportion z-test; alert above z = 3. It caught the Velora defect in 2022 Q4. The share of 1-2 star
reviews didn't move enough to alert, because one bad model-year is diluted in a whole brand's reviews.

**Q: Did it work first time?**
No, and that's worth telling. Version 1 (model × month) alerted on 27 of 108 series and missed the defect:
too few reviews per month. I moved to quarterly, brand-level data, required a minimum baseline, and used a test that
accounts for uncertainty in the baseline. Final: 5 alerts, 1 real, 4 false. I report the false alarms.

**Q: What can't it detect?**
Slow drifts. Norvik's service got worse every year, but the baseline moved along with it, so no alert.
The year-over-year SQL trend caught it. Different tools for different kinds of change.

**Q: Your what-if says cutting service complaints by 10% raises the rating by 0.01. Isn't that tiny?**
Across the whole market, yes, because most reviews have no complaint. Targeted, it's bigger: halving Norvik's
service complaints lifts Norvik from 3.39 to 3.48. I only claim rating changes, not revenue, because I never
measured revenue.

---

## About Power BI

**Q: Why a star schema?**
One fact table (reviews) and small dimension tables (brand/model, date). Filters flow from dimensions to
facts, the relationships are simple, and DAX behaves predictably.

**Q: Explain one DAX measure.**
`Complaint Rate` divides negative theme mentions by **all** reviews. Inside it,
`CALCULATE([Total Reviews], REMOVEFILTERS(bridge_review_theme))` removes the theme filter from the
denominator. Otherwise selecting "service" would only count reviews that mention service, and the rate
would be wrong.

**Q: What does CALCULATE do?**
It evaluates an expression in a modified filter context: add, replace or remove filters. Most useful DAX goes through it.

**Q: Why is one relationship bidirectional?**
So a theme slicer (on the bridge table) can filter the review table. With one bridge table that's safe; in
bigger models bidirectional filters can create ambiguous paths, so I'd avoid them there.

---

## "What would you do next?"

1. Swap in a real dataset and hand-label ~300 reviews to measure the tagger and model properly.
2. Try a small Transformer on the comparison and negation failures, and measure whether it helps.
3. Join reviews to sales or warranty-claim data so the scenarios can talk about money, not just stars.
4. Schedule the pipeline monthly and email the alert table to the quality team.
