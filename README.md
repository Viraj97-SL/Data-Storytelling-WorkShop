# Data Storytelling Workshop

Two deliverables built from the same UK AI/ML/DS job-market dataset (a
market-intelligence agent's Postgres export): a multi-library chart survey
plus an interactive Streamlit dashboard, and a standalone D3 scrollytelling
story built on a second, related dataset. Nothing here depends on any other
repo — every data-shaping utility is implemented locally in `viz/shared.py`.

## Layout

```
scripts/export_for_viz.py   Exports the market-intelligence DB -> data/exports/*.csv + jobmarket.parquet
viz/shared.py                Palette, helpers (week_start, normalize_location, classify_rising_cooling, ...)
viz/01_matplotlib_seaborn.py Salary bands, role composition, top hiring organisations
viz/02_plotly.py             Skill trends, salary by experience, skill co-occurrence heatmap
viz/03_altair.py             Work-model mix over time, top UK locations
viz/04_bokeh.py              Weekly posting volume
viz/dashboard.py             Streamlit app — dark/greyscale/amber "financial terminal" theme
viz/story/                   Scrollytelling page (D3 v7 + Scrollama) — see viz/story/README.md
tests/                       pytest coverage for the story data builder
```

See `viz/README.md` for the full design-system writeup, real-data caveats,
and a chart-by-chart takeaway table. See `viz/story/README.md` for the
story's narrative outline, sourcing, and the honest cut-corners list.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install pandas pyarrow sqlalchemy psycopg2-binary matplotlib seaborn plotly altair bokeh streamlit pytest
```

## Getting the data

Both deliverables read from `data/exports/`, which is never committed (see
`.gitignore`). Regenerate it from a Postgres connection string:

```bash
# PowerShell
$env:JOBFORGE_VIZ_DB_URL = "postgresql://..."
python scripts/export_for_viz.py
```

The story additionally needs its own database for `viz/story/build_story_data.py`
— see `viz/story/README.md` for the full two-source explanation.

## Running the charts and dashboard

```bash
python viz/01_matplotlib_seaborn.py   # -> viz/output/01_*.png
python viz/02_plotly.py               # -> viz/output/02_*.html
python viz/03_altair.py               # -> viz/output/03_*.html
python viz/04_bokeh.py                # -> viz/output/04_*.html
streamlit run viz/dashboard.py        # interactive app on localhost:8501
```

## Running the story

```bash
cd viz/story
python -m http.server                 # then open http://localhost:8000
```

`data/story.json` must be regenerated first (`python viz/story/build_story_data.py`)
— it is precomputed, never generated client-side, and never committed.

## Tests

```bash
pytest tests/
```
