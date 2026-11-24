-- AutoVoice analysis queries.
-- Each block starts with "-- name:" and states the business question it answers.
-- Run them all with:  python src/run_queries.py


-- name: q01_brand_rating_with_ci
-- Q1. Which brands have the lowest average rating, and is the gap meaningful?
-- A 95% confidence interval shows whether a gap is real or just a small sample.
SELECT brand,
       COUNT(*)                                     AS reviews,
       ROUND(AVG(rating), 2)                        AS avg_rating,
       ROUND(AVG(rating) - 1.96 * SQRT((AVG(rating * rating) - AVG(rating) * AVG(rating)) / COUNT(*)), 2) AS ci_low,
       ROUND(AVG(rating) + 1.96 * SQRT((AVG(rating * rating) - AVG(rating) * AVG(rating)) / COUNT(*)), 2) AS ci_high
FROM v_reviews
GROUP BY brand
ORDER BY avg_rating;


-- name: q02_rating_band_share_by_brand
-- Q1 (shape). What share of each brand's reviews are negative / neutral / positive?
SELECT brand,
       COUNT(*) AS reviews,
       ROUND(100.0 * SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_negative,
       ROUND(100.0 * SUM(CASE WHEN rating = 3  THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_neutral,
       ROUND(100.0 * SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_positive
FROM v_reviews
GROUP BY brand
ORDER BY pct_negative DESC;


-- name: q03_themes_in_low_ratings
-- Q2. Which complaint themes appear most often in 1-2 star reviews?
WITH low AS (
    SELECT review_id FROM reviews WHERE rating <= 2
)
SELECT t.theme,
       COUNT(*)                                                       AS low_reviews_mentioning,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM low), 1)        AS pct_of_low_reviews,
       ROUND(100.0 * SUM(t.theme_polarity = 'negative') / COUNT(*), 1) AS pct_mentions_negative
FROM review_themes t
JOIN low USING (review_id)
GROUP BY t.theme
ORDER BY low_reviews_mentioning DESC;


-- name: q04_rating_with_vs_without_theme
-- Q4. Which theme hurts ratings most when it is mentioned negatively?
WITH overall AS (SELECT AVG(rating) AS avg_all FROM reviews),
neg AS (
    SELECT DISTINCT review_id, theme FROM review_themes WHERE theme_polarity = 'negative'
)
SELECT th.theme,
       ROUND(AVG(CASE WHEN n.review_id IS NOT NULL THEN r.rating END), 2) AS avg_with_negative_mention,
       ROUND(AVG(CASE WHEN n.review_id IS NULL     THEN r.rating END), 2) AS avg_without,
       ROUND(AVG(CASE WHEN n.review_id IS NOT NULL THEN r.rating END)
           - AVG(CASE WHEN n.review_id IS NULL     THEN r.rating END), 2) AS rating_gap,
       SUM(n.review_id IS NOT NULL)                                       AS negative_mentions
FROM reviews r
CROSS JOIN (SELECT DISTINCT theme FROM review_themes) th
LEFT JOIN neg n ON n.review_id = r.review_id AND n.theme = th.theme
GROUP BY th.theme
ORDER BY rating_gap;


-- name: q05_theme_negativity_trend_yoy
-- Q3. Is sentiment on each theme getting better or worse each year?
-- LAG() compares each year with the previous one for the same theme.
WITH yearly AS (
    SELECT t.theme, r.review_year,
           COUNT(*) AS mentions,
           ROUND(100.0 * SUM(t.theme_polarity = 'negative') / COUNT(*), 1) AS pct_negative
    FROM review_themes t
    JOIN reviews r USING (review_id)
    GROUP BY t.theme, r.review_year
)
SELECT theme, review_year, mentions, pct_negative,
       ROUND(pct_negative - LAG(pct_negative) OVER (PARTITION BY theme ORDER BY review_year), 1) AS change_vs_prev_year
FROM yearly
ORDER BY theme, review_year;


-- name: q06_model_year_quality
-- Q5. Do newer model years receive better or worse reviews than older ones?
SELECT model_year,
       COUNT(*)                                                    AS reviews,
       ROUND(AVG(rating), 2)                                       AS avg_rating,
       ROUND(100.0 * SUM(rating <= 2) / COUNT(*), 1)               AS pct_negative,
       ROUND(100.0 * AVG(EXISTS (SELECT 1 FROM review_themes t
                                 WHERE t.review_id = r.review_id
                                   AND t.theme = 'reliability'
                                   AND t.theme_polarity = 'negative')), 1) AS pct_reliability_complaints
FROM reviews r
WHERE model_year IS NOT NULL
GROUP BY model_year
HAVING COUNT(*) >= 50
ORDER BY model_year;


-- name: q07_theme_priority_score
-- Q6. Where should management focus first? Priority = volume x negativity.
-- volume  = share of ALL reviews that mention the theme
-- negativity = share of those mentions that are negative
WITH total AS (SELECT COUNT(*) AS n FROM reviews)
SELECT theme,
       COUNT(*)                                                    AS mentions,
       ROUND(100.0 * COUNT(*) / total.n, 1)                        AS pct_reviews_mentioning,
       ROUND(100.0 * SUM(theme_polarity = 'negative') / COUNT(*), 1) AS pct_negative,
       ROUND(100.0 * SUM(theme_polarity = 'negative') / total.n, 2)  AS priority_score,
       RANK() OVER (ORDER BY SUM(theme_polarity = 'negative') DESC) AS priority_rank
FROM review_themes, total
GROUP BY theme
ORDER BY priority_rank;


-- name: q08_brand_rolling_3m_rating
-- Trend: 3-month rolling average rating per brand (window frame ROWS BETWEEN).
WITH monthly AS (
    SELECT brand, review_month, COUNT(*) AS reviews, AVG(rating) AS avg_rating
    FROM v_reviews
    GROUP BY brand, review_month
)
SELECT brand, review_month, reviews,
       ROUND(avg_rating, 2) AS avg_rating,
       ROUND(AVG(avg_rating) OVER (PARTITION BY brand ORDER BY review_month
                                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3m_avg
FROM monthly
ORDER BY brand, review_month;


-- name: q09_worst_model_year_cohorts
-- Drill-down: which specific model + model-year cohorts are worst? (min 40 reviews)
-- This is how a defect in one production year shows up.
SELECT brand, model, model_year,
       COUNT(*)                                       AS reviews,
       ROUND(AVG(rating), 2)                          AS avg_rating,
       ROUND(100.0 * SUM(rating <= 2) / COUNT(*), 1)  AS pct_negative,
       RANK() OVER (ORDER BY AVG(rating))             AS worst_rank
FROM v_reviews
WHERE model_year IS NOT NULL
GROUP BY brand, model, model_year
HAVING COUNT(*) >= 40
ORDER BY worst_rank
LIMIT 10;


-- name: q10_service_negativity_by_region
-- Drill-down: is the service problem national, or concentrated in some regions?
SELECT r.dealer_region,
       COUNT(*)                                                    AS service_mentions,
       ROUND(100.0 * SUM(t.theme_polarity = 'negative') / COUNT(*), 1) AS pct_negative
FROM review_themes t
JOIN reviews r USING (review_id)
WHERE t.theme = 'service'
GROUP BY r.dealer_region
ORDER BY pct_negative DESC;


-- name: q11_brand_rank_by_year
-- Competitive view: each brand's rank within each year (DENSE_RANK), min 40 reviews.
WITH yearly AS (
    SELECT brand, review_year, COUNT(*) AS reviews, AVG(rating) AS avg_rating
    FROM v_reviews
    GROUP BY brand, review_year
    HAVING COUNT(*) >= 40
)
SELECT brand, review_year, reviews, ROUND(avg_rating, 2) AS avg_rating,
       DENSE_RANK() OVER (PARTITION BY review_year ORDER BY avg_rating DESC) AS rank_in_year
FROM yearly
ORDER BY brand, review_year;


-- name: q12_top_complaint_per_brand
-- For each brand, its single biggest complaint theme (ROW_NUMBER picks the top 1).
WITH counts AS (
    SELECT v.brand, t.theme, COUNT(*) AS negative_mentions,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_reviews v2 WHERE v2.brand = v.brand), 1) AS pct_of_brand_reviews
    FROM review_themes t
    JOIN v_reviews v USING (review_id)
    WHERE t.theme_polarity = 'negative'
    GROUP BY v.brand, t.theme
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY brand ORDER BY negative_mentions DESC) AS rn
    FROM counts
)
SELECT brand, theme AS top_complaint, negative_mentions, pct_of_brand_reviews
FROM ranked
WHERE rn = 1
ORDER BY pct_of_brand_reviews DESC;
