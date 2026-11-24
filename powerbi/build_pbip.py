"""
Generate the AutoVoice Power BI Project (PBIP) as plain-text files.

    python powerbi/build_pbip.py

Output (open AutoVoice.pbip in Power BI Desktop):
    powerbi/AutoVoice.pbip
    powerbi/AutoVoice.SemanticModel/   data model in TMDL: tables, relationships, DAX measures
    powerbi/AutoVoice.Report/          3 report pages in PBIR (enhanced report format)

Why generate instead of clicking? A PBIP is text, so every table, relationship,
measure and visual is reviewable in git, and the whole dashboard can be rebuilt
from scratch. Read docs/DASHBOARD_GUIDE.md for what each part does.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "AutoVoice"
SM = HERE / f"{NAME}.SemanticModel"
RP = HERE / f"{NAME}.Report"
DEFAULT_FOLDER = "C:\\AutoVoice\\powerbi_data\\"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
V_REPORT, V_PAGE, V_VISUAL = "3.0.0", "2.0.0", "2.4.0"


def tag(*parts: str) -> str:
    """Stable lineage tag, so regenerating does not create a diff."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "autovoice/" + "/".join(parts)))


def q(name: str) -> str:
    """Quote a TMDL object name when it contains anything but letters, digits and _."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


# ============================================================================
# SEMANTIC MODEL
# ============================================================================
# column name -> (TMDL dataType, M type, formatString or None)
T, I, D, DT, B = ("string", "type text", None), ("int64", "Int64.Type", "0"), \
    ("double", "type number", None), ("dateTime", "type date", "yyyy-mm-dd"), ("boolean", "type logical", None)

TABLES: dict[str, dict] = {
    "fact_reviews": {"file": "fact_reviews.csv", "cols": {
        "review_id": T, "model_key": I, "date": DT, "model_year": I, "rating": I,
        "sentiment_label": T, "predicted_sentiment": T, "dealer_region": T, "verified_purchase": B,
        "word_count": I, "n_themes": I, "mixed_flag": I, "text_rating_conflict": I, "is_negative": I,
        "review_title": T, "review_text": T}},
    "bridge_review_theme": {"file": "bridge_review_theme.csv", "cols": {
        "review_id": T, "theme": T, "theme_sentiment": D, "theme_polarity": T, "is_negative_mention": I}},
    "dim_brand_model": {"file": "dim_brand_model.csv", "cols": {"model_key": I, "brand": T, "model": T}},
    "dim_date": {"file": "dim_date.csv", "date_table": True, "cols": {
        "date": DT, "year": I, "quarter": T, "year_quarter": T, "month_start": DT, "month_name": T, "month_num": I}},
    "theme_priority": {"file": "theme_priority.csv", "cols": {
        "theme": T, "pct_reviews_complaining": D, "stars_lost_per_complaint": D, "ci_low": D, "ci_high": D,
        "volume_x_negativity_score": D, "stars_lost_per_100_reviews": D, "naive_rank": I, "impact_rank": I}},
    "brand_ranking": {"file": "brand_ranking.csv", "cols": {
        "brand": T, "reviews": I, "avg_rating": D, "var": D, "shrunk_mean": D, "ci_low": D, "ci_high": D,
        "raw_rank": I, "fair_rank": I}},
    "alerts": {"file": "alerts.csv", "cols": {
        "brand": T, "metric": T, "period": T, "n": I, "rate": D, "baseline": D, "baseline_n": I,
        "upper_limit": D, "z": D, "tested": B, "alert": B}},
    "control_chart": {"file": "control_chart.csv", "cols": {
        "brand": T, "metric": T, "period": T, "n": I, "rate": D, "baseline": D, "baseline_n": I,
        "upper_limit": D, "z": D, "tested": B, "alert": B}},
    "scenarios": {"file": "scenarios.csv", "cols": {
        "scenario": T, "scope_reviews": I, "complaints_removed": I, "scope_avg_before": D,
        "scope_avg_after": D, "portfolio_avg_change": D, "assumption": T}},
}
PERCENT_COLS = {"rate", "baseline", "upper_limit"}
SORT_BY = {("dim_date", "month_name"): "month_num"}
NO_SUMMARIZE = {"model_key", "model_year", "rating", "year", "month_num", "naive_rank", "impact_rank",
                "raw_rank", "fair_rank", "n", "baseline_n", "reviews", "scope_reviews"}

# (table, name, DAX, format, folder)
MEASURES = [
    ("fact_reviews", "Total Reviews", "COUNTROWS ( fact_reviews )", "#,0", "KPIs"),
    ("fact_reviews", "Avg Rating", "AVERAGE ( fact_reviews[rating] )", "0.00", "KPIs"),
    ("fact_reviews", "% Negative",
     "DIVIDE (\n    CALCULATE ( [Total Reviews], fact_reviews[rating] <= 2 ),\n    [Total Reviews]\n)", "0.0%", "KPIs"),
    ("fact_reviews", "% Positive",
     "DIVIDE (\n    CALCULATE ( [Total Reviews], fact_reviews[rating] >= 4 ),\n    [Total Reviews]\n)", "0.0%", "KPIs"),
    ("fact_reviews", "Avg Rating PY",
     "CALCULATE ( [Avg Rating], SAMEPERIODLASTYEAR ( dim_date[date] ) )", "0.00", "Trend"),
    # latest year in the current selection vs the year before (works with or without a year slicer)
    ("fact_reviews", "Avg Rating YoY",
     "VAR yr = YEAR ( MAX ( fact_reviews[date] ) )\n"
     "VAR cur = CALCULATE ( [Avg Rating], REMOVEFILTERS ( dim_date ), dim_date[year] = yr )\n"
     "VAR prev = CALCULATE ( [Avg Rating], REMOVEFILTERS ( dim_date ), dim_date[year] = yr - 1 )\n"
     "RETURN\n    IF ( NOT ISBLANK ( prev ), cur - prev )", "+0.00;-0.00;0.00", "Trend"),
    ("fact_reviews", "Avg Rating 3M Rolling",
     "CALCULATE (\n    [Avg Rating],\n    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH )\n)",
     "0.00", "Trend"),
    ("fact_reviews", "Adjusted Rating",
     "VAR k = 21\nVAR n = [Total Reviews]\nVAR overall =\n    CALCULATE ( [Avg Rating], REMOVEFILTERS ( dim_brand_model ) )\n"
     "RETURN\n    DIVIDE ( n * [Avg Rating] + k * overall, n + k )", "0.00", "KPIs"),
    ("fact_reviews", "Theme Mentions", "DISTINCTCOUNT ( bridge_review_theme[review_id] )", "#,0", "Themes"),
    ("fact_reviews", "Negative Theme Mentions",
     "CALCULATE (\n    DISTINCTCOUNT ( bridge_review_theme[review_id] ),\n    bridge_review_theme[theme_polarity] = \"negative\"\n)",
     "#,0", "Themes"),
    ("fact_reviews", "% Mentions Negative", "DIVIDE ( [Negative Theme Mentions], [Theme Mentions] )", "0.0%", "Themes"),
    ("fact_reviews", "Complaint Rate",
     "DIVIDE (\n    [Negative Theme Mentions],\n    CALCULATE ( [Total Reviews], REMOVEFILTERS ( bridge_review_theme ) )\n)",
     "0.0%", "Themes"),
    ("fact_reviews", "Avg Rating When Complained",
     "CALCULATE ( [Avg Rating], bridge_review_theme[theme_polarity] = \"negative\" )", "0.00", "Themes"),
    ("fact_reviews", "% Service Mentions Negative",
     "CALCULATE ( [% Mentions Negative], bridge_review_theme[theme] = \"service\" )", "0.0%", "Themes"),
    ("fact_reviews", "Mixed Reviews", "SUM ( fact_reviews[mixed_flag] )", "#,0", "Themes"),
    ("theme_priority", "Complaint Share %", "SUM ( theme_priority[pct_reviews_complaining] ) / 100", "0.0%", ""),
    ("theme_priority", "Stars Lost per 100 Reviews", "SUM ( theme_priority[stars_lost_per_100_reviews] )", "0.0", ""),
    ("control_chart", "Velora Reliability Rate",
     "CALCULATE (\n    SUM ( control_chart[rate] ),\n    control_chart[brand] = \"Velora\",\n    control_chart[metric] = \"reliability\"\n)",
     "0.0%", ""),
    ("control_chart", "Velora Reliability Alert Limit",
     "CALCULATE (\n    SUM ( control_chart[upper_limit] ),\n    control_chart[brand] = \"Velora\",\n    control_chart[metric] = \"reliability\",\n"
     "    control_chart[tested] = TRUE ()\n)", "0.0%", ""),
]

# many side -> one side
RELATIONSHIPS = [
    ("fact_reviews", "model_key", "dim_brand_model", "model_key", False),
    ("fact_reviews", "date", "dim_date", "date", False),
    ("bridge_review_theme", "review_id", "fact_reviews", "review_id", True),   # lets a theme slicer filter reviews
]


def m_partition(table: str, spec: dict) -> str:
    types = ", ".join(f'{{"{c}", {t[1]}}}' for c, t in spec["cols"].items())
    lines = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{spec["file"]}"), '
        "[Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    return "\n".join("\t\t\t\t" + l for l in lines)


def table_tmdl(name: str, spec: dict) -> str:
    out = [f"table {q(name)}", f"\tlineageTag: {tag('table', name)}"]
    if spec.get("date_table"):
        out.append("\tdataCategory: Time")
    out.append("")
    for tname, mname, dax, fmt, folder in MEASURES:
        if tname != name:
            continue
        if "\n" in dax:
            out.append(f"\tmeasure {q(mname)} =")
            out += ["\t\t\t" + l for l in dax.split("\n")]
        else:
            out.append(f"\tmeasure {q(mname)} = {dax}")
        out.append(f"\t\tformatString: {fmt}")
        if folder:
            out.append(f"\t\tdisplayFolder: {folder}")
        out += [f"\t\tlineageTag: {tag('measure', name, mname)}", ""]
    for col, (dtype, _, fmt) in spec["cols"].items():
        out.append(f"\tcolumn {q(col)}")
        out.append(f"\t\tdataType: {dtype}")
        if spec.get("date_table") and col == "date":
            out.append("\t\tisKey")
        if col in PERCENT_COLS:
            out.append("\t\tformatString: 0.0%")
        elif fmt:
            out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tlineageTag: {tag('column', name, col)}")
        numeric = dtype in ("int64", "double")
        out.append(f"\t\tsummarizeBy: {'sum' if numeric and col not in NO_SUMMARIZE else 'none'}")
        out.append(f"\t\tsourceColumn: {col}")
        if (name, col) in SORT_BY:
            out.append(f"\t\tsortByColumn: {SORT_BY[(name, col)]}")
        if dtype == "dateTime":
            out += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
        out.append("")
    out += [f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource =", m_partition(name, spec), "",
            "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def build_semantic_model():
    d = SM / "definition"
    (d / "tables").mkdir(parents=True)
    write_json(SM / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}})
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n\n")
    order = json.dumps(["DataFolder", *TABLES])
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects",
             "\t\treturnErrorValuesAsNull", "",
             f"annotation PBI_QueryOrder = {order}", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    model += [f"ref table {q(t)}" for t in TABLES] + [""]
    (d / "model.tmdl").write_text("\n".join(model))
    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{DEFAULT_FOLDER}" meta [IsParameterQuery = true, Type = "Text", '
        f'IsParameterQueryRequired = true]\n\tlineageTag: {tag("expression", "DataFolder")}\n\n'
        "\tannotation PBI_ResultType = Text\n\n")
    rels = []
    for f_t, f_c, t_t, t_c, both in RELATIONSHIPS:
        rels.append(f"relationship {tag('rel', f_t, f_c, t_t, t_c)}")
        if both:
            rels.append("\tcrossFilteringBehavior: bothDirections")
        rels += [f"\tfromColumn: {q(f_t)}.{q(f_c)}", f"\ttoColumn: {q(t_t)}.{q(t_c)}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rels))
    for name, spec in TABLES.items():
        (d / "tables" / f"{name}.tmdl").write_text(table_tmdl(name, spec))


# ============================================================================
# REPORT (PBIR)
# ============================================================================
INK, INK2, ACCENT = "#0B0B0B", "#52514E", "#2A78D6"


def lit(v) -> dict:
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def color(hex_: str) -> dict:
    return {"solid": {"color": lit(hex_)}}


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field: dict, display: str | None = None) -> dict:
    kind = "Column" if "Column" in field else "Measure"
    ent, prop = field[kind]["Expression"]["SourceRef"]["Entity"], field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


class Page:
    def __init__(self, name: str, display: str):
        self.name, self.display, self.visuals = name, display, []

    def add(self, vid: str, x, y, w, h, visual: dict):
        self.visuals.append({
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/{V_VISUAL}/schema.json",
            "name": vid,
            "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "height": h, "width": w,
                         "tabOrder": len(self.visuals) * 1000},
            "visual": visual,
        })


def container(title: str | None, subtitle: str | None = None) -> dict:
    o = {"background": [{"properties": {"show": lit(True), "color": color("#FFFFFF")}}],
         "border": [{"properties": {"show": lit(True), "color": color("#E5E4DF"), "radius": lit(6)}}],
         "padding": [{"properties": {"top": lit(8), "bottom": lit(8), "left": lit(10), "right": lit(10)}}]}
    if title:
        o["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontColor": color(INK),
                                      "fontSize": lit(12), "bold": lit(True)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    if subtitle:
        o["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle), "fontColor": color(INK2),
                                         "fontSize": lit(9)}}]
    return o


def textbox(text: str, size: int = 20, bold: bool = True, ink: str = INK, sub: str | None = None) -> dict:
    paras = [{"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold" if bold else "normal",
                                                          "fontSize": f"{size}pt", "color": ink}}]}]
    if sub:
        paras.append({"textRuns": [{"value": sub, "textStyle": {"fontSize": "10pt", "color": INK2}}]})
    return {"visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paras}}]},
            "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}],
                                       "border": [{"properties": {"show": lit(False)}}]}}


def card(field: dict, label: str) -> dict:
    return {"visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(field, label)]}}},
            "objects": {"labels": [{"properties": {"fontSize": lit(26), "color": color(INK)}}],
                        "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(10),
                                                           "color": color(INK2)}}]},
            "visualContainerObjects": container(None)}


def slicer(field: dict, title: str) -> dict:
    return {"visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(field)]}}},
            "objects": {"data": [{"properties": {"mode": lit("Dropdown")}}],
                        "header": [{"properties": {"show": lit(True), "text": lit(title), "fontColor": color(INK2)}}]},
            "visualContainerObjects": {"title": [{"properties": {"show": lit(False)}}],
                                       "background": [{"properties": {"show": lit(False)}}]}}


def bar(category: dict, value: dict, title: str, sub: str | None = None, desc: bool = True,
        color_hex: str = ACCENT, value_label: str | None = None) -> dict:
    return {"visualType": "clusteredBarChart",
            "query": {"queryState": {"Category": {"projections": [proj(category)]},
                                     "Y": {"projections": [proj(value, value_label)]}},
                      "sortDefinition": {"sort": [{"field": value, "direction": "Descending" if desc else "Ascending"}],
                                         "isDefaultSort": False}},
            "objects": {"dataPoint": [{"properties": {"fill": color(color_hex)}}],
                        "labels": [{"properties": {"show": lit(True), "color": color(INK2)}}],
                        "valueAxis": [{"properties": {"show": lit(False)}}],
                        "categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}]},
            "visualContainerObjects": container(title, sub)}


def line(category: dict, values: list[tuple[dict, str]], title: str, sub: str | None = None,
         series: dict | None = None) -> dict:
    qs = {"Category": {"projections": [proj(category)]},
          "Y": {"projections": [proj(v, label) for v, label in values]}}
    if series:
        qs["Series"] = {"projections": [proj(series)]}
    return {"visualType": "lineChart",
            "query": {"queryState": qs},
            "objects": {"lineStyles": [{"properties": {"strokeWidth": lit(2)}}],
                        "categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}],
                        "valueAxis": [{"properties": {"showAxisTitle": lit(False)}}],
                        "legend": [{"properties": {"show": lit(len(values) > 1 or series is not None),
                                                   "position": lit("Top")}}]},
            "visualContainerObjects": container(title, sub)}


def table(fields: list[tuple[dict, str]], title: str, sub: str | None = None,
          sort: dict | None = None) -> dict:
    v = {"visualType": "tableEx",
         "query": {"queryState": {"Values": {"projections": [proj(f, label) for f, label in fields]}}},
         "objects": {"columnHeaders": [{"properties": {"bold": lit(True), "fontColor": color(INK)}}],
                     "values": [{"properties": {"wordWrap": lit(True)}}]},
         "visualContainerObjects": container(title, sub)}
    if sort:
        v["query"]["sortDefinition"] = {"sort": [{"field": sort, "direction": "Descending"}], "isDefaultSort": False}
    return v


def matrix(rows: dict, cols: dict, value: dict, title: str, sub: str | None = None) -> dict:
    return {"visualType": "pivotTable",
            "query": {"queryState": {"Rows": {"projections": [proj(rows)]},
                                     "Columns": {"projections": [proj(cols)]},
                                     "Values": {"projections": [proj(value)]}}},
            "objects": {"columnHeaders": [{"properties": {"bold": lit(True)}}],
                        "subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]},
            "visualContainerObjects": container(title, sub)}


F = "fact_reviews"
FOOT = "Synthetic data. Illustrates the method, not a real market."


def build_pages() -> list[Page]:
    # ---------------- Page 1: Overview ----------------
    p1 = Page("overview", "1 · Overview")
    p1.add("ov_title", 16, 8, 1000, 56, textbox(
        "Norvik and Velora trail the market. Service is the main reason.", 20, sub=FOOT))
    for i, (fld, ttl) in enumerate([(col("dim_date", "year"), "Year"), (col(F, "dealer_region"), "Dealer region"),
                                    (col("dim_brand_model", "brand"), "Brand"),
                                    (col(F, "verified_purchase"), "Verified purchase")]):
        p1.add(f"ov_slicer{i}", 16 + i * 312, 70, 300, 56, slicer(fld, ttl))
    for i, (m, lab) in enumerate([("Total Reviews", "Total reviews"), ("Avg Rating", "Average rating"),
                                  ("% Negative", "% rated 1-2 stars"), ("Avg Rating YoY", "Latest year vs year before")]):
        p1.add(f"ov_kpi{i}", 16 + i * 312, 136, 300, 92, card(meas(F, m), lab))
    p1.add("ov_trend", 16, 240, 760, 464, line(
        col("dim_date", "month_start"), [(meas(F, "Avg Rating 3M Rolling"), "Avg rating (3-month rolling)")],
        "Average rating over time", "3-month rolling average smooths noisy months"))
    p1.add("ov_brands", 792, 240, 472, 464, bar(
        col("dim_brand_model", "brand"), meas(F, "Adjusted Rating"),
        "Brand ranking (adjusted for sample size)",
        "Small brands pulled toward the market average; Brixton has only 98 reviews",
        value_label="Adjusted rating"))

    # ---------------- Page 2: Complaint themes ----------------
    p2 = Page("themes", "2 · Complaint Themes")
    p2.add("th_title", 16, 8, 960, 56, textbox(
        "Price is the most common complaint, but service and reliability cost the most rating.", 18, sub=FOOT))
    p2.add("th_slicer_brand", 992, 8, 272, 56, slicer(col("dim_brand_model", "brand"), "Brand"))
    p2.add("th_often", 16, 74, 404, 300, bar(
        col("theme_priority", "theme"), meas("theme_priority", "Complaint Share %"),
        "How OFTEN: % of reviews complaining", "Naive priority: price comes first",
        color_hex="#9A9993", value_label="% of reviews"))
    p2.add("th_cost", 436, 74, 404, 300, bar(
        col("theme_priority", "theme"), meas("theme_priority", "Stars Lost per 100 Reviews"),
        "How much it COSTS: stars lost per 100 reviews", "Impact priority: service and reliability first",
        value_label="Stars lost per 100 reviews"))
    p2.add("th_matrix", 856, 74, 408, 300, matrix(
        col("dim_brand_model", "brand"), col("bridge_review_theme", "theme"), meas(F, "Complaint Rate"),
        "Complaint rate by brand and theme", "% of the brand's reviews complaining about each theme"))
    p2.add("th_trend", 16, 390, 760, 314, line(
        col("dim_date", "year"), [(meas(F, "Complaint Rate"), "Complaint rate")],
        "Complaint rate by theme, per year", "Pick Norvik in the Brand slicer and watch service climb",
        series=col("bridge_review_theme", "theme")))
    p2.add("th_region", 792, 390, 472, 314, bar(
        col(F, "dealer_region"), meas(F, "% Service Mentions Negative"),
        "Service: % of mentions that are negative, by region", "East-region dealers stand out",
        value_label="% negative"))

    # ---------------- Page 3: Drill-down & early warning ----------------
    p3 = Page("drilldown", "3 · Drill-down & Early Warning")
    p3.add("dd_title", 16, 8, 1248, 52, textbox(
        "Read the reviews behind the numbers, and see what changed this quarter.", 18, sub=FOOT))
    for i, (fld, ttl) in enumerate([(col("dim_brand_model", "brand"), "Brand"),
                                    (col("dim_brand_model", "model"), "Model"),
                                    (col(F, "model_year"), "Model year"),
                                    (col("bridge_review_theme", "theme"), "Theme"),
                                    (col("bridge_review_theme", "theme_polarity"), "Theme sentiment"),
                                    (col(F, "sentiment_label"), "Rating band")]):
        p3.add(f"dd_slicer{i}", 16 + i * 208, 66, 200, 56, slicer(fld, ttl))
    p3.add("dd_reviews", 16, 132, 760, 572, table(
        [(col("dim_date", "date"), "Date"), (col("dim_brand_model", "brand"), "Brand"),
         (col("dim_brand_model", "model"), "Model"), (col(F, "model_year"), "MY"),
         (col(F, "rating"), "Stars"), (col(F, "review_text"), "Review")],
        "Reviews", "Try: Velora > Strato > 2022 > reliability > negative", sort=col("dim_date", "date")))
    p3.add("dd_chart", 792, 132, 472, 300, line(
        col("control_chart", "period"),
        [(meas("control_chart", "Velora Reliability Rate"), "Complaint rate"),
         (meas("control_chart", "Velora Reliability Alert Limit"), "Alert limit")],
        "Early warning: Velora reliability complaints", "Crossed the alert limit in 2022 Q4"))
    p3.add("dd_alerts", 792, 444, 472, 260, table(
        [(col("alerts", "brand"), "Brand"), (col("alerts", "metric"), "Theme"), (col("alerts", "period"), "Quarter"),
         (col("alerts", "rate"), "Rate"), (col("alerts", "baseline"), "Baseline"), (col("alerts", "z"), "z")],
        "All alerts (z > 3 vs previous 4 quarters)", "1 real defect, 4 false alarms: an alert means 'go and read'"))
    return [p1, p2, p3]


def build_report():
    d = RP / "definition"
    (d / "pages").mkdir(parents=True)
    write_json(RP / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(d / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    theme = "AutoVoiceTheme.json"
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/{V_REPORT}/schema.json",
        "themeCollection": {"customTheme": {
            "name": theme, "type": "RegisteredResources",
            "reportVersionAtImport": {"visual": V_VISUAL, "page": V_PAGE, "report": V_REPORT}}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": theme, "path": theme, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True}})
    res = RP / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True)
    write_json(res / theme, {
        "name": "AutoVoice",
        "dataColors": ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#6250D6", "#E34948"],
        "foreground": INK, "background": "#FFFFFF", "tableAccent": ACCENT,
        "good": "#0CA30C", "neutral": "#EDA100", "bad": "#E34948",
        "visualStyles": {"page": {"*": {"background": [{"color": {"solid": {"color": "#F4F4F2"}},
                                                        "transparency": 0}]}}}})
    pages = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        pd_ = d / "pages" / p.name
        write_json(pd_ / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/{V_PAGE}/schema.json",
            "name": p.name, "displayName": p.display, "displayOption": "FitToPage", "height": 720, "width": 1280})
        for v in p.visuals:
            write_json(pd_ / "visuals" / v["name"] / "visual.json", v)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def main():
    for p in (SM, RP):
        if p.exists():
            shutil.rmtree(p)
    build_semantic_model()
    build_report()
    write_json(HERE / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    (HERE / ".gitignore").write_text("# Power BI Desktop local caches\n**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    n = sum(1 for _ in HERE.rglob("*") if _.is_file())
    print(f"PBIP written to {HERE} ({n} files)")


if __name__ == "__main__":
    main()
