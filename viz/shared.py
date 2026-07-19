"""
Shared data loaders and palette for the workshop viz scripts.

Every viz/*.py chart script loads through here so all five charts (+ the
dashboard) read the same tables the same way and share one visual language.
Not a standalone script — imported by the others, which each still run with
`python viz/0N_*.py` on their own (the script's own directory is on
sys.path automatically).

Data comes from data/exports/ (produced by scripts/export_for_viz.py against
a `market` schema — run that first). This schema is a general-purpose
market-intelligence agent's database — there is no CV-match score anywhere
in it, so "tier" here means a salary tercile band, not a score bucket. See
README.md for every caveat.

week_start(), classify_rising_cooling(), and normalize_location() were
originally imported read-only from a sibling pipeline project's source tree
(pure, dependency-free utilities with no pipeline secrets attached); they're
inlined directly here so this repo is fully standalone.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT_DIR / "data" / "exports"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ── week_start / classify_rising_cooling ─────────────────────────────────
# A skill with fewer than this many total zero-followed-by-nonzero weeks of
# history isn't "New" so much as noise — require it to have been genuinely
# absent before appearing.
NEW_SKILL_ZERO_WEEKS = 2
STABLE_SLOPE_THRESHOLD = 0.3
TREND_R_SQUARED_THRESHOLD = 0.8


def week_start(dt: datetime) -> datetime:
    """Return the Monday 00:00 of the ISO week containing dt."""
    date_only = datetime(dt.year, dt.month, dt.day)
    return date_only - timedelta(days=date_only.weekday())


def _linear_trend(y: list[float] | np.ndarray) -> tuple[float, float]:
    """Fit a simple linear trend to y (evenly spaced). Returns (slope, r_squared)."""
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n < 2 or np.all(y_arr == y_arr[0]):
        return 0.0, 0.0

    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, y_arr, 1)
    y_pred = slope * x + intercept
    ss_res = float(np.sum((y_arr - y_pred) ** 2))
    ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), r_squared


def classify_rising_cooling(weekly_counts: list[float], window: int = 3) -> str:
    """
    Statistically robust Rising/Cooling/Stable label over the trailing window.

    Rising  = positive slope over the trailing `window` weeks AND the current
              week's value is at or above the trailing-window mean.
    Cooling = the mirror condition (negative slope, current <= mean).
    Stable  = neither condition holds, or not enough history yet.
    """
    if len(weekly_counts) < window:
        return "Stable"

    trailing = weekly_counts[-window:]
    slope, _ = _linear_trend(trailing)
    mean = sum(trailing) / len(trailing)
    current = trailing[-1]

    if slope > 0 and current >= mean:
        return "Rising"
    if slope < 0 and current <= mean:
        return "Cooling"
    return "Stable"


# ── normalize_location ────────────────────────────────────────────────────
_POSTCODE_DATA_FILE = ROOT_DIR / "data" / "uk_postcode_areas.json"
_POSTCODE_PATTERN = re.compile(r"\b([A-Z]{1,2})\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.IGNORECASE)
_REMOTE_PATTERN = re.compile(r"\bremote\b|\bwork\s*from\s*home\b|\bwfh\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _postcode_area_lookup() -> dict[str, str]:
    with open(_POSTCODE_DATA_FILE, encoding="utf-8") as f:
        raw: dict[str, str] = json.load(f)
    return {area.upper(): city for area, city in raw.items()}


@lru_cache(maxsize=1)
def _known_cities() -> tuple[str, ...]:
    """Every city/region name in the lookup, longest-first so substring
    matching prefers the more specific name (e.g. "Milton Keynes" before
    a shorter false-positive substring)."""
    return tuple(sorted(set(_postcode_area_lookup().values()), key=len, reverse=True))


def normalize_location(location: str | None) -> str:
    """
    Normalise a raw job location string to a city/region label.

    Priority: explicit postcode > known city name substring > "Remote" > "Other UK".
    """
    if not location or not location.strip():
        return "Unknown"

    postcode_match = _POSTCODE_PATTERN.search(location)
    if postcode_match:
        area = postcode_match.group(1).upper()
        city = _postcode_area_lookup().get(area)
        if city:
            return city

    lowered = location.lower()
    for city in _known_cities():
        if city.lower() in lowered:
            return city

    if _REMOTE_PATTERN.search(location):
        return "Remote"

    return "Other UK"


# ── Palette (validated instance from the dataviz skill's references/palette.md) ──
# Fixed categorical order — assign by entity identity, never by rank/value.
CATEGORICAL = [
    ("blue", "#2a78d6"),
    ("green", "#008300"),
    ("magenta", "#e87ba4"),
    ("yellow", "#eda100"),
    ("aqua", "#1baf7a"),
    ("orange", "#eb6834"),
    ("violet", "#4a3aa7"),
    ("red", "#e34948"),
]
CATEGORICAL_HEXES = [hex_ for _, hex_ in CATEGORICAL]

# Sequential blue ramp (light -> dark), used for ordinal/magnitude encodings.
SEQUENTIAL_BLUE = {
    100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef",
    300: "#6da7ec", 350: "#5598e7", 400: "#3987e5", 450: "#2a78d6",
    500: "#256abf", 550: "#1c5cab", 600: "#184f95", 650: "#104281", 700: "#0d366b",
}

# Ordinal pay-band ramp — lower/mid/upper salary tercile as light->dark steps
# of one hue, mirroring how a genuine score tier would be encoded (this
# schema has no CV-match score to build tiers from).
PAY_BAND_ORDER = ["lower", "mid", "upper"]
PAY_BAND_COLORS = {
    "lower": SEQUENTIAL_BLUE[250],
    "mid": SEQUENTIAL_BLUE[450],
    "upper": SEQUENTIAL_BLUE[650],
}

STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"

SURFACE = "#fcfcfb"
PAGE_PLANE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
CARD_BORDER = "rgba(11,11,11,0.10)"
CARD_SHADOW = "0 1px 2px rgba(11,11,11,0.04), 0 8px 24px rgba(11,11,11,0.06)"

# Diverging pair (blue <-> red) for polarity encodings — e.g. a salary
# premium/discount vs. the market median. Neutral midpoint is gray.
DIVERGING_POSITIVE = SEQUENTIAL_BLUE[450]
DIVERGING_NEGATIVE = "#e34948"
DIVERGING_NEUTRAL = "#c3c2b7"

# ── Typography — sized up from each library's default (10-12px reads as
# fine print once a chart is embedded at half the dashboard's width) ──
FONT_FAMILY = "system-ui, -apple-system, Segoe UI, sans-serif"
FONT_SIZE_TITLE = 17
FONT_SIZE_SUBTITLE = 12
FONT_SIZE_AXIS_TITLE = 13
FONT_SIZE_TICK = 12

_ACRONYMS = {"ai", "ml", "nlp", "llm"}
_WORD_OVERRIDES = {"mlops": "MLOps"}


def humanize_label(raw: str) -> str:
    """
    'ai_engineer' -> 'AI Engineer', 'data_scientist' -> 'Data Scientist'.

    Category values across this schema (role_category, work_model, pay
    bands) are snake_case in the DB — fine for code, unreadable as an axis
    label. Known ML/AI acronyms are upper-cased; everything else is
    title-cased word by word.
    """
    words = str(raw).replace("_", " ").split()
    out = []
    for w in words:
        lowered = w.lower()
        if lowered in _WORD_OVERRIDES:
            out.append(_WORD_OVERRIDES[lowered])
        elif lowered in _ACRONYMS:
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


PLOTLY_LAYOUT_KWARGS = dict(
    plot_bgcolor=SURFACE,
    paper_bgcolor=SURFACE,
    font=dict(family=FONT_FAMILY, color=INK_PRIMARY, size=FONT_SIZE_TICK),
    title_font=dict(size=FONT_SIZE_TITLE, color=INK_PRIMARY),
    margin=dict(l=60, r=30, t=70, b=50),
)


def style_plotly_axes(fig) -> None:
    """Apply the shared readability + palette styling to a plotly figure's axes."""
    fig.update_xaxes(
        gridcolor=GRIDLINE, linecolor=INK_SECONDARY, zeroline=False,
        title_font=dict(size=FONT_SIZE_AXIS_TITLE, color=INK_SECONDARY),
        tickfont=dict(size=FONT_SIZE_TICK, color=INK_SECONDARY),
    )
    fig.update_yaxes(
        gridcolor=GRIDLINE, linecolor=INK_SECONDARY, zeroline=False,
        title_font=dict(size=FONT_SIZE_AXIS_TITLE, color=INK_SECONDARY),
        tickfont=dict(size=FONT_SIZE_TICK, color=INK_SECONDARY),
    )


