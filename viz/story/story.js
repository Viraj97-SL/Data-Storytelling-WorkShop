// Scrollytelling engine — one persistent <svg>, D3 v7 transitions between
// states, Scrollama for scroll-triggering. No aggregation happens here:
// every number comes straight from data/story.json (see build_story_data.py).

(function () {
  "use strict";

  const WIDTH = 960;
  const HEIGHT = 600;
  const T = 650; // shared transition duration (ms)

  const COLOR = {
    ink: "#f2f1ec",
    inkMuted: "#8c8a83",
    inkFaint: "#56544e",
    line: "#2c2c2a",
    blue: "#3987e5",
    red: "#e66767",
    gold: "#c98500",
    aqua: "#199e70",
    tierBronze: "#5598e7", // light->dark steps of the same ordinal blue ramp
    tierSilver: "#2a78d6", // used everywhere else in this project for
    tierGold: "#104281",   // gold/silver/bronze — no arbitrary new hues.
  };

  const ACCENT_MAP = { red: COLOR.red, blue: COLOR.blue, gold: COLOR.gold, aqua: COLOR.aqua, none: COLOR.inkFaint };

  // ── Data binding: fill every [data-bind] element from story.json, zero aggregation ──

  function resolvePath(obj, path) {
    return path.split(".").reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
  }

  function formatValue(value, format) {
    if (value == null) return "";
    if (format === "comma" && typeof value === "number") return value.toLocaleString("en-GB");
    if (format === "pct" && typeof value === "number") return `${value}%`;
    return String(value);
  }

  function bindText(story) {
    document.querySelectorAll("[data-bind]").forEach((el) => {
      const path = el.getAttribute("data-bind");
      const value = resolvePath(story, path);
      el.textContent = formatValue(value, el.getAttribute("data-format"));
    });

    const closeList = document.getElementById("close-list");
    closeList.innerHTML = "";
    story.close.points.forEach((point) => {
      const li = document.createElement("li");
      li.textContent = point;
      closeList.appendChild(li);
    });
  }

  // ── Chart engine — every render function shares one <svg>, fades the
  //    others out, and updates/enters its own group with a transition ──

  // Simple isotype-style person glyph (head + shoulders), used by the
  // pictogram grids — not plain circles, per the brief's "grid of small
  // human icons" spec.
  const PERSON_ICON_PATH = "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z";

  function buildChart(svg) {
    svg.append("defs").append("symbol")
      .attr("id", "person-icon")
      .attr("viewBox", "0 0 24 24")
      .append("path")
      .attr("d", PERSON_ICON_PATH);

    const root = svg.append("g").attr("class", "chart-root");

    const groups = {
      hook: root.append("g").attr("class", "layer layer-hook"),
      scale: root.append("g").attr("class", "layer layer-scale"),
      funnel: root.append("g").attr("class", "layer layer-funnel"),
      visa: root.append("g").attr("class", "layer layer-visa"),
      skills: root.append("g").attr("class", "layer layer-skills"),
      salary: root.append("g").attr("class", "layer layer-salary"),
    };

    function focus(activeKey, activeOpacity) {
      Object.entries(groups).forEach(([key, g]) => {
        const target = key === activeKey ? activeOpacity : 0;
        g.transition().duration(T).style("opacity", target);
      });
    }

    // Reusable pictogram grid — used dimmed behind the hook, then in full
    // at the visa step. 10x10 grid of small person-icon glyphs (isotype
    // style, per the brief), not plain circles. The first `highlighted` of
    // them (reading order) get the highlight color.
    function renderPictogram(g, total, highlighted, opts) {
      const cols = 10;
      const cellSize = opts.cellSize;
      const iconSize = opts.radius * 2; // reuse the old "radius" knob as half the icon's footprint
      const offsetX = opts.x;
      const offsetY = opts.y;
      const data = d3.range(total).map((i) => ({
        i,
        x: offsetX + (i % cols) * cellSize,
        y: offsetY + Math.floor(i / cols) * cellSize,
      }));

      g.selectAll("use.pictogram-cell")
        .data(data, (d) => d.i)
        .join(
          (enter) => enter.append("use")
            .attr("class", "pictogram-cell")
            .attr("href", "#person-icon")
            .attr("x", (d) => d.x - iconSize / 2)
            .attr("y", (d) => d.y - iconSize / 2)
            .attr("width", 0)
            .attr("height", 0)
            .attr("fill", (d) => (d.i < highlighted ? opts.highlightColor : opts.baseColor))
            .attr("fill-opacity", opts.baseOpacity)
            .call((enter) => enter.transition().duration(T).delay((d) => d.i * 4)
              .attr("width", iconSize).attr("height", iconSize)
              .attr("x", (d) => d.x - iconSize / 2).attr("y", (d) => d.y - iconSize / 2)),
          (update) => update.transition().duration(T)
            .attr("fill", (d) => (d.i < highlighted ? opts.highlightColor : opts.baseColor))
            .attr("width", iconSize).attr("height", iconSize)
            .attr("x", (d) => d.x - iconSize / 2).attr("y", (d) => d.y - iconSize / 2),
        );
    }

    // ── Step 1: Hook — dimmed pictogram preview behind the full-bleed title ──
    function showHook(story) {
      focus("hook", 0.22);
      renderPictogram(groups.hook, story.visa.pictogram_n, story.visa.pictogram_highlighted, {
        cellSize: 32, radius: 8, x: WIDTH / 2 - 160, y: HEIGHT / 2 - 160,
        highlightColor: COLOR.red, baseColor: COLOR.inkFaint, baseOpacity: 1,
      });
    }

    // ── Step 2: Scale — one big animated number ──
    function showScale(story) {
      focus("scale", 1);
      const g = groups.scale;
      const value = story.scale.total_scraped;

      let numberText = g.selectAll("text.big-number").data([value]);
      numberText = numberText.join(
        (enter) => enter.append("text")
          .attr("class", "big-number")
          .attr("x", WIDTH / 2).attr("y", HEIGHT / 2 - 10)
          .attr("text-anchor", "middle")
          .attr("font-size", 0)
          .attr("font-weight", 700)
          .attr("fill", COLOR.blue)
          .text("0"),
        (update) => update,
      );

      numberText.transition().duration(T).attr("font-size", 120)
        .tween("text", function () {
          const node = this;
          const i = d3.interpolateNumber(0, value);
          return (t) => { node.textContent = Math.round(i(t)).toLocaleString("en-GB"); };
        });

      const sub = g.selectAll("text.sub-label").data([story]);
      sub.join(
        (enter) => enter.append("text")
          .attr("class", "sub-label")
          .attr("x", WIDTH / 2).attr("y", HEIGHT / 2 + 60)
          .attr("text-anchor", "middle")
          .attr("font-size", 18)
          .attr("fill", COLOR.inkMuted)
          .attr("opacity", 0)
          .text((d) => `postings · ${d.scale.weeks} weeks · ${d.scale.source_count} sources`)
          .call((enter) => enter.transition().duration(T).delay(200).attr("opacity", 1)),
        (update) => update.text((d) => `postings · ${d.scale.weeks} weeks · ${d.scale.source_count} sources`),
      );
    }

    // ── Step 3: Funnel — 2 real stages + tier split ──
    function showFunnel(story) {
      focus("funnel", 1);
      const g = groups.funnel;
      const stages = story.funnel.stages;
      const tiers = story.funnel.tiers;
      const tierColor = { bronze: COLOR.tierBronze, silver: COLOR.tierSilver, gold: COLOR.tierGold };

      const barMaxWidth = 560;
      const stageScale = d3.scaleLinear().domain([0, stages[0].value]).range([0, barMaxWidth]);
      const tierMaxScale = d3.scaleLinear().domain([0, d3.max(tiers, (t) => t.count)]).range([0, 320]);

      const stageBars = g.selectAll("g.stage-bar").data(stages, (d) => d.label);
      const stageEnter = stageBars.join(
        (enter) => {
          const eg = enter.append("g").attr("class", "stage-bar")
            .attr("transform", (d, i) => `translate(120, ${140 + i * 90})`);
          eg.append("rect").attr("height", 46).attr("rx", 4).attr("fill", COLOR.blue).attr("width", 0);
          eg.append("text").attr("class", "stage-label").attr("y", -10).attr("fill", COLOR.inkMuted).attr("font-size", 14);
          eg.append("text").attr("class", "stage-value").attr("x", 12).attr("y", 30).attr("fill", COLOR.ink).attr("font-size", 20).attr("font-weight", 700);
          return eg;
        },
        (update) => update.attr("transform", (d, i) => `translate(120, ${140 + i * 90})`),
      );
      stageEnter.select("text.stage-label").text((d) => d.label);
      stageEnter.select("text.stage-value").text((d) => d.value.toLocaleString("en-GB"));
      stageEnter.select("rect").transition().duration(T).attr("width", (d) => stageScale(d.value));

      const tierBars = g.selectAll("g.tier-bar").data(tiers, (d) => d.tier);
      const tierEnter = tierBars.join(
        (enter) => {
          const eg = enter.append("g").attr("class", "tier-bar")
            .attr("transform", (d, i) => `translate(120, ${360 + i * 46})`);
          eg.append("rect").attr("height", 30).attr("rx", 3).attr("width", 0);
          eg.append("text").attr("class", "tier-label").attr("x", -10).attr("y", 20).attr("text-anchor", "end").attr("fill", COLOR.inkMuted).attr("font-size", 13);
          eg.append("text").attr("class", "tier-value").attr("y", 20).attr("fill", COLOR.ink).attr("font-size", 13).attr("font-weight", 600);
          return eg;
        },
        (update) => update.attr("transform", (d, i) => `translate(120, ${360 + i * 46})`),
      );
      tierEnter.select("rect").attr("fill", (d) => tierColor[d.tier])
        .transition().duration(T).delay(200).attr("width", (d) => tierMaxScale(d.count));
      tierEnter.select("text.tier-label").text((d) => d.tier[0].toUpperCase() + d.tier.slice(1));
      tierEnter.select("text.tier-value").attr("x", (d) => tierMaxScale(d.count) + 10).text((d) => `${d.count} (${d.pct}%)`);
    }

    // ── Step 4: Visa pictogram, in full — the emotional core ──
    function showVisa(story) {
      focus("visa", 1);
      renderPictogram(groups.visa, story.visa.pictogram_n, story.visa.pictogram_highlighted, {
        cellSize: 34, radius: 12, x: WIDTH / 2 - 170, y: 70,
        highlightColor: COLOR.red, baseColor: COLOR.inkFaint, baseOpacity: 0.8,
      });

      const legend = groups.visa.selectAll("text.pictogram-legend").data([story.visa]);
      legend.join(
        (enter) => enter.append("text")
          .attr("class", "pictogram-legend")
          .attr("x", WIDTH / 2).attr("y", 560)
          .attr("text-anchor", "middle")
          .attr("fill", COLOR.inkMuted)
          .attr("font-size", 15)
          .attr("opacity", 0)
          .text((d) => `Each dot = ~${Math.round(d.employers_checked / d.pictogram_n)} employers checked. Red = actually licensed.`)
          .call((enter) => enter.transition().duration(T).delay(600).attr("opacity", 1)),
      );
    }

    // ── Step 5: Skills over time — connected lines, one highlighted ──
    function showSkills(story) {
      focus("skills", 1);
      const g = groups.skills;
      const weeks = story.skills.weeks.map((w) => new Date(w));
      const series = story.skills.series;
      const highlightSkill = "Python" in series ? "Python" : Object.keys(series)[0];

      const margin = { top: 60, right: 40, bottom: 50, left: 50 };
      const plotW = WIDTH - margin.left - margin.right;
      const plotH = HEIGHT - margin.top - margin.bottom;

      const x = d3.scaleTime().domain(d3.extent(weeks)).range([0, plotW]);
      const allValues = Object.values(series).flat();
      const y = d3.scaleLinear().domain([0, d3.max(allValues)]).nice().range([plotH, 0]);
      const line = d3.line().x((d, i) => x(weeks[i])).y((d) => y(d)).curve(d3.curveMonotoneX);

      let plot = g.select("g.skills-plot");
      if (plot.empty()) {
        plot = g.append("g").attr("class", "skills-plot").attr("transform", `translate(${margin.left},${margin.top})`);
        plot.append("g").attr("class", "y-axis");
        plot.append("g").attr("class", "x-axis").attr("transform", `translate(0,${plotH})`);
      }

      plot.select("g.y-axis")
        .call(d3.axisLeft(y).ticks(4))
        .call((g2) => g2.selectAll("text").attr("fill", COLOR.inkMuted).attr("font-size", 11))
        .call((g2) => g2.selectAll("path,line").attr("stroke", COLOR.line));
      plot.select("g.x-axis")
        .call(d3.axisBottom(x).ticks(6))
        .call((g2) => g2.selectAll("text").attr("fill", COLOR.inkMuted).attr("font-size", 11))
        .call((g2) => g2.selectAll("path,line").attr("stroke", COLOR.line));

      const lineData = Object.entries(series).map(([skill, values]) => ({ skill, values }));
      const paths = plot.selectAll("path.skill-line").data(lineData, (d) => d.skill);
      paths.join(
        (enter) => enter.append("path")
          .attr("class", "skill-line")
          .attr("fill", "none")
          .attr("stroke", (d) => (d.skill === highlightSkill ? COLOR.aqua : COLOR.inkFaint))
          .attr("stroke-width", (d) => (d.skill === highlightSkill ? 3 : 1.5))
          .attr("opacity", 0)
          .attr("d", (d) => line(d.values))
          .call((enter) => enter.transition().duration(T).attr("opacity", 1)),
        (update) => update.transition().duration(T)
          .attr("stroke", (d) => (d.skill === highlightSkill ? COLOR.aqua : COLOR.inkFaint))
          .attr("d", (d) => line(d.values)),
      );

      const label = plot.selectAll("text.skill-highlight-label").data([highlightSkill]);
      label.join(
        (enter) => enter.append("text")
          .attr("class", "skill-highlight-label")
          .attr("x", plotW).attr("y", y(lineData.find((d) => d.skill === highlightSkill).values.at(-1)) - 8)
          .attr("text-anchor", "end")
          .attr("fill", COLOR.aqua)
          .attr("font-size", 13)
          .attr("font-weight", 700)
          .text((d) => d),
      );
    }

    // ── Step 6: Salary vs. score scatter, diverging color on score ──
    function showSalary(story) {
      focus("salary", 1);
      const g = groups.salary;
      const points = story.salary_score.points;
      const midpoint = story.salary_score.silver_min;

      const margin = { top: 50, right: 40, bottom: 50, left: 70 };
      const plotW = WIDTH - margin.left - margin.right;
      const plotH = HEIGHT - margin.top - margin.bottom;

      const x = d3.scaleLinear().domain([0, 100]).range([0, plotW]);
      const y = d3.scaleLinear().domain([0, d3.max(points, (p) => p.salary)]).nice().range([plotH, 0]);
      const color = d3.scaleDiverging(d3.interpolateRgbBasis([COLOR.red, COLOR.inkFaint, COLOR.blue]))
        .domain([0, midpoint, 100]);

      let plot = g.select("g.salary-plot");
      if (plot.empty()) {
        plot = g.append("g").attr("class", "salary-plot").attr("transform", `translate(${margin.left},${margin.top})`);
        plot.append("g").attr("class", "y-axis");
        plot.append("g").attr("class", "x-axis").attr("transform", `translate(0,${plotH})`);
      }

      plot.select("g.y-axis")
        .call(d3.axisLeft(y).ticks(5).tickFormat((d) => `£${d / 1000}k`))
        .call((g2) => g2.selectAll("text").attr("fill", COLOR.inkMuted).attr("font-size", 11))
        .call((g2) => g2.selectAll("path,line").attr("stroke", COLOR.line));
      plot.select("g.x-axis")
        .call(d3.axisBottom(x).ticks(5))
        .call((g2) => g2.selectAll("text").attr("fill", COLOR.inkMuted).attr("font-size", 11))
        .call((g2) => g2.selectAll("path,line").attr("stroke", COLOR.line));

      const dots = plot.selectAll("circle.score-point").data(points, (d, i) => i);
      dots.join(
        (enter) => enter.append("circle")
          .attr("class", "score-point")
          .attr("cx", (d) => x(d.score))
          .attr("cy", (d) => y(0))
          .attr("r", 0)
          .attr("fill", (d) => color(d.score))
          .attr("fill-opacity", 0.75)
          .call((enter) => enter.transition().duration(T).delay((d, i) => i * 3)
            .attr("cy", (d) => y(d.salary)).attr("r", 5)),
        (update) => update.transition().duration(T)
          .attr("cx", (d) => x(d.score)).attr("cy", (d) => y(d.salary)).attr("fill", (d) => color(d.score)),
      );
    }

    function showClose() {
      focus("none", 0);
    }

    return { showHook, showScale, showFunnel, showVisa, showSkills, showSalary, showClose };
  }

  // ── Boot ──

  function init(story) {
    bindText(story);

    const svg = d3.select("#chart-svg");
    const chart = buildChart(svg);

    const renderers = {
      hook: () => chart.showHook(story),
      scale: () => chart.showScale(story),
      funnel: () => chart.showFunnel(story),
      visa: () => chart.showVisa(story),
      skills: () => chart.showSkills(story),
      salary: () => chart.showSalary(story),
      close: () => chart.showClose(),
    };

    // Render the hook state immediately (before any scrolling) so the page
    // isn't blank on load.
    renderers.hook();

    const scroller = scrollama();
    scroller.setup({ step: ".step", offset: 0.55 }).onStepEnter((response) => {
      document.querySelectorAll(".step").forEach((el) => el.classList.remove("is-active"));
      response.element.classList.add("is-active");
      const stepKey = response.element.getAttribute("data-step");
      const accentKey = response.element.getAttribute("data-accent");
      response.element.style.setProperty("--step-accent", ACCENT_MAP[accentKey] || COLOR.blue);

      const render = renderers[stepKey];
      if (render) render();
    });

    window.addEventListener("resize", () => scroller.resize());
  }

  fetch("data/story.json")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(init)
    .catch((err) => {
      console.error("Failed to load data/story.json:", err);
      document.getElementById("server-warning").style.display = "flex";
    });
})();
