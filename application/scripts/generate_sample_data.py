"""
Generate a committed, schema-identical synthetic sample of the market-
intelligence export, so every viz/ script and the dashboard can run with
zero setup (no Postgres connection string, no scraping).

Mirrors the real export's documented shape (see ../viz/README.md's
"Real-data caveats" section) rather than a plausible-looking invented one:
role_category dominated by "other" (~66%), work_model 100% populated but
mostly "unknown", ~26% of company names reading as recruitment agencies,
~1.5% of disclosed salaries sitting at exactly 0 and a further slice under
£1,000 reading as day-rate contract values, offers_sponsorship/
citizens_only under 1%/4% populated respectively, and a ~26% seen_jobs
repost rate. Company names are obviously fake (adjective + noun + suffix,
e.g. "Quantum Fictus Analytics Ltd") — never a real employer or agency name.

Usage:
    python scripts/generate_sample_data.py

Output (committed — see .gitignore, this is the one exception under data/):
    data/sample/jobmarket_sample.parquet
    data/sample/job_skills_sample.csv
    data/sample/seen_jobs_sample.csv
    data/sample/skill_cooccurrence_sample.csv
"""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT_DIR / "data" / "sample"

RNG = np.random.default_rng(42)
N_JOBS = 2000
N_WEEKS = 17
WEEK_START = datetime(2026, 3, 16)  # a Monday

ROLE_CATEGORIES = ["other", "ai_engineer", "data_scientist", "ml_engineer", "mlops_engineer", "data_engineer"]
ROLE_WEIGHTS = [0.66, 0.10, 0.08, 0.06, 0.05, 0.05]

WORK_MODELS = ["unknown", "hybrid", "remote"]
WORK_MODEL_WEIGHTS = [0.69, 0.21, 0.10]

EXPERIENCE_LEVELS = ["junior", "mid", "senior", "unknown"]
EXPERIENCE_WEIGHTS = [0.20, 0.35, 0.25, 0.20]

SOURCES = ["reed", "career_pages", "wellfound", "ats_direct", "recruiter_boards", "hn_who_is_hiring", "linkedin_proxy"]
SOURCE_WEIGHTS = [0.30, 0.18, 0.14, 0.13, 0.12, 0.08, 0.05]

CITIES = ["London", "Manchester", "Birmingham", "Leeds", "Sheffield", "Liverpool", "Newcastle",
          "Bristol", "Cambridge", "Oxford", "Edinburgh", "Glasgow", "Cardiff"]
CITY_WEIGHTS = [0.43, 0.09, 0.07, 0.06, 0.04, 0.05, 0.04, 0.06, 0.03, 0.03, 0.04, 0.03, 0.03]
LOCATION_FORMATS = ["{city}", "{city}, UK", "Central {city}", "Remote", "{city} (Hybrid)"]

_FAKE_ADJ = ["Quantum", "Fictus", "Northern", "Bright", "Silver", "Nimbus", "Vertex", "Lumen", "Meridian", "Solace"]
_FAKE_NOUN = ["Analytics", "Robotics", "Dynamics", "Systems", "Labs", "Forge", "Works", "Collective", "Networks", "Ventures"]
_FAKE_SUFFIX = ["Ltd", "PLC", "Group", "Partners", "Studio"]
# Sized so recruiter-pattern names collide (and so dominate a top-N-by-
# count chart) at roughly the same relative rate as regular company names —
# 10 x 5 = 50 non-recruiter suffix combos would otherwise be ~10x denser
# per unique name than the 10x10x5=500 regular-company combo space, making
# every single top-15 "hiring organisation" a recruiter, which overstates
# the real ~26% agency-listed caveat this chart is meant to illustrate.
_RECRUITER_NOUN = [
    "Recruit Partners", "Staffing Group", "Talent Collective", "Recruit Solutions", "Staffing Network",
    "Talent Partners", "Recruit Group", "Staffing Solutions", "Talent Network", "Recruit Collective",
    "Staffing Partners", "Talent Solutions", "Recruit Network", "Staffing Collective", "Talent Group",
]

