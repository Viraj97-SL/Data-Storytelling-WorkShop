"""
Workshop Viz #2: Plotly (interactive).

Three interactive charts from the real exported market-intelligence data:
  1. Weekly mention trend for the top 8 skills (from job_skills — this
     needed real per-job skill tags to build a genuine trend from).
  2. Salary by experience level, one point per job with disclosed pay,
     hover showing title/company/source.
  3. Skill co-occurrence heatmap — from skill_cooccurrence, previously
     unused. Answers "what should I actually learn alongside X" better
     than a flat ranked skill list.

pio.renderers.default is set to "notebook" up front — the default "iframe"
renderer throws MemoryError on Windows in this environment.

Run standalone:
    python viz/02_plotly.py

Output: viz/output/02_skill_trends.html
        viz/output/02_salary_by_experience.html
        viz/output/02_skill_cooccurrence_heatmap.html
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.io as pio

from shared import (
    PLOTLY_LAYOUT_KWARGS,
    SEQUENTIAL_BLUE,
    categorical_color_map,
    ensure_output_dir,
    load_job_skills,
    load_jobs,
    load_skill_cooccurrence,
    style_plotly_axes,
    week_start,
    with_valid_salary,
)

pio.renderers.default = "notebook"

TOP_N_SKILLS = 8
TOP_N_HEATMAP_SKILLS = 12


def build_skill_trends(skills: pd.DataFrame):
    df = skills.dropna(subset=["extracted_at", "skill"]).copy()
    df["week"] = df["extracted_at"].apply(week_start)

    top_skills = df["skill"].value_counts().head(TOP_N_SKILLS).index.tolist()
    df = df[df["skill"].isin(top_skills)]

    weekly = df.groupby(["week", "skill"]).size().rename("mentions").reset_index()
    all_weeks = pd.date_range(weekly["week"].min(), weekly["week"].max(), freq="W-MON")
    dense_index = pd.MultiIndex.from_product([all_weeks, top_skills], names=["week", "skill"])
    weekly = weekly.set_index(["week", "skill"]).reindex(dense_index, fill_value=0).reset_index()

    color_map = categorical_color_map(top_skills)

    fig = px.line(
        weekly, x="week", y="mentions", color="skill",
        color_discrete_map=color_map, category_orders={"skill": sorted(top_skills)},
        markers=True,
        title=f"Weekly mention trend, top {TOP_N_SKILLS} skills",
        labels={"week": "Week starting", "mentions": "Job postings mentioning skill", "skill": "Skill"},
    )
    fig.update_layout(**PLOTLY_LAYOUT_KWARGS, hovermode="x unified", legend_title_text="Skill")
    style_plotly_axes(fig)
    return fig


def build_salary_by_experience(jobs: pd.DataFrame):
    df = with_valid_salary(jobs).copy()
    df["experience_level"] = df["experience_level"].fillna("unknown")

    if df.empty:
        fig = px.box(title="No jobs with disclosed salary in this export")
        fig.update_layout(**PLOTLY_LAYOUT_KWARGS)
        return fig

    order = df.groupby("experience_level")["salary_midpoint"].median().sort_values().index.tolist()
    color_map = categorical_color_map(df["experience_level"].unique().tolist())

    fig = px.box(
        df, x="experience_level", y="salary_midpoint", color="experience_level",
        color_discrete_map=color_map, category_orders={"experience_level": order},
        points="all",
        hover_data={"title": True, "company": True, "source": True, "salary_midpoint": ":.0f"},
        title="Salary by experience level<br>"
              "<sup>Includes some likely day-rate values — no pay-period field exists to filter them</sup>",
        labels={"experience_level": "Experience level", "salary_midpoint": "Disclosed salary midpoint (£)"},
    )
    fig.update_traces(marker=dict(size=5, opacity=0.5))
    fig.update_layout(**PLOTLY_LAYOUT_KWARGS, showlegend=False)
    style_plotly_axes(fig)
    return fig


def build_skill_cooccurrence_heatmap(cooc: pd.DataFrame):
    if cooc.empty:
        fig = px.imshow([[0]], title="No skill co-occurrence data in this export")
        fig.update_layout(**PLOTLY_LAYOUT_KWARGS)
        return fig

    agg = cooc.groupby(["skill_a", "skill_b"]).agg(
        co_count=("co_count", "sum"), pmi=("pmi_score", "mean")
    ).reset_index()

    involvement = (
        pd.concat([
            agg[["skill_a", "co_count"]].rename(columns={"skill_a": "skill"}),
            agg[["skill_b", "co_count"]].rename(columns={"skill_b": "skill"}),
        ])
        .groupby("skill")["co_count"].sum()
        .sort_values(ascending=False)
    )
    top_skills = involvement.head(TOP_N_HEATMAP_SKILLS).index.tolist()

    matrix = pd.DataFrame(0, index=top_skills, columns=top_skills, dtype=float)
    for _, row in agg.iterrows():
        a, b = row["skill_a"], row["skill_b"]
        if a in top_skills and b in top_skills:
            matrix.loc[a, b] = row["co_count"]
            matrix.loc[b, a] = row["co_count"]

    fig = px.imshow(
        matrix, color_continuous_scale=[SEQUENTIAL_BLUE[100], SEQUENTIAL_BLUE[700]],
        labels={"color": "Postings mentioning both"},
        title=f"Skill co-occurrence — top {TOP_N_HEATMAP_SKILLS} skills, how often each pair appears together",
    )
    fig.update_traces(
        hovertemplate="%{y} + %{x}<br>%{z:.0f} postings<extra></extra>",
    )
    fig.update_layout(**PLOTLY_LAYOUT_KWARGS, height=650)
    fig.update_xaxes(tickangle=45)
    style_plotly_axes(fig)
    return fig


def main() -> None:
    out_dir = ensure_output_dir()

    skills = load_job_skills()
    trend_fig = build_skill_trends(skills)
    trend_path = out_dir / "02_skill_trends.html"
    trend_fig.write_html(trend_path, include_plotlyjs=True)
    print(f"wrote {trend_path} ({skills['skill'].nunique()} distinct skills, top {TOP_N_SKILLS} plotted)")

    jobs = load_jobs()
    salary_fig = build_salary_by_experience(jobs)
    salary_path = out_dir / "02_salary_by_experience.html"
    salary_fig.write_html(salary_path, include_plotlyjs=True)
    print(f"wrote {salary_path}")

    cooc = load_skill_cooccurrence()
    heatmap_fig = build_skill_cooccurrence_heatmap(cooc)
    heatmap_path = out_dir / "02_skill_cooccurrence_heatmap.html"
    heatmap_fig.write_html(heatmap_path, include_plotlyjs=True)
    print(f"wrote {heatmap_path} ({len(cooc)} weekly pair observations)")


if __name__ == "__main__":
    main()
