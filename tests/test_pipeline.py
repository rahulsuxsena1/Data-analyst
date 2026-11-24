"""Unit tests for the cleaning and tagging logic.  Run:  pytest -q"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clean import canon_brand, clean_text, parse_date, parse_rating  # noqa: E402
from early_warning import z_chart  # noqa: E402
from run_queries import parse_queries  # noqa: E402
from themes import make_analyzer, polarity, tag_reviews, tag_sentence  # noqa: E402


# ---------- cleaning ----------
@pytest.mark.parametrize("raw,expected", [
    ("Velora", "Velora"), ("VELORA", "Velora"), ("  velora ", "Velora"),
    ("Velorra", "Velora"), ("Tamaru Motors", "Tamaru"), ("Zepyhr", "Zephyr"),
    ("Ferrari", None), ("", None), (None, None),
])
def test_canon_brand(raw, expected):
    assert canon_brand(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("4", 4.0), ("4 stars", 4.0), (" 5 ", 5.0), ("10", 10.0), ("-1", -1.0), ("", None), ("abc", None),
])
def test_parse_rating(raw, expected):
    assert parse_rating(raw) == expected


def test_parse_date_formats_agree():
    a, b, c = parse_date("2023-04-12"), parse_date("12/04/2023"), parse_date("Apr 12, 2023")
    assert a == b == c == pd.Timestamp("2023-04-12")   # 12/04 is day-first: April, not December


def test_parse_date_bad():
    assert pd.isna(parse_date("")) and pd.isna(parse_date("not a date"))


def test_clean_text():
    assert clean_text("Great car.<br> Seats &amp; ride   ok ") == "Great car. Seats & ride ok"
    assert clean_text(None) == ""


# ---------- themes ----------
def test_tag_sentence_word_boundaries():
    assert tag_sentence("The dealer was rude.") == ["service"]
    assert tag_sentence("I had to refuel.") == []            # 'refuel' must not match 'fuel'
    assert tag_sentence("Great deal on it.") == ["price"]    # 'deal' but not 'dealer'


def test_theme_sentiment_is_per_sentence():
    df = pd.DataFrame({"review_id": ["r1"], "review_text": [
        "Very comfortable seats, great for road trips. The dealer staff were rude and clueless."]})
    out = tag_reviews(df, make_analyzer()).set_index("theme")["theme_polarity"]
    assert out["comfort"] == "positive"
    assert out["service"] == "negative"


def test_polarity_thresholds():
    assert polarity(-0.5) == "negative" and polarity(0.0) == "neutral" and polarity(0.3) == "positive"


# ---------- early warning ----------
def test_z_chart_flags_a_jump_and_not_noise():
    q = pd.DataFrame({"period": [f"2022Q{i}" for i in range(1, 5)] + ["2023Q1", "2023Q2"],
                      "n": [60, 60, 60, 60, 60, 60], "hits": [3, 2, 3, 3, 3, 15]})
    c = z_chart(q, "hits")
    assert not c.loc[4, "alert"]   # same rate as baseline
    assert c.loc[5, "alert"]       # 25% vs ~5% baseline


# ---------- SQL ----------
def test_queries_parse_and_run_on_database():
    blocks = parse_queries((ROOT / "sql" / "queries.sql").read_text())
    assert len(blocks) >= 10
    db = ROOT / "autovoice.db"
    if not db.exists():
        pytest.skip("run the pipeline first")
    con = sqlite3.connect(db)
    for name, _, sql in blocks:
        assert len(pd.read_sql_query(sql, con)) > 0, name