SKILLS_POOL = [
    "Python", "SQL", "Machine Learning", "PyTorch", "TensorFlow", "Docker", "Kubernetes",
    "AWS", "Spark", "Airflow", "dbt", "NLP", "LangChain", "REST API", "Git", "MLOps",
]
SKILL_WEIGHTS = np.array([0.16, 0.14, 0.10, 0.08, 0.06, 0.07, 0.05, 0.07, 0.04, 0.04, 0.03, 0.05, 0.04, 0.03, 0.02, 0.02])
SKILL_WEIGHTS = SKILL_WEIGHTS / SKILL_WEIGHTS.sum()

TITLES_BY_ROLE = {
    "other": ["Software Engineer", "Business Analyst", "Product Manager", "IT Support Specialist"],
    "ai_engineer": ["AI Engineer", "Senior AI Engineer", "Generative AI Engineer"],
    "data_scientist": ["Data Scientist", "Senior Data Scientist", "Applied Data Scientist"],
    "ml_engineer": ["ML Engineer", "Machine Learning Engineer"],
    "mlops_engineer": ["MLOps Engineer", "Senior MLOps Engineer"],
    "data_engineer": ["Data Engineer", "Senior Data Engineer"],
}


def _fake_company(is_recruiter: bool) -> str:
    if is_recruiter:
        return f"{RNG.choice(_FAKE_ADJ)} {RNG.choice(_RECRUITER_NOUN)}"
    return f"{RNG.choice(_FAKE_ADJ)} {RNG.choice(_FAKE_NOUN)} {RNG.choice(_FAKE_SUFFIX)}"


def _random_location() -> str:
    city = RNG.choice(CITIES, p=CITY_WEIGHTS)
    fmt = RNG.choice(LOCATION_FORMATS)
    return fmt.format(city=city)


def generate_jobs() -> pd.DataFrame:
    job_ids = [f"sample-{i:05d}" for i in range(N_JOBS)]
    scraped_at = [WEEK_START + timedelta(days=int(RNG.integers(0, N_WEEKS * 7))) for _ in range(N_JOBS)]
    role_category = RNG.choice(ROLE_CATEGORIES, size=N_JOBS, p=ROLE_WEIGHTS)
    work_model = RNG.choice(WORK_MODELS, size=N_JOBS, p=WORK_MODEL_WEIGHTS)
    experience_level = RNG.choice(EXPERIENCE_LEVELS, size=N_JOBS, p=EXPERIENCE_WEIGHTS)
    source = RNG.choice(SOURCES, size=N_JOBS, p=SOURCE_WEIGHTS)
    is_recruiter = RNG.random(N_JOBS) < 0.26
    company = [_fake_company(bool(r)) for r in is_recruiter]
    location = [_random_location() for _ in range(N_JOBS)]
    title = [RNG.choice(TITLES_BY_ROLE[r]) for r in role_category]

    has_salary = RNG.random(N_JOBS) < 0.45
    salary_midpoint = np.where(
        has_salary,
        np.clip(RNG.normal(loc=65000, scale=28000, size=N_JOBS), 20000, 160000),
        np.nan,
    )
    # Inject the two documented anomalies: exact-zero placeholders (~1.5%
    # of disclosed salaries) and day-rate-like values under £1,000 (~7%).
    zero_mask = has_salary & (RNG.random(N_JOBS) < 0.015)
    day_rate_mask = has_salary & ~zero_mask & (RNG.random(N_JOBS) < 0.075)
    salary_midpoint = np.where(zero_mask, 0.0, salary_midpoint)
    salary_midpoint = np.where(day_rate_mask, RNG.uniform(325, 750, size=N_JOBS), salary_midpoint)

    spread = RNG.uniform(0.85, 1.0, size=N_JOBS)
    salary_min = np.where(has_salary, np.round(salary_midpoint * spread, -2), np.nan)
    salary_max = np.where(has_salary, np.round(salary_midpoint * (2 - spread), -2), np.nan)

    offers_sponsorship = (RNG.random(N_JOBS) < 0.004).astype(int)
    citizens_only = (RNG.random(N_JOBS) < 0.034).astype(int)

    return pd.DataFrame({
        "job_id": job_ids,
        "scraped_at": scraped_at,
        "title": title,
        "company": company,
        "role_category": role_category,
        "work_model": work_model,
        "experience_level": experience_level,
        "location": location,
        "source": source,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_midpoint": salary_midpoint,
        "offers_sponsorship": offers_sponsorship,
        "citizens_only": citizens_only,
    })


