"""
Scrollytelling data builder — precomputes every step of viz/story/index.html
into viz/story/data/story.json. The JS does zero aggregation; every number
the story shows is computed here, once, from real data.

Reads from TWO separate data sources, each tagged in the output JSON so the
story can label them distinctly (see viz/story/README.md for the full
narrative-outline rationale):

  1. The matching-pipeline DB (job_analytics, score_history, run_history)
     — scale, funnel, tiers, the real UK sponsor-register cross-check, and
     salary-vs-score. Connection string from JOBFORGE_PIPELINE_DB_URL —
     deliberately a different env var name from JOBFORGE_VIZ_DB_URL, which
     scripts/export_for_viz.py already uses for the separate market DB, so
     the two can never collide with each other or with Railway's own
     project-level DATABASE_URL variable.
  2. The market-intelligence DB's local export (data/exports/job_skills.csv,
     produced by scripts/export_for_viz.py) — skills-over-time, since the
     matching pipeline's own matched_skills_json is always an empty list
     (see viz/README.md's caveats section).

Usage:
    # PowerShell: $env:JOBFORGE_PIPELINE_DB_URL = "postgresql://..."
    # bash:       export JOBFORGE_PIPELINE_DB_URL="postgresql://..."
    python viz/story/build_story_data.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

STORY_DIR = Path(__file__).resolve().parent
ROOT_DIR = STORY_DIR.parent.parent
EXPORT_DIR = ROOT_DIR / "data" / "exports"
OUTPUT_PATH = STORY_DIR / "data" / "story.json"

sys.path.insert(0, str(ROOT_DIR / "viz"))
from shared import classify_rising_cooling, week_start  # noqa: E402

_DB_URL_ENV_VAR = "JOBFORGE_PIPELINE_DB_URL"

# Mirrors the matching pipeline's own match_threshold setting and tier
# boundaries — kept as plain constants here rather than importing pipeline
# settings (which would require secrets this standalone script has no
# business depending on; see viz/shared.py for the same reasoning applied
# to assign_pay_band()).
MATCH_THRESHOLD = 70
GOLD_MIN = 85
SILVER_MIN = 75
TIER_ORDER = ("bronze", "silver", "gold")

TOP_N_SKILLS = 8
PICTOGRAM_N = 100

JOBFORGE_SOURCE_LABEL = "matching pipeline"
MARKET_SOURCE_LABEL = "market-intelligence system"


def _sync_engine_url(database_url: str) -> str:
    """Convert a Railway-style postgres:// URL to the sync psycopg2 driver."""
    return database_url.replace("postgres://", "postgresql+psycopg2://", 1).replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


def _build_engine() -> Engine:
    database_url = os.environ.get(_DB_URL_ENV_VAR)
    if not database_url:
        sys.exit(
            f"{_DB_URL_ENV_VAR} is not set.\n"
            "This is the matching pipeline's OWN database (distinct from "
            "JOBFORGE_VIZ_DB_URL, which points at the separate "
            "market-intelligence database) — copy the PUBLIC connection "
            "string from Railway, e.g.:\n"
            f'  PowerShell: $env:{_DB_URL_ENV_VAR} = "postgresql://..."\n'
            f'  bash:       export {_DB_URL_ENV_VAR}="postgresql://..."'
        )
    return create_engine(_sync_engine_url(database_url), pool_pre_ping=True)


def build_scale(engine: Engine) -> dict[str, Any]:
    """Step 2 — how big is this dataset, honestly (distinct jobs, not raw re-scrape events)."""
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM job_analytics")).scalar()
        start_raw, end_raw = conn.execute(text("SELECT MIN(scraped_at), MAX(scraped_at) FROM job_analytics")).fetchone()
        sources = [row[0] for row in conn.execute(text("SELECT DISTINCT source FROM job_analytics ORDER BY source")).fetchall()]
        # For the caveat: what summing run_history.total_scraped would have
        # implied (inflated by weekly re-scrapes of the same postings) —
        # kept only to document why we didn't use it, not used as a figure.
        inflated_sum = conn.execute(text("SELECT SUM(total_scraped) FROM run_history")).scalar()

    start, end = pd.to_datetime(start_raw), pd.to_datetime(end_raw)
    weeks = max(1, round((end - start).days / 7))

    return {
        "source": JOBFORGE_SOURCE_LABEL,
        "total_scraped": int(total),
        "date_start": start.date().isoformat(),
        "date_end": end.date().isoformat(),
        "weeks": weeks,
        "source_count": len(sources),
        "sources": sources,
        "inflated_run_history_sum": int(inflated_sum) if inflated_sum is not None else None,
        "note": (
            "total_scraped is a distinct job_analytics count. Summing "
            "run_history.total_scraped across all runs gives a much bigger, "
            "misleading number (re-scrape events, not distinct jobs) — see "
            "inflated_run_history_sum, not used as the headline figure."
        ),
    }