def style_mpl_axes(ax, hide_spines: tuple[str, ...] = ("top", "right", "left")) -> None:
    """Apply the shared readability + palette styling to a matplotlib Axes."""
    for spine in hide_spines:
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        if spine not in hide_spines:
            ax.spines[spine].set_color(BASELINE)
    ax.tick_params(colors=INK_SECONDARY, labelsize=FONT_SIZE_TICK)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.xaxis.label.set_fontsize(FONT_SIZE_AXIS_TITLE)
    ax.yaxis.label.set_fontsize(FONT_SIZE_AXIS_TITLE)


def with_valid_salary(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    jobs rows with a real disclosed salary_midpoint.

    Excludes both nulls and exact 0 — a handful of rows have
    salary_min=salary_max=0, a placeholder rather than a real disclosed
    figure (not a judgment call: £0 isn't a wage). A further chunk sit
    under £1,000 and read as day-rate contract values misplaced in an
    annual-looking field (there is no salary-period column in this schema
    to disambiguate) — those are left in but every chart using this data
    calls that out directly, per README.md.
    """
    return jobs[jobs["salary_midpoint"].notna() & (jobs["salary_midpoint"] > 0)]


def assign_pay_band(salary_midpoints: pd.Series) -> pd.Series:
    """Lower/mid/upper tercile of disclosed salary_midpoint (qcut, data-derived — no fixed thresholds exist here)."""
    return pd.qcut(salary_midpoints, q=3, labels=PAY_BAND_ORDER, duplicates="drop").astype(str)


def _require_export(path: Path) -> None:
    if not path.exists():
        sys.exit(
            f"Missing {path}.\n"
            "Run `python scripts/export_for_viz.py` first to populate data/exports/."
        )


def load_jobs() -> pd.DataFrame:
    """The full jobs export — one row per posting (market schema)."""
    path = EXPORT_DIR / "jobmarket.parquet"
    _require_export(path)
    df = pd.read_parquet(path)
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
    return df


def load_job_skills() -> pd.DataFrame:
    """job_skills export — one row per (job, skill) tag."""
    path = EXPORT_DIR / "job_skills.csv"
    _require_export(path)
    df = pd.read_csv(path)
    df["extracted_at"] = pd.to_datetime(df["extracted_at"], errors="coerce", utc=True)
    return df


def load_seen_jobs() -> pd.DataFrame:
    path = EXPORT_DIR / "seen_jobs.csv"
    _require_export(path)
    df = pd.read_csv(path)
    df["first_seen"] = pd.to_datetime(df["first_seen"], errors="coerce", utc=True)
    df["last_seen"] = pd.to_datetime(df["last_seen"], errors="coerce", utc=True)
    return df


def load_skill_cooccurrence() -> pd.DataFrame:
    path = EXPORT_DIR / "skill_cooccurrence.csv"
    _require_export(path)
    df = pd.read_csv(path)
    df["week"] = pd.to_datetime(df["week"], errors="coerce")
    return df


def load_pipeline_runs() -> pd.DataFrame:
    path = EXPORT_DIR / "pipeline_runs.csv"
    _require_export(path)
    df = pd.read_csv(path)
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce", utc=True)
    return df


def load_weekly_snapshots() -> pd.DataFrame:
    """Pre-computed weekly aggregates (salary percentiles, job_count, rates) — see README.md for caveats."""
    path = EXPORT_DIR / "weekly_snapshots.csv"
    _require_export(path)
    df = pd.read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    return df


def weekly_counts(timestamps: pd.Series, values: pd.Series | None = None) -> pd.Series:
    """
    Bucket a series of timestamps into weekly counts (or summed values).
    Gaps are NOT filled with zero — callers that need a dense weekly grid
    should reindex.
    """
    ts = pd.to_datetime(timestamps)
    weeks = ts.apply(week_start)
    if values is None:
        return weeks.value_counts().sort_index()
    return pd.Series(values.to_numpy(), index=weeks).groupby(level=0).sum().sort_index()


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def categorical_color_map(labels: list[str]) -> dict[str, str]:
    """
    Stable label -> hex mapping from the fixed categorical order.

    Sorted alphabetically once so a color always belongs to the same label
    run to run, rather than being reassigned by whatever order a groupby
    happens to produce. Past 8 distinct labels (the palette's slot count),
    the rest fold to muted ink rather than generating new hues.
    """
    ordered_labels = sorted(labels)
    color_map = {label: INK_MUTED for label in ordered_labels}
    for label, hex_ in zip(ordered_labels, CATEGORICAL_HEXES):
        color_map[label] = hex_
    return color_map


__all__ = [
    "CATEGORICAL", "CATEGORICAL_HEXES", "SEQUENTIAL_BLUE", "PAY_BAND_ORDER", "PAY_BAND_COLORS",
    "STATUS_GOOD", "STATUS_CRITICAL", "SURFACE", "PAGE_PLANE", "INK_PRIMARY", "INK_SECONDARY",
    "INK_MUTED", "GRIDLINE", "BASELINE", "CARD_BORDER", "CARD_SHADOW", "DIVERGING_POSITIVE",
    "DIVERGING_NEGATIVE", "DIVERGING_NEUTRAL", "FONT_FAMILY", "FONT_SIZE_TITLE",
    "FONT_SIZE_SUBTITLE", "FONT_SIZE_AXIS_TITLE", "FONT_SIZE_TICK", "PLOTLY_LAYOUT_KWARGS",
    "style_plotly_axes", "style_mpl_axes", "humanize_label", "assign_pay_band",
    "with_valid_salary", "load_jobs", "load_job_skills", "load_seen_jobs",
    "load_skill_cooccurrence", "load_pipeline_runs", "load_weekly_snapshots",
    "weekly_counts", "ensure_output_dir", "categorical_color_map",
    "week_start", "classify_rising_cooling", "normalize_location", "EXPORT_DIR", "OUTPUT_DIR",
]