def generate_job_skills(jobs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for job_id, scraped_at in zip(jobs["job_id"], jobs["scraped_at"]):
        if RNG.random() > 0.72:  # ~28% of postings have no extracted skill tags
            continue
        n_skills = int(RNG.integers(1, 6))
        chosen = RNG.choice(SKILLS_POOL, size=n_skills, replace=False, p=SKILL_WEIGHTS)
        for skill in chosen:
            rows.append({
                "job_id": job_id,
                "skill": skill,
                "extracted_at": scraped_at + timedelta(hours=int(RNG.integers(1, 48))),
            })
    return pd.DataFrame(rows)


def generate_seen_jobs(jobs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for job_id, scraped_at in zip(jobs["job_id"], jobs["scraped_at"]):
        is_reposted = RNG.random() < 0.26
        if is_reposted:
            times_seen = int(RNG.integers(2, 6))
            gap_days = int(RNG.normal(35, 12))
            last_seen = scraped_at + timedelta(days=max(gap_days, 1))
        else:
            times_seen = 1
            last_seen = scraped_at
        rows.append({
            "job_id": job_id, "first_seen": scraped_at, "last_seen": last_seen, "times_seen": times_seen,
        })
    return pd.DataFrame(rows)


def generate_skill_cooccurrence(job_skills: pd.DataFrame) -> pd.DataFrame:
    if job_skills.empty:
        return pd.DataFrame(columns=["week", "skill_a", "skill_b", "co_count", "pmi_score"])

    df = job_skills.copy()
    df["week"] = df["extracted_at"].dt.to_period("W-SUN").apply(lambda p: p.start_time)

    rows = []
    skill_totals = df["skill"].value_counts()
    total_n = len(df)
    for week, week_df in df.groupby("week"):
        for job_id, group in week_df.groupby("job_id"):
            skills = sorted(group["skill"].unique())
            for a, b in combinations(skills, 2):
                rows.append({"week": week, "skill_a": a, "skill_b": b})

    if not rows:
        return pd.DataFrame(columns=["week", "skill_a", "skill_b", "co_count", "pmi_score"])

    pairs = pd.DataFrame(rows)
    agg = pairs.groupby(["week", "skill_a", "skill_b"]).size().rename("co_count").reset_index()

    # Simple pointwise-mutual-information-style score: log(joint / (marginal_a * marginal_b)),
    # not a statistically rigorous PMI (no smoothing) — good enough for a
    # synthetic sample whose only job is to exercise the heatmap chart.
    def _pmi(row) -> float:
        p_a = skill_totals.get(row["skill_a"], 1) / total_n
        p_b = skill_totals.get(row["skill_b"], 1) / total_n
        p_ab = row["co_count"] / total_n
        return float(np.log(p_ab / (p_a * p_b) + 1e-9))

    agg["pmi_score"] = agg.apply(_pmi, axis=1)
    return agg


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    jobs = generate_jobs()
    jobs_path = SAMPLE_DIR / "jobmarket_sample.parquet"
    jobs.to_parquet(jobs_path, index=False)
    print(f"wrote {jobs_path} ({len(jobs)} rows)")

    job_skills = generate_job_skills(jobs)
    skills_path = SAMPLE_DIR / "job_skills_sample.csv"
    job_skills.to_csv(skills_path, index=False)
    print(f"wrote {skills_path} ({len(job_skills)} rows)")

    seen_jobs = generate_seen_jobs(jobs)
    seen_path = SAMPLE_DIR / "seen_jobs_sample.csv"
    seen_jobs.to_csv(seen_path, index=False)
    print(f"wrote {seen_path} ({len(seen_jobs)} rows)")

    cooc = generate_skill_cooccurrence(job_skills)
    cooc_path = SAMPLE_DIR / "skill_cooccurrence_sample.csv"
    cooc.to_csv(cooc_path, index=False)
    print(f"wrote {cooc_path} ({len(cooc)} rows)")


if __name__ == "__main__":
    main()