def build_funnel(engine: Engine) -> dict[str, Any]:
    """Step 3 — the real 2-gate funnel (scraped -> scored) plus tier split. dedup/prescreen were never instrumented."""
    with engine.connect() as conn:
        scraped = conn.execute(text("SELECT COUNT(*) FROM job_analytics")).scalar()
        scored = conn.execute(text("SELECT COUNT(*) FROM score_history")).scalar()
        qualified = conn.execute(
            text("SELECT COUNT(*) FROM score_history WHERE overall_score >= :threshold"),
            {"threshold": MATCH_THRESHOLD},
        ).scalar()
        tier_rows = conn.execute(text(f"""
            SELECT
                CASE WHEN overall_score >= {GOLD_MIN} THEN 'gold'
                     WHEN overall_score >= {SILVER_MIN} THEN 'silver'
                     ELSE 'bronze' END AS tier,
                COUNT(*) AS n
            FROM score_history
            GROUP BY tier
        """)).fetchall()
        dedup_populated = conn.execute(text("SELECT COUNT(*) FROM run_history WHERE total_after_dedup IS NOT NULL")).scalar()
        prescreen_populated = conn.execute(text("SELECT COUNT(*) FROM run_history WHERE total_after_prescreen IS NOT NULL")).scalar()
        total_runs = conn.execute(text("SELECT COUNT(*) FROM run_history")).scalar()

    tier_counts = {tier: n for tier, n in tier_rows}
    tiers = [
        {
            "tier": tier,
            "count": int(tier_counts.get(tier, 0)),
            "pct": round(100 * tier_counts.get(tier, 0) / scored, 1) if scored else 0.0,
        }
        for tier in TIER_ORDER
    ]

    return {
        "source": JOBFORGE_SOURCE_LABEL,
        "stages": [
            {"label": "Scraped", "value": int(scraped)},
            {"label": "Scored", "value": int(scored)},
        ],
        "tiers": tiers,
        "qualified_at_threshold": int(qualified),
        "match_threshold": MATCH_THRESHOLD,
        "dedup_stage_populated_runs": int(dedup_populated),
        "prescreen_stage_populated_runs": int(prescreen_populated),
        "total_runs": int(total_runs),
        "note": (
            "The pipeline schema has dedup/prescreen funnel columns "
            "(run_history.total_after_dedup/.total_after_prescreen), but "
            f"they are NULL on all {total_runs} runs — never instrumented, "
            "not thin data. Only the 2 real gates (scraped -> scored) are "
            "shown, plus the tier split of the scored jobs."
        ),
    }


