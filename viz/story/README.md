# The UK AI/ML Job Market, As Scraped — a scrollytelling story

A single-page scrolling data narrative in the Tampa Bay Times "Failure
Factories" style: one persistent D3 chart that morphs between states as you
scroll, short bold-the-number prose steps on the left, dark theme, one
highlight color per step. Vanilla D3 v7 + Scrollama, no build step, no
framework.

## How to run it

Browsers block `fetch()` against `file://` paths, so double-clicking
`index.html` will show a "needs a local server" warning instead of the
story. From this folder:

```bash
python -m http.server
```

then open `http://localhost:8000` in a browser (Chrome/Firefox/Edge —
anything from the last few years; uses `Array.prototype.at()`). Laptop
screen width or wider; not built for mobile.

## Regenerating the data

`data/story.json` is precomputed — the JS never aggregates anything. To
regenerate it:

```bash
# The matching pipeline's own DB (scale, funnel, tiers, visa, salary-vs-score):
export JOBFORGE_PIPELINE_DB_URL="postgresql://..."   # PowerShell: $env:JOBFORGE_PIPELINE_DB_URL = "..."

# Skills-over-time reads data/exports/job_skills.csv (from the separate
# market-intelligence DB) — run scripts/export_for_viz.py first if that
# file doesn't exist yet.

python viz/story/build_story_data.py
```

It prints real row counts per step when it runs — if a number here looks
different from the table below, the underlying data has changed since this
was written; trust the live run.

## What each step claims, and where the number came from

This story deliberately pulls from **two different internal databases** —
a matching pipeline, and a separate market-intelligence system — because
neither alone supports the full narrative. Every step is tagged with its
source (`source-tag` pill under the step text) so this is never ambiguous
while reading. No public/external data was used anywhere in this story —
see the caveats below for exactly why some obvious extensions (literal
three-gate funnel, full sponsorship-rate-of-the-whole-market) were cut
rather than filled in with outside numbers.

| Step | Claim | Source | Real number (at time of writing) |
|---|---|---|---|
| **1. Hook** | Of the employers we could verify actually hold a sponsor licence, essentially none said so in the job ad | matching pipeline | 49 licensed; 0 of those overlapped with a "claims sponsorship" posting |
| **2. Scale** | How big this dataset actually is, honestly | matching pipeline | 3,915 distinct postings, 17 weeks, 7 sources |
| **3. The narrowing funnel** | Scraped → scored → tier split | matching pipeline | 3,915 → 775 scored (19.8%) → bronze 462 / silver 157 / gold 156 |
| **4. The visa reality** | The gap between JD-claimed sponsorship and a verified licence | matching pipeline, cross-referenced against the real UK Home Office Register of Licensed Sponsors | Of 480 employers actually checked, only 49 (10.2%) hold a licence |
| **5. Skills over time** | Which skills dominate week to week | Market-intelligence system | 278 distinct skills tracked, ~15 real weeks of data |
| **6. Salary vs. match score** | Whether a higher match score means better pay | matching pipeline (`score_history` ⋈ `job_analytics`) | n=123 scored jobs with disclosed annual-looking pay |
| **7. Close** | Honest statement of what this data can't tell us | — | Drawn directly from the caveats found while building steps 3–4 |

## Caveats and cut corners (found while building this, not guessed)

- **The funnel is 2 real gates, not the three originally scoped.**
  `run_history.total_after_dedup` and `.total_after_prescreen` are `NULL`
  on every single run in the database — that instrumentation exists in the
  schema but nothing has ever written to it. Rather than fabricate a
  plausible-looking dedup/prescreen number, the funnel shows only
  scraped → scored (both real), then the tier split of the scored jobs.
- **The visa pictogram is based on the 480-checked → 49-licensed gap, not
  the "claims AND was checked" overlap.** That direct overlap is only n=6
  (with 0 of those 6 confirmed licensed) — too thin a sample to headline a
  story on. The 480→49 gap is real, well-supported, and just as damning.
- **`scale.total_scraped` is a distinct-jobs count, not a sum of
  `run_history.total_scraped`.** Summing the latter across all 24 runs
  gives 33,511 — that's counting the same posting every time it gets
  re-scraped in a later weekly run, not distinct postings. The inflated
  number is kept in `story.json` (`scale.inflated_run_history_sum`) only
  as documentation of why it wasn't used.
- **`salary_score` excludes disclosed pay under £1,000.** Values like
  "£450" or "£625" in this schema are day-rate contract figures, not
  annual salaries — there's no pay-period column to disambiguate them (the
  exact same issue found and handled the same way for the market DB in
  `viz/shared.py`'s `with_valid_salary()`). Plotting a £450 day rate next
  to a £120,000 annual salary on one linear axis would misrepresent
  contract roles as near-unpaid — some of the original points were
  excluded rather than shown misleadingly (`salary_score.excluded_day_rate_like`).
- **Skills-over-time uses a different database from every other step**
  because the matching pipeline's own `matched_skills_json` is always an
  empty list — confirmed while building the earlier `viz/` charts (see
  the main `README.md`). There was no real skill data to draw the
  requested chart from in the matching pipeline at all.
- **Only a minority of employers in this dataset have ever been checked**
  against the real government register — checks are cached/rate-limited,
  not exhaustive. The true market-wide licence rate is unknown beyond this
  sample; the story says this explicitly in the close step rather than
  implying full coverage.

## Files

- `index.html` — structure, CDN script tags (D3 v7, Scrollama), step text markup with `data-bind` attributes.
- `story.css` — dark theme, sticky-graphic + scrolling-steps layout, responsive to laptop width.
- `story.js` — Scrollama wiring, `data-bind` text population, and the D3 chart engine (one `<svg>`, six state-render functions, all state changes via `.transition()` — never a swapped static image).
- `build_story_data.py` — precomputes every step into `data/story.json`. Standalone, type-hinted, runnable on its own; prints real row counts per step every time it runs.
- `data/story.json` — generated output (regenerate with the command above; not meant to be hand-edited, not committed — see .gitignore).
