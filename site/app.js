/* Automotive Customer Sentiment & Business Intelligence: showcase page.
   All numbers come from window.AV (site/data.js, generated from the pipeline outputs). */
(function () {
  "use strict";
  const AV = window.AV;
  const $ = (s) => document.querySelector(s);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
  const fmt = (x, d = 2) => Number(x).toFixed(d);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const NS = "http://www.w3.org/2000/svg";
  const P = Object.fromEntries(AV.priority.map((p) => [p.theme, p]));

  // ---------- links ----------
  const repo = AV.repo, blob = AV.blob;
  ["#nav-repo", "#hero-repo"].forEach((s) => ($(s).href = repo));
  $("#hero-report").href = `${blob}/docs/insights_report.md`;

  // ---------- tooltip ----------
  const tip = $("#tip");
  const showTip = (html, x, y) => { tip.innerHTML = html; tip.style.left = x + "px"; tip.style.top = y + "px"; tip.classList.add("show"); };
  const hideTip = () => tip.classList.remove("show");

  // ---------- hero stats ----------
  const m = AV.meta;
  $("#stats").innerHTML = [
    [m.rawRows.toLocaleString() + " → " + m.cleanRows.toLocaleString(), "messy reviews in → clean reviews out"],
    [m.queries, "SQL queries: CTEs, window functions"],
    [`${m.checksPassed} / ${m.checksTotal}`, "planted problems recovered blind"],
    ["2022 Q4", "defect flagged; ratings never moved"],
  ].map(([v, l]) => `<div><dd>${v}</dd><dt>${l}</dt></div>`).join("");

  // ---------- 01: race chart ----------
  const colorFor = (t) => (t === "price" ? css("--price") : t === "service" || t === "reliability" ? css("--accent") : css("--neutral-bar"));
  const modes = {
    often: {
      value: (p) => p.often, label: (p) => p.often.toFixed(1) + "%",
      caption: "% of all reviews that contain a complaint about the theme",
      insight: `By volume, <b>price</b> is the #1 problem: ${P.price.often.toFixed(1)}% of reviews complain about it. A "most frequent complaint" report would put it first.`,
    },
    cost: {
      value: (p) => p.cost, label: (p) => p.cost.toFixed(1),
      caption: "Stars lost per 100 reviews = how often × stars lost per complaint (regression)",
      insight: `By impact, <b>service</b> and <b>reliability</b> lead. A service complaint costs ${fmt(P.service.perComplaint)} stars, a price complaint only ${fmt(P.price.perComplaint)}: about ${Math.round(P.service.perComplaint / P.price.perComplaint)}× less. Price drops from #1 to #${P.price.impactRank}.`,
    },
  };
  const race = $("#priority"), ROW = 48;
  race.style.height = AV.priority.length * ROW + "px";
  const rowEls = {};
  AV.priority.forEach((p) => {
    const r = document.createElement("div");
    r.className = "race-row";
    r.innerHTML = `<div class="race-label">${p.theme}<small></small></div>
      <div class="race-track"><div class="race-bar" style="background:${colorFor(p.theme)}"></div></div>
      <div class="race-val"></div>`;
    race.appendChild(r);
    rowEls[p.theme] = r;
  });
  function renderRace(mode) {
    const md = modes[mode];
    const sorted = [...AV.priority].sort((a, b) => md.value(b) - md.value(a));
    const max = md.value(sorted[0]);
    sorted.forEach((p, i) => {
      const r = rowEls[p.theme];
      r.style.top = i * ROW + "px";
      r.querySelector(".race-bar").style.width = (md.value(p) / max) * 100 + "%";
      r.querySelector(".race-val").textContent = md.label(p);
      r.querySelector("small").textContent = mode === "cost" ? `${fmt(p.perComplaint)} per complaint` : `#${p.naiveRank} by volume`;
    });
    $("#priority-caption").textContent = md.caption;
    $("#priority-insight").innerHTML = md.insight;
    document.querySelectorAll(".toggle button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  }
  document.querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => renderRace(b.dataset.mode)));
  renderRace("often");
  $("#priority-table").innerHTML = table(
    ["Theme", "% of reviews complaining", "Stars lost per complaint", "Stars lost per 100 reviews", "Rank by volume", "Rank by impact"],
    [...AV.priority].sort((a, b) => a.impactRank - b.impactRank).map((p) =>
      [p.theme, p.often.toFixed(1) + "%", fmt(p.perComplaint), p.cost.toFixed(1), "#" + p.naiveRank, "#" + p.impactRank]),
    [false, true, true, true, true, true]);

  // ---------- generic svg helpers ----------
  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, s, cls, anchor = "start", extra = {}) {
    const t = el("text", { x, y, class: cls || "", "text-anchor": anchor, ...extra }, parent);
    t.textContent = s;
    return t;
  }
  function niceMax(v, step) { return Math.ceil(v / step) * step; }

  /* Line chart: x = category labels, series = [{name, values, color, dash, width, label}] */
  function lineChart(host, o) {
    host.innerHTML = "";
    const W = Math.max(300, host.clientWidth), H = o.height || 250;
    const mg = { l: 40, r: o.right ?? 82, t: 14, b: 30 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria }, host);
    const iw = W - mg.l - mg.r, ih = H - mg.t - mg.b;
    const n = o.x.length;
    const xs = (i) => mg.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
    const yMax = o.yMax, ys = (v) => mg.t + ih - (v / yMax) * ih;
    const g = el("g", { class: "grid" }, svg);
    for (let v = 0; v <= yMax + 1e-9; v += o.yStep) {
      el("line", { x1: mg.l, x2: mg.l + iw, y1: ys(v), y2: ys(v) }, g);
      text(svg, mg.l - 8, ys(v) + 4, o.yFmt(v), "", "end");
    }
    o.x.forEach((lab, i) => { if (i % (o.xEvery || 1) === 0 || i === n - 1) text(svg, xs(i), H - 8, lab, "", "middle"); });
    if (o.shade) {
      const i = o.x.indexOf(o.shade.at);
      if (i >= 0) {
        el("rect", { x: xs(i) - 3, y: mg.t, width: 6, height: ih, fill: css("--grid") }, svg);
        text(svg, xs(i) + 7, mg.t + 10, o.shade.label, "");
      }
    }
    o.series.forEach((s) => {
      let d = "", pen = false;
      s.values.forEach((v, i) => {
        if (v == null) { pen = false; return; }
        d += (pen ? "L" : "M") + xs(i).toFixed(1) + "," + ys(v).toFixed(1);
        pen = true;
      });
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2.5, "stroke-dasharray": s.dash || "",
        "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      if (s.dots) s.values.forEach((v, i) => v != null && el("circle", { cx: xs(i), cy: ys(v), r: 3.2, fill: s.color }, svg));
      const last = s.values.map((v, i) => [v, i]).filter(([v]) => v != null).pop();
      if (last && s.label) text(svg, xs(last[1]) + 8, ys(last[0]) + 4, s.label(last[0]), s.strong ? "lab-strong" : "lab", "start", { style: s.strong ? `fill:${s.color}` : "" });
    });
    (o.marks || []).forEach((mk) => {
      const i = o.x.indexOf(mk.at);
      if (i < 0) return;
      el("circle", { cx: xs(i), cy: ys(mk.value), r: 7, fill: css("--alert"), stroke: css("--card"), "stroke-width": 2.5 }, svg);
      const right = xs(i) < mg.l + iw * 0.6;
      text(svg, xs(i) + (right ? 12 : -12), ys(mk.value) - 10, mk.text, "alert-lab", right ? "start" : "end");
    });
    // hover
    const hl = el("line", { class: "hover-line", y1: mg.t, y2: mg.t + ih, x1: -10, x2: -10 }, svg);
    const hit = el("rect", { x: mg.l - 10, y: mg.t, width: iw + 20, height: ih, fill: "transparent" }, svg);
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * (W / r.width);
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - mg.l) / iw) * (n - 1))));
      hl.setAttribute("x1", xs(i)); hl.setAttribute("x2", xs(i)); hl.classList.add("on");
      const rows = o.series.map((s) => s.values[i] == null ? "" :
        `<span style="color:${s.color}">●</span> ${s.name}: <b>${o.tipFmt(s.values[i])}</b>`).filter(Boolean).join("<br>");
      const top = Math.min(...o.series.map((s) => (s.values[i] == null ? Infinity : ys(s.values[i]))));
      showTip(`<b>${o.x[i]}</b>${o.tipExtra ? o.tipExtra(i) : ""}<br>${rows}`, r.left + (xs(i) * r.width) / W, r.top + (top * r.height) / H);
    };
    hit.addEventListener("mousemove", move);
    hit.addEventListener("touchstart", move, { passive: true });
    hit.addEventListener("mouseleave", () => { hl.classList.remove("on"); hideTip(); });
  }

  // ---------- 02: early warning ----------
  const V = AV.velora, periods = V.map((d) => d.period);
  const alertQ = V.find((d) => d.rel.alert);
  $("#warning-lede").innerHTML = `Every quarter, each brand × theme complaint rate is compared with the previous four quarters
    (two-proportion z-test, alert above z = 3). In <b>${alertQ.period}</b>, Velora's reliability complaints jumped from
    ${pct(alertQ.rel.baseline, 0)} to ${pct(alertQ.rel.rate, 0)}. In the same quarter, its share of 1-2 star reviews moved
    from ${pct(alertQ.low.baseline, 0)} to ${pct(alertQ.low.rate, 0)}, well inside normal variation.`;
  const wc = AV.worstCohort;
  $("#warning-callouts").innerHTML = [
    [`${pct(alertQ.rel.baseline, 0)} → ${pct(alertQ.rel.rate, 0)}`, `Velora reliability complaints, ${alertQ.period}: alert fired`],
    [`${wc.pct_negative}%`, `of ${wc.brand} ${wc.model} MY${wc.model_year} reviews are 1-2 stars: the worst cohort in the market (SQL)`],
    [`${m.realAlerts} real · ${m.alerts - m.realAlerts} false`, `alerts across ${m.tests} tests. Reported, not hidden: an alert means "go and read 20 reviews"`],
  ].map(([b, s]) => `<div class="callout"><b>${b}</b><span>${s}</span></div>`).join("");

  function drawWarning() {
    const common = { x: periods, xEvery: 4, yFmt: (v) => Math.round(v * 100) + "%", tipFmt: (v) => pct(v), height: 250,
      shade: { at: "2022Q3", label: "defect begins" } };
    lineChart($("#chart-rel"), { ...common, aria: "Velora reliability complaint rate by quarter with alert limit",
      yMax: 0.3, yStep: 0.1, tipExtra: (i) => ` · ${V[i].rel.n} reviews`,
      series: [
        { name: "Complaint rate", values: V.map((d) => d.rel.rate), color: css("--accent"), dots: true, label: () => "rate", strong: true },
        { name: "Alert limit", values: V.map((d) => d.rel.limit), color: css("--muted"), dash: "5 4", width: 1.6, label: () => "alert limit" },
      ],
      marks: [{ at: alertQ.period, value: alertQ.rel.rate, text: `ALERT ${alertQ.period}` }] });
    lineChart($("#chart-low"), { ...common, aria: "Velora share of 1-2 star reviews by quarter with alert limit",
      yMax: 0.5, yStep: 0.1, tipExtra: (i) => ` · ${V[i].low.n} reviews`,
      series: [
        { name: "1-2 star share", values: V.map((d) => d.low.rate), color: css("--ink-2"), dots: true, label: () => "no alert", strong: true },
        { name: "Alert limit", values: V.map((d) => d.low.limit), color: css("--muted"), dash: "5 4", width: 1.6, label: () => "alert limit" },
      ] });
  }

  // ---------- 03: brands + Norvik ----------
  function drawBrands() {
    const host = $("#chart-brands"); host.innerHTML = "";
    const B = [...AV.brands].sort((a, b) => b.adjusted - a.adjusted);
    const W = Math.max(300, host.clientWidth), rowH = 30, mg = { l: 74, r: 64, t: 8, b: 30 };
    const H = mg.t + B.length * rowH + mg.b;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Brand average ratings with 95% confidence intervals" }, host);
    const lo = 3.2, hi = 4.4, iw = W - mg.l - mg.r, xs = (v) => mg.l + ((v - lo) / (hi - lo)) * iw;
    const g = el("g", { class: "grid" }, svg);
    for (let v = lo; v <= hi + 1e-9; v += 0.2) {
      el("line", { x1: xs(v), x2: xs(v), y1: mg.t, y2: H - mg.b }, g);
      text(svg, xs(v), H - 10, v.toFixed(1), "", "middle");
    }
    B.forEach((b, i) => {
      const y = mg.t + i * rowH + rowH / 2;
      const weak = b.brand === "Norvik" || b.brand === "Velora";
      text(svg, mg.l - 10, y + 4, b.brand, weak ? "lab-strong" : "lab", "end");
      el("line", { x1: xs(b.lo), x2: xs(b.hi), y1: y, y2: y, stroke: css("--neutral-bar"), "stroke-width": 5, "stroke-linecap": "round" }, svg);
      el("circle", { cx: xs(b.avg), cy: y, r: 3, fill: css("--ink-2") }, svg);
      el("rect", { x: xs(b.adjusted) - 5, y: y - 5, width: 10, height: 10, transform: `rotate(45 ${xs(b.adjusted)} ${y})`,
        fill: weak ? css("--alert") : css("--accent") }, svg);
      text(svg, xs(b.hi) + 8, y + 4, "n=" + b.reviews.toLocaleString(), "");
      const hit = el("rect", { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", (ev) => showTip(`<b>${b.brand}</b> · ${b.reviews.toLocaleString()} reviews<br>Average ${fmt(b.avg)} · adjusted <b>${fmt(b.adjusted)}</b><br>95% CI ${fmt(b.lo)} to ${fmt(b.hi)}`, ev.clientX, ev.clientY));
      hit.addEventListener("mouseleave", hideTip);
    });
  }
  function drawNorvik() {
    const N = AV.norvik;
    lineChart($("#chart-norvik"), { x: N.map((d) => String(d.year)), yMax: 0.2, yStep: 0.05, height: 270, right: 92,
      yFmt: (v) => Math.round(v * 100) + "%", tipFmt: (v) => pct(v), aria: "Share of reviews with a service complaint, Norvik vs others",
      series: [
        { name: "All other brands", values: N.map((d) => d.others), color: css("--neutral-bar"), dots: true, label: (v) => "Others " + pct(v, 0) },
        { name: "Norvik", values: N.map((d) => d.norvik), color: css("--accent"), dots: true, width: 3, strong: true, label: (v) => "Norvik " + pct(v, 0) },
      ] });
  }

  // ---------- 04: recommendations ----------
  const S = Object.fromEntries(AV.scenarios.map((s) => [s.scenario, s]));
  const east = AV.region[0], others = AV.region.slice(1).reduce((a, r) => a + Number(r.pct_negative), 0) / (AV.region.length - 1);
  const nv = AV.norvik[0], nv2 = AV.norvik[AV.norvik.length - 1];
  const recs = [
    ["Make dealer service the #1 improvement programme", `Service complaints cost ${P.service.cost.toFixed(1)} stars per 100 reviews, the most of any theme. Start with Norvik (service complaints ${pct(nv.norvik, 0)} → ${pct(nv2.norvik, 0)}, ${nv.year}–${nv2.year}) and ${east.dealer_region}-region dealers (${east.pct_negative}% of service mentions negative vs ${others.toFixed(0)}% elsewhere).`, "High confidence", true],
    [`Investigate ${wc.brand} ${wc.model}, model years 2022-23`, `Worst cohort in the market: ${wc.pct_negative}% of MY${wc.model_year} reviews are 1-2 stars, average ${wc.avg_rating}. The complaints point to the transmission.`, "High confidence", true],
    ["Monitor complaint themes every quarter, not just ratings", `The z-test flagged the defect in ${alertQ.period}; the 1-2 star share never triggered. ${m.alerts - m.realAlerts} of ${m.alerts} alerts were false alarms, so an alert should start a review, not a recall.`, "Medium confidence", false],
    ["Don't change prices because of reviews", `Price is the most common complaint (${P.price.often.toFixed(1)}% of reviews) but costs only ${fmt(P.price.perComplaint)} stars each. Reviews can't measure lost sales, so test pricing elsewhere.`, "High for ratings", true],
  ];
  $("#recs").innerHTML = recs.map(([h, p, c, hiConf]) => `<li><h3>${h}</h3><p>${p}</p><span class="conf ${hiConf ? "high" : ""}">${c}</span></li>`).join("");
  $("#scenarios").innerHTML = table(["Scenario", "Complaints removed", "Rating before", "Rating after"],
    AV.scenarios.map((s) => [s.scenario, s.removed, fmt(s.before, s.before > 3.6 ? 3 : 2), `<b>${fmt(s.after, s.before > 3.6 ? 3 : 2)}</b>`]),
    [false, true, true, true], true);

  // ---------- 05: dashboard ----------
  const haveShots = AV.shots.some((s) => s.file);
  const shots = $("#shots");
  if (!haveShots) shots.classList.add("placeholders");
  shots.innerHTML = AV.shots.map((s) => s.file
    ? `<figure class="shot"><a href="${s.file}"><img src="${s.file}" alt="Power BI dashboard page ${esc(s.title)}" loading="lazy"></a><figcaption><b>${s.title}.</b> ${s.caption}</figcaption></figure>`
    : `<figure class="shot"><div class="ph"><div><strong>${s.title}</strong>${s.caption}<br><br><em>Screenshot coming soon</em></div></div></figure>`).join("");

  // ---------- 06: validation ----------
  $("#score").innerHTML = `<b>${m.checksPassed} / ${m.checksTotal}</b><span>planted signals recovered by an analysis that never saw the answers</span>`;
  $("#checks").innerHTML = table(["Check", "What was planted", "What the pipeline found", ""],
    AV.checks.map((c) => [c.signal.replace(/^(P\d+[a-z]?|Extra)\.\s*/, ""), c.planted, c.found, `<span class="pass">${c.result}</span>`]),
    [false, false, false, true], false, [false, true, false, false]);
  $("#tagger").innerHTML = table(["Theme", "Precision", "Recall"],
    AV.tagger.map((t) => [t.theme, meter(t.precision), meter(t.recall)]), [false, false, false]);
  $("#models").innerHTML = table(["Model", "Accuracy", "Macro-F1"],
    AV.models.map((r) => [r.model, pct(r.accuracy), fmt(r.f1)]), [false, true, true], false, null, 2);

  // ---------- 07: method ----------
  const steps = [
    ["Generate", "12k messy reviews, 6 problems planted, answers sealed"],
    ["Clean", "3 date formats, brand typos, duplicates, all logged"],
    ["SQL", `SQLite star schema, ${m.queries} queries: CTEs, LAG, RANK, rolling windows`],
    ["Themes", "Keyword tagging per sentence + VADER aspect sentiment"],
    ["Sentiment", "VADER vs TF-IDF + logistic regression, error analysis"],
    ["Drivers", "OLS regression, shrinkage ranking, what-if scenarios"],
    ["Early warning", "Quarterly two-proportion z-test per brand × theme"],
    ["Power BI", "Star schema, 19 DAX measures, 3-page report as PBIP"],
  ];
  $("#pipeline").innerHTML = steps.map(([b, s]) => `<li><b>${b}</b><span>${s}</span></li>`).join("");
  $("#cleaning").innerHTML = table(["Step", "Rows", "Change"],
    AV.cleaning.filter((c) => c.before !== c.after || /model year/i.test(c.step)).map((c) =>
      [c.step, c.after.toLocaleString(), c.after - c.before === 0 ? "nulled, kept" : (c.after - c.before).toLocaleString()]),
    [false, true, true]);
  const links = [
    ["Code repository", repo], ["Insights report", `${blob}/docs/insights_report.md`], ["SQL queries", `${blob}/sql/queries.sql`],
    ["Error analysis", `${blob}/docs/error_analysis.md`], ["Validation", `${blob}/docs/pipeline_validation.md`],
    ["Power BI project", `${repo}/tree/${blob.split("/").pop()}/powerbi`], ["Cleaning log", `${blob}/docs/cleaning_log.md`],
  ];
  $("#links").innerHTML = links.map(([t, h]) => `<a href="${h}">${t} →</a>`).join("");
  $("#footer").innerHTML = `<span>Automotive Customer Sentiment &amp; Business Intelligence${AV.author ? " · " + esc(AV.author) : ""}</span>
    <span><a href="${repo}">GitHub</a>${AV.linkedin ? ` · <a href="${AV.linkedin}">LinkedIn</a>` : ""} · Synthetic data, real method</span>`;

  // ---------- helpers ----------
  function meter(v) { return `<div style="display:flex;align-items:center;gap:10px"><div class="meter" style="flex:1"><i style="width:${v * 100}%"></i></div><span style="font-variant-numeric:tabular-nums;width:3.2em;text-align:right">${pct(v, 0)}</span></div>`; }
  function table(head, body, numeric, highlightFirst, hideSm, highlightIndex) {
    const th = head.map((h, i) => `<th class="${numeric[i] ? "num" : ""} ${hideSm && hideSm[i] ? "hide-sm" : ""}">${h}</th>`).join("");
    const tr = body.map((r, ri) => `<tr class="${highlightIndex === ri ? "highlight-row" : ""}">${r.map((c, i) =>
      `<td class="${numeric[i] ? "num" : ""} ${hideSm && hideSm[i] ? "hide-sm" : ""}">${c}</td>`).join("")}</tr>`).join("");
    return `<div style="overflow-x:auto"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
  }

  // ---------- draw + redraw on resize / theme change ----------
  function drawAll() { drawWarning(); drawBrands(); drawNorvik(); Object.values(rowEls).forEach((r) => {
    r.querySelector(".race-bar").style.background = colorFor(r.querySelector(".race-label").firstChild.textContent.trim()); }); }
  drawAll();
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(drawAll, 150); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawAll);
})();