def build_visa(engine: Engine) -> dict[str, Any]:
    """Step 4 — the sponsor-licence gap: JD claims vs. the real UK Home Office register."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN offers_sponsorship = 1 THEN 1 ELSE 0 END) AS claims,
                SUM(CASE WHEN employer_is_licensed_sponsor IS NOT NULL THEN 1 ELSE 0 END) AS checked,
                SUM(CASE WHEN employer_is_licensed_sponsor = 1 THEN 1 ELSE 0 END) AS licensed,
                SUM(CASE WHEN offers_sponsorship = 1 AND employer_is_licensed_sponsor IS NOT NULL THEN 1 ELSE 0 END) AS claims_and_checked,
                SUM(CASE WHEN offers_sponsorship = 1 AND employer_is_licensed_sponsor = 1 THEN 1 ELSE 0 END) AS claims_and_licensed
            FROM job_analytics
        """)).fetchone()

    total, claims, checked, licensed, claims_and_checked, claims_and_licensed = row
    checked = checked or 0
    licensed_pct_of_checked = round(100 * licensed / checked, 1) if checked else 0.0
    pictogram_highlighted = round(PICTOGRAM_N * licensed / checked) if checked else 0

    return {
        "source": JOBFORGE_SOURCE_LABEL,
        "total_postings": int(total),
        "claims_sponsorship": int(claims or 0),
        "claims_pct": round(100 * (claims or 0) / total, 1),
        "employers_checked": int(checked),
        "employers_checked_pct": round(100 * checked / total, 1),
        "employers_licensed": int(licensed or 0),
        "licensed_pct_of_checked": licensed_pct_of_checked,
        "claims_and_checked_overlap": int(claims_and_checked or 0),
        "claims_and_licensed_overlap": int(claims_and_licensed or 0),
        "pictogram_n": PICTOGRAM_N,
        "pictogram_highlighted": pictogram_highlighted,
        "register_source": (
            "UK Home Office Register of Licensed Sponsors (Worker/Temporary "
            "Worker routes), cross-referenced via the pipeline's sponsor "
            "register connector"
        ),
        "note": (
            f"The direct 'claimed sponsorship AND was checked' overlap is "
            f"only n={claims_and_checked} — too thin to headline. The "
            "pictogram instead shows the honest, better-supported gap: of "
            f"{checked} employers actually checked against the real "
            f"register, only {licensed} ({licensed_pct_of_checked}%) hold "
            "a licence."
        ),
    }


def build_salary_vs_score(engine: Engine) -> dict[str, Any]:
    """Step 6 — salary vs. match score, one point per scored job with disclosed pay."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT sh.overall_score, ja.salary_min, ja.salary_max, ja.title, ja.company, ja.source
            FROM score_history sh
            JOIN job_analytics ja ON sh.job_hash = ja.dedup_hash
            WHERE ja.salary_min IS NOT NULL OR ja.salary_max IS NOT NULL
        """)).fetchall()

    # Below this, a "salary" reads as a day-rate contract value (e.g. "£450"
    # for "AI Engineer (Contract)") rather than an annual salary — this
    # schema has no pay-period column to disambiguate them (same issue
    # found and handled the same way in viz/shared.py's with_valid_salary()
    # for the market DB). Mixing the two on one linear salary axis would
    # misrepresent day-rate contract roles as near-unpaid annual roles, so
    # they're excluded here rather than plotted misleadingly.
    DAY_RATE_LIKE_THRESHOLD = 1000

    all_points, kept_points = [], []
    for score, salary_min, salary_max, title, company, source in rows:
        disclosed = [v for v in (salary_min, salary_max) if v is not None and v > 0]
        if not disclosed:
            continue
        midpoint = sum(disclosed) / len(disclosed)
        score_f = float(score)
        tier = "gold" if score_f >= GOLD_MIN else ("silver" if score_f >= SILVER_MIN else "bronze")
        point = {
            "score": round(score_f, 1),
            "salary": round(float(midpoint)),
            "tier": tier,
            "title": title,
            "company": company,
            "source": source,
        }
        all_points.append(point)
        if point["salary"] >= DAY_RATE_LIKE_THRESHOLD:
            kept_points.append(point)

    excluded_n = len(all_points) - len(kept_points)
    return {
        "source": JOBFORGE_SOURCE_LABEL,
        "points": kept_points,
        "n": len(kept_points),
        "gold_min": GOLD_MIN,
        "silver_min": SILVER_MIN,
        "excluded_day_rate_like": excluded_n,
        "note": (
            f"n={len(kept_points)} scored jobs have disclosed annual-looking pay — modest, real, "
            f"plottable. {excluded_n} more had a disclosed value under £{DAY_RATE_LIKE_THRESHOLD} that reads as "
            "a day-rate contract figure, not an annual salary (no pay-period column exists to confirm either "
            "way) — excluded rather than plotted as if annual."
        ),
    }


