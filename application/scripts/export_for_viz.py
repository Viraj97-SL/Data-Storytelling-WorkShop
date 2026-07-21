"""
Workshop Data Export.

Exports historic data from the `market` schema of a Railway Postgres
project (a market-intelligence agent). Reads the connection string from the
JOBFORGE_VIZ_DB_URL environment variable — deliberately not DATABASE_URL,
so it can never collide with Railway's own project-level variable of that
name. Never hardcode the connection string, and never commit anything under
data/exports/ (see .gitignore).

Use the PUBLIC connection string (Railway dashboard -> Postgres service ->
Variables -> DATABASE_PUBLIC_URL, or the entry using a *.proxy.rlwy.net /
containers-...railway.app host). The internal *.railway.internal hostname
only resolves between services inside Railway's own network and will fail
to resolve from a local machine.

Usage:
    # PowerShell: $env:JOBFORGE_VIZ_DB_URL = "postgresql://..."
    # bash:       export JOBFORGE_VIZ_DB_URL="postgresql://..."
    python scripts/export_for_viz.py
    python scripts/export_for_viz.py --sample 200
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

ROOT_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT_DIR / "data" / "exports"

DB_SCHEMA = "market"

# Only the tables that actually have rows in this database (checked via
# introspection at export time regardless — this is just the wishlist).
# companies, cost_log, llm_cache, ml_features, model_evaluations,
# paper_index, qa_log, research_signals, salary_history, security_log,
# skill_taxonomy, skill_trends, agent_logs, alert_log all exist in the
# schema but are empty — see README.md.
TABLES = (
    "jobs",
    "job_skills",
    "seen_jobs",
    "skill_cooccurrence",
    "pipeline_runs",
    "agent_state",
    "weekly_snapshots",
)

# Per-table column most likely to carry a usable date range for the summary.
_DATE_COLUMN_BY_TABLE = {
    "jobs": "scraped_at",
    "job_skills": "extracted_at",
    "seen_jobs": "first_seen",
    "skill_cooccurrence": "week",
    "pipeline_runs": "started_at",
    "agent_state": "updated_at",
    "weekly_snapshots": "week_start",
}

_COMBINED_SOURCE_TABLE = "jobs"
_ANON_DROP_COLUMNS = ("url", "job_id", "description")
_ANON_HASH_LENGTH = 12


def _sync_engine_url(database_url: str) -> str:
    """Convert a Railway-style postgres:// URL to the sync psycopg2 driver."""
    return database_url.replace("postgres://", "postgresql+psycopg2://", 1).replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


_DB_URL_ENV_VAR = "JOBFORGE_VIZ_DB_URL"


def _build_engine() -> Engine:
    database_url = os.environ.get(_DB_URL_ENV_VAR)
    if not database_url:
        sys.exit(
            f"{_DB_URL_ENV_VAR} is not set.\n"
            "Copy the PUBLIC connection string from Railway dashboard -> "
            "the relevant project -> Postgres service -> Variables tab "
            "(DATABASE_PUBLIC_URL, or the entry with a *.proxy.rlwy.net / "
            "containers-...railway.app host — NOT the *.railway.internal "
            "one, which only resolves inside Railway's own network), then "
            "set it in this shell session, e.g.:\n"
            f'  PowerShell: $env:{_DB_URL_ENV_VAR} = "postgresql://..."\n'
            f'  bash:       export {_DB_URL_ENV_VAR}="postgresql://..."'
        )
    return create_engine(_sync_engine_url(database_url), pool_pre_ping=True)


def _existing_tables(engine: Engine) -> list[str]:
    available = set(inspect(engine).get_table_names(schema=DB_SCHEMA))
    existing = [t for t in TABLES if t in available]
    for missing in TABLES:
        if missing not in available:
            print(f"  [skip] {missing} — table not found in {DB_SCHEMA} schema")
    return existing


def _print_schema_summary(table: str, df: pd.DataFrame) -> None:
    print(f"\n{table} ({len(df)} rows)")
    if df.empty:
        print("  0 rows — nothing to summarise")
        return

    print("  columns:")
    for col, dtype in df.dtypes.items():
        non_null = df[col].notna().sum()
        print(f"    {col:<24} {str(dtype):<10} {non_null}/{len(df)} non-null")

    date_col = _DATE_COLUMN_BY_TABLE.get(table)
    if date_col and date_col in df.columns:
        parsed = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not parsed.empty:
            print(f"  date range ({date_col}): {parsed.min()} -> {parsed.max()}")


def _export_tables(engine: Engine, tables: list[str]) -> dict[str, pd.DataFrame]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}

    for table in tables:
        df = pd.read_sql(f'SELECT * FROM {DB_SCHEMA}."{table}"', engine)
        frames[table] = df
        csv_path = EXPORT_DIR / f"{table}.csv"
        df.to_csv(csv_path, index=False)
        _print_schema_summary(table, df)

    return frames


def _write_combined_parquet(frames: dict[str, pd.DataFrame]) -> None:
    if _COMBINED_SOURCE_TABLE not in frames:
        print(
            f"\n[skip] combined jobmarket.parquet — {_COMBINED_SOURCE_TABLE} "
            "table was not available"
        )
        return

    combined = frames[_COMBINED_SOURCE_TABLE].copy()
    if "scraped_at" in combined.columns:
        combined["scraped_at"] = pd.to_datetime(combined["scraped_at"], errors="coerce")

    parquet_path = EXPORT_DIR / "jobmarket.parquet"
    combined.to_parquet(parquet_path, index=False)
    print(f"\ncombined export -> {parquet_path} ({len(combined)} rows, from {_COMBINED_SOURCE_TABLE})")


def _write_anonymised_sample(frames: dict[str, pd.DataFrame], sample_n: int) -> None:
    if _COMBINED_SOURCE_TABLE not in frames or frames[_COMBINED_SOURCE_TABLE].empty:
        print(f"\n[skip] sample_anon.csv — no rows available in {_COMBINED_SOURCE_TABLE}")
        return

    source = frames[_COMBINED_SOURCE_TABLE]
    n = min(sample_n, len(source))
    sample = source.sample(n=n, random_state=42).drop(columns=list(_ANON_DROP_COLUMNS), errors="ignore")

    if "company" in sample.columns:
        sample = sample.copy()
        sample["company"] = sample["company"].apply(
            lambda name: hashlib.sha256(str(name).encode()).hexdigest()[:_ANON_HASH_LENGTH]
        )

    sample_path = EXPORT_DIR / "sample_anon.csv"
    sample.to_csv(sample_path, index=False)
    print(f"\nanonymised sample -> {sample_path} ({n} rows, safe to project)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Also write an anonymised N-row sample to data/exports/sample_anon.csv",
    )
    args = parser.parse_args()

    engine = _build_engine()
    print(f"Connected: {engine.url.render_as_string(hide_password=True)} (schema={DB_SCHEMA})")

    tables = _existing_tables(engine)
    if not tables:
        sys.exit(f"None of the expected tables exist in the {DB_SCHEMA} schema. Nothing to export.")

    frames = _export_tables(engine, tables)
    _write_combined_parquet(frames)

    if args.sample is not None:
        _write_anonymised_sample(frames, args.sample)

    print(
        "\nNote: there is no CV-match score anywhere in this schema (this is a "
        "general market-intelligence agent, not a personalised job-matching "
        "pipeline) — Phase-2 charts use salary tercile bands as the ordinal "
        "dimension instead of a score tier. offers_sponsorship/citizens_only "
        "are also very sparse here (<1% populated) — see README.md."
    )
    print(f"\nDone. Files written to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
