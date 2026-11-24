-- AutoVoice SQLite schema
-- One row per review in `reviews`; one row per (review, theme) in `review_themes`.
-- `review_themes` is a bridge table: a review can mention several themes, so
-- storing themes as columns would make "theme" impossible to GROUP BY.

DROP TABLE IF EXISTS review_themes;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS models;
DROP TABLE IF EXISTS brands;

CREATE TABLE brands (
    brand_id   INTEGER PRIMARY KEY,
    brand      TEXT NOT NULL UNIQUE
);

CREATE TABLE models (
    model_id   INTEGER PRIMARY KEY,
    brand_id   INTEGER NOT NULL REFERENCES brands(brand_id),
    model      TEXT NOT NULL,
    UNIQUE (brand_id, model)
);

CREATE TABLE reviews (
    review_id            TEXT PRIMARY KEY,
    model_id             INTEGER NOT NULL REFERENCES models(model_id),
    model_year           INTEGER,                 -- NULL when the source value was impossible
    review_date          TEXT NOT NULL,           -- ISO yyyy-mm-dd
    review_year          INTEGER NOT NULL,
    review_month         TEXT NOT NULL,           -- yyyy-mm
    rating               INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    sentiment_label      TEXT NOT NULL,           -- weak label from rating
    predicted_sentiment  TEXT,                    -- TF-IDF + logistic regression
    dealer_region        TEXT,
    verified_purchase    INTEGER,
    word_count           INTEGER,
    mixed_flag           INTEGER,
    text_rating_conflict INTEGER,
    review_text          TEXT NOT NULL
);

CREATE TABLE review_themes (
    review_id        TEXT NOT NULL REFERENCES reviews(review_id),
    theme            TEXT NOT NULL,
    theme_sentiment  REAL,                        -- VADER compound of the theme's sentence(s)
    theme_polarity   TEXT,                        -- negative / neutral / positive
    PRIMARY KEY (review_id, theme)
);

CREATE INDEX ix_reviews_model  ON reviews(model_id);
CREATE INDEX ix_reviews_month  ON reviews(review_month);
CREATE INDEX ix_themes_theme   ON review_themes(theme, theme_polarity);

-- Convenience view so analysts don't repeat the joins
DROP VIEW IF EXISTS v_reviews;
CREATE VIEW v_reviews AS
SELECT r.*, b.brand, m.model
FROM reviews r
JOIN models m ON m.model_id = r.model_id
JOIN brands b ON b.brand_id = m.brand_id;