def build_skills() -> dict[str, Any]:
    """Step 5 — weekly skill-mention trend + rising/cooling classification, from the market DB's local export."""
    skills_path = EXPORT_DIR / "job_skills.csv"
    if not skills_path.exists():
        sys.exit(f"Missing {skills_path} — run scripts/export_for_viz.py first (market DB).")

    df = pd.read_csv(skills_path)
    df["extracted_at"] = pd.to_datetime(df["extracted_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["extracted_at", "skill"]).copy()
    df["week"] = df["extracted_at"].apply(week_start)

    top_skills = df["skill"].value_counts().head(TOP_N_SKILLS).index.tolist()
    subset = df[df["skill"].isin(top_skills)]
    all_weeks: list[datetime] = sorted(subset["week"].unique())

    series: dict[str, list[int]] = {}
    buckets: dict[str, list[str]] = {"Rising": [], "Cooling": [], "Stable": []}
    for skill in top_skills:
        counts_by_week = subset[subset["skill"] == skill].groupby("week").size()
        weekly_counts = [int(counts_by_week.get(w, 0)) for w in all_weeks]
        series[skill] = weekly_counts
        buckets[classify_rising_cooling(weekly_counts)].append(skill)

    return {
        "source": MARKET_SOURCE_LABEL,
        "weeks": [w.date().isoformat() for w in all_weeks],
        "series": series,
        "rising": buckets["Rising"],
        "cooling": buckets["Cooling"],
        "stable": buckets["Stable"],
        "distinct_skills_total": int(df["skill"].nunique()),
        "note": "The matching pipeline's own matched_skills_json is always an empty list — this step uses the market-intelligence system's real per-job skill tags instead. See README.md.",
    }


def build_hook(scale: dict[str, Any], visa: dict[str, Any]) -> dict[str, Any]:
    """Step 1 — the single headline claim, derived from the visa gap already computed."""
    return {
        "claim_prefix": "Of the",
        "claim_number": visa["employers_licensed"],
        "claim_suffix": (
            f"UK employers we could verify actually hold a sponsor licence, "
            f"only {visa['claims_and_licensed_overlap']} had said so in the job ad."
        ),
        "sub": f"{scale['total_scraped']:,} postings scraped over {scale['weeks']} weeks. This is what the data actually shows.",
    }


def build_close(funnel: dict[str, Any], visa: dict[str, Any]) -> dict[str, Any]:
    """Step 7 — honest limits, drawn directly from the caveats found while building the earlier steps."""
    return {
        "points": [
            funnel["note"],
            (
                f"Only {visa['employers_checked_pct']}% of employers in this dataset have ever been "
                "checked against the real sponsor register — the true market-wide licence rate is "
                "unknown beyond this sample."
            ),
            (
                f"JD-stated sponsorship ({visa['claims_pct']}% of postings) barely overlaps with "
                "verified reality on this evidence."
            ),
        ],
        "no_public_data_used": True,
    }


def _clean_nans(value: Any) -> Any:
    """Recursively replace NaN/inf with None — json.dump emits invalid 'NaN' tokens otherwise."""
    if isinstance(value, dict):
        return {k: _clean_nans(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_nans(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def main() -> None:
    engine = _build_engine()

    scale = build_scale(engine)
    funnel = build_funnel(engine)
    visa = build_visa(engine)
    salary_score = build_salary_vs_score(engine)
    skills = build_skills()
    hook = build_hook(scale, visa)
    close = build_close(funnel, visa)

    story = _clean_nans({
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "jobforge_pipeline": JOBFORGE_SOURCE_LABEL,
                "market_intelligence": MARKET_SOURCE_LABEL,
            },
        },
        "hook": hook,
        "scale": scale,
        "funnel": funnel,
        "visa": visa,
        "skills": skills,
        "salary_score": salary_score,
        "close": close,
    })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(story, f, indent=2)

    print(f"Wrote {OUTPUT_PATH}\n")
    print("Row counts per step:")
    print(f"  hook              (derived from scale + visa)")
    print(f"  scale             total_scraped={scale['total_scraped']}, weeks={scale['weeks']}, sources={scale['source_count']}")
    print(f"  funnel            scraped={funnel['stages'][0]['value']}, scored={funnel['stages'][1]['value']}, "
          f"tiers={[(t['tier'], t['count']) for t in funnel['tiers']]}")
    print(f"  visa              total={visa['total_postings']}, claims={visa['claims_sponsorship']}, "
          f"checked={visa['employers_checked']}, licensed={visa['employers_licensed']}")
    print(f"  skills            top_skills={len(skills['series'])}, weeks={len(skills['weeks'])}, "
          f"rising={len(skills['rising'])}, cooling={len(skills['cooling'])}")
    print(f"  salary_score      n={salary_score['n']}")
    print(f"  close             {len(close['points'])} points")


if __name__ == "__main__":
    main()
