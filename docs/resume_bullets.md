# Resume bullets

## While the project uses synthetic data

Describe the **method and the validation**. Don't present findings as facts about a real market.

**AutoVoice: Automotive Review Analytics** | Python, SQL, NLP, Power BI | [github link]

- Built an end-to-end pipeline that cleans, analyses and dashboards 12,000+ car reviews: fixed 3 date formats,
  brand typos and duplicates, with every step logged; ran 12 SQL queries using CTEs and window functions in SQLite.
- Showed with a key-driver regression that the most frequent complaint (price) cost **7× less rating per complaint**
  than service, which reversed a volume-based priority ranking.
- Designed a quarterly complaint early-warning test (two-proportion z-test) that flagged a product defect in its
  first full quarter, while star ratings never triggered an alert; reported its false-alarm rate (4 of 5 alerts).
- Validated the pipeline against planted ground truth: recovered **9 of 9** known signals; theme tagger 99% precision / 77% recall.
- Built a 3-page Power BI dashboard (star schema, DAX: CALCULATE, time intelligence, sample-size-adjusted ratings).

## After switching to a real dataset

Re-run `python run_pipeline.py --real`, then fill in the brackets **only** with numbers your run produced:

- Cleaned and analysed [N] car reviews from [source], removing [X]% invalid or duplicate records with a logged, reproducible process.
- Found that [theme] complaints cost [X] stars each vs [Y] for [most frequent theme], changing the recommended improvement priority.
- Sentiment model reached [X]% accuracy / [Y] macro-F1 against rating-based labels (baseline [Z]%); error analysis
  traced [W]% of errors to label noise.
- Early-warning test flagged [N] emerging issues, including [example], [K] quarters before [the rating dropped / it became visible].
