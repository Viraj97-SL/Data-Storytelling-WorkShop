"""
Streamlit Dashboard (Day-2 deliverable) — market-intelligence schema.

Dark, greyscale, one amber accent per view — a financial-terminal register,
not another "modern SaaS dashboard." Streamlit's own chrome (menu, footer,
header/deploy button) is hidden outright; st.metric is not used anywhere —
every number block below is hand-built HTML, because st.metric's internal
value/label elements ship with fixed-width, single-line CSS
(overflow:hidden; text-overflow:ellipsis) that silently truncates anything
longer than a bare number, which is exactly what broke the old KPI row.
Every panel title states the finding computed from the current filter, not
the dimension being shown ("London absorbs 43% of listings", not "Top
region") — the numbers are pulled out and used as the headline, not buried
in a caption below a generic label.

There is no CV-match score in this schema (see README.md) — filters and
charts are built around the fields that are actually well-populated here
(role_category, work_model, salary, location, company, and real per-job
skill tags).

Run:
    streamlit run viz/dashboard.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from shared import (
    assign_pay_band,
    classify_rising_cooling,
    humanize_label,
    load_job_skills,
    load_jobs,
    load_seen_jobs,
    load_skill_cooccurrence,
    normalize_location,
    week_start,
    with_valid_salary,
)

st.set_page_config(page_title="Market Intelligence", layout="wide", page_icon=None)

TOP_N_SKILLS = 10
TOP_N_COMPANIES = 12
TOP_N_LOCATIONS = 10
TOP_N_HEATMAP_SKILLS = 12
TOP_N_TREND_SKILLS = 15
MIN_SALARY_SAMPLE_PER_SKILL = 15

_RECRUITER_MARKERS = ("recruit", "staffing", "talent", "hays", "reed", "randstad", "harnham", "adria", "xcede", "matchtech", "itol")

# ── Dark, greyscale, one-accent palette — deliberately separate from
# viz/shared.py's light "Light Luxury" constants, which the static
# viz/01-04 scripts still correctly use. This file doesn't touch those. ──
BG = "#0e0e0e"
PANEL_BG = "#131313"
LINE = "#262624"
INK = "#e8e6e0"
INK_MUTED = "#8a8a86"
INK_FAINT = "#55534d"
ACCENT = "#d99a3e"
GREY_BAR = "#5a5a56"
GREY_BAR_DIM = "#3a3a37"
FONT_FAMILY = '"IBM Plex Sans", system-ui, sans-serif'

# Ordinal pay-band shades — dark-to-light grey reads as low-to-high on a
# dark background (brighter = more prominent = higher band). No amber here:
# the finding is the split itself, not one band being "the important one."
PAY_BAND_DARK = {"lower": "#4a4a47", "mid": "#8a8a86", "upper": "#c8c6be"}
PAY_BAND_ORDER = ["lower", "mid", "upper"]

# Two-stop continuous grey scale for the co-occurrence heatmap — a
# sequential magnitude encoding, not a categorical "important one" choice,
# so it stays pure greyscale rather than introducing amber into a ramp.
GREY_SEQUENTIAL_SCALE = ["#1a1a18", "#c8c6be"]

PLOTLY_LAYOUT_DARK = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT_FAMILY, color=INK_MUTED, size=12),
    margin=dict(l=50, r=20, t=10, b=40),
)


def _looks_like_recruiter(company: str) -> bool:
    return any(marker in str(company).lower() for marker in _RECRUITER_MARKERS)


def _style(fig, height: int | None = None):
    """Transparent background, hairline greyscale gridlines, page typeface — no default Plotly colourway."""
    fig.update_layout(**PLOTLY_LAYOUT_DARK)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor=LINE, linecolor=LINE, zeroline=False, tickfont=dict(color=INK_MUTED, size=11))
    fig.update_yaxes(gridcolor=LINE, linecolor=LINE, zeroline=False, tickfont=dict(color=INK_MUTED, size=11))
    return fig


# Streamlit's default theme="streamlit" (the st.plotly_chart default) runs a
# client-side template/colorway substitution layer on every figure before
# render — it's the one unaccounted-for transformation between "the figure
# object is correct" and "what actually reaches the DOM." theme=None turns
# it off so the palette set above is what actually renders, unmodified.
def _plot(fig) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;700&display=swap');

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    [data-testid="stToolbar"] {{visibility: hidden;}}
    [data-testid="stDecoration"] {{display: none;}}

    html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; }}
    .stApp {{ background: {BG}; color: {INK}; }}
    .block-container {{ padding-top: 2.2rem; max-width: 1240px; }}

    h1, h2, h3, h4 {{ font-family: {FONT_FAMILY}; font-weight: 700; color: {INK}; letter-spacing: -0.01em; }}
    h1 {{ font-size: 1.5rem; text-transform: none; border-bottom: 1px solid {LINE}; padding-bottom: 0.8rem; }}
    h4 {{
        font-size: 1.02rem; font-weight: 700; color: {INK};
        margin: 0 0 0.9rem 0; padding: 0;
    }}
    p, div, span, label {{ font-family: {FONT_FAMILY}; }}

    /* Flat, hairline-bordered panels — no rounded corners, no shadow, no
       white-on-grey card look. A panel differs from the page background by
       a 1px line only. */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {PANEL_BG};
        border: 1px solid {LINE} !important;
        border-radius: 0 !important;
        box-shadow: none !important;
    }}

    .finding-banner {{
        background: {PANEL_BG};
        border-top: 1px solid {LINE};
        border-bottom: 1px solid {LINE};
        padding: 1.4rem 0;
        margin-bottom: 1.6rem;
        font-size: 1.05rem;
        line-height: 1.6;
        color: {INK_MUTED};
    }}
    .finding-banner b {{ color: {INK}; font-weight: 700; }}
    .finding-banner .accent {{ color: {ACCENT}; font-weight: 700; }}

    .insight-caption {{ color: {INK_FAINT}; font-size: 0.85rem; margin: -0.4rem 0 0.9rem 0; }}

    /* Hand-built KPI blocks — replaces st.metric entirely. st.metric's
       internal elements ship with overflow:hidden + text-overflow:ellipsis,
       which silently truncated the old "N (X%)" compound values; a plain
       div has no such limit. */
    .kpi-row {{ display: flex; border-top: 1px solid {LINE}; border-bottom: 1px solid {LINE}; }}
    .kpi-block {{
        flex: 1; padding: 1.1rem 1.4rem; border-left: 1px solid {LINE};
    }}
    .kpi-block:first-child {{ border-left: none; }}
    .kpi-value {{
        font-size: 2.4rem; font-weight: 700; line-height: 1.1;
        font-variant-numeric: tabular-nums; white-space: nowrap;
    }}
    .kpi-label {{
        font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
        color: {INK_FAINT}; margin-top: 0.35rem;
    }}
    .kpi-delta {{ font-size: 0.82rem; color: {INK_MUTED}; margin-top: 0.2rem; font-variant-numeric: tabular-nums; }}

    .stat-row {{ display: flex; gap: 0; border: 1px solid {LINE}; }}
    .stat-block {{ flex: 1; padding: 1rem 1.2rem; border-left: 1px solid {LINE}; }}
    .stat-block:first-child {{ border-left: none; }}
    .stat-value {{ font-size: 1.9rem; font-weight: 700; color: {INK}; font-variant-numeric: tabular-nums; }}
    .stat-value.accent {{ color: {ACCENT}; }}
    .stat-label {{ font-size: 0.78rem; color: {INK_FAINT}; margin-top: 0.3rem; }}

    .trend-line {{ font-size: 0.95rem; color: {INK_MUTED}; margin: 0.3rem 0; }}
    .trend-line .accent {{ color: {ACCENT}; font-weight: 700; }}
    .trend-line .count {{ color: {INK}; font-weight: 700; }}

    .stTabs [data-baseweb="tab"] {{
        font-size: 0.9rem; padding: 8px 4px; color: {INK_FAINT};
        text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700;
    }}
    .stTabs [aria-selected="true"] {{ color: {INK} !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background-color: {ACCENT}; height: 2px; }}
    .stTabs [data-baseweb="tab-border"] {{ background-color: {LINE}; }}

    [data-testid="stPopover"] button {{
        background: {PANEL_BG}; border: 1px solid {LINE}; border-radius: 0;
        color: {INK_MUTED}; font-weight: 400; box-shadow: none;
    }}
    [data-testid="stPopover"] button:hover {{ border-color: {INK_FAINT}; color: {INK}; }}

    [data-testid="stMultiSelect"] [data-baseweb="tag"] {{ background: {LINE} !important; border-radius: 0 !important; }}

    hr {{ border-color: {LINE}; }}
</style>
"""


@st.cache_data
def _load_jobs() -> pd.DataFrame:
    # Normalise the nullable categorical columns to "unknown" once, here —
    # otherwise a multiselect filter built from .dropna().unique() silently
    # excludes every null row by default (role_category has 60 such rows),
    # since NaN never matches .isin(selected_values).
    jobs = load_jobs()
    for col in ("role_category", "work_model", "experience_level"):
        jobs[col] = jobs[col].fillna("unknown")
    return jobs


@st.cache_data
def _load_skills() -> pd.DataFrame:
    return load_job_skills()


@st.cache_data
def _load_cooccurrence() -> pd.DataFrame:
    return load_skill_cooccurrence()


@st.cache_data
def _load_seen() -> pd.DataFrame:
    return load_seen_jobs()


def _weekly_series_trailing(df: pd.DataFrame, date_col: str, agg_col: str | None, n_weeks: int = 8) -> list[float]:
    """Trailing weekly row-count or per-week-median series, chronological."""
    working = df.dropna(subset=[date_col]).copy()
    if working.empty:
        return []
    working["week"] = working[date_col].apply(week_start)
    series = working.groupby("week").size() if agg_col is None else working.groupby("week")[agg_col].median()
    return series.sort_index().tail(n_weeks).tolist()


def _kpi_html(label: str, value: str, delta: str | None = None, accent: bool = False) -> str:
    color = ACCENT if accent else INK
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    return (
        f'<div class="kpi-block"><div class="kpi-value" style="color:{color}">{value}</div>'
        f'<div class="kpi-label">{label}</div>{delta_html}</div>'
    )


def _apply_filters(jobs: pd.DataFrame, skills: pd.DataFrame):
    overall_min = jobs["scraped_at"].min()
    overall_max = jobs["scraped_at"].max()

    header_col, filter_col = st.columns([5, 1])
    with header_col:
        st.markdown("# Market Intelligence")
        st.caption("Real market-schema data, exported via scripts/export_for_viz.py — workshop demo, not the live app.")
    with filter_col:
        st.write("")
        with st.popover("Filters", width="stretch"):
            date_range = st.date_input(
                "Date range (scraped_at)",
                value=(overall_min.date(), overall_max.date()),
                min_value=overall_min.date(),
                max_value=overall_max.date(),
            )
            role_options = sorted(jobs["role_category"].unique())
            selected_roles = st.multiselect(
                "Role category", role_options, default=role_options, format_func=humanize_label,
            )
            work_model_options = sorted(jobs["work_model"].unique())
            selected_work_models = st.multiselect(
                "Work model", work_model_options, default=work_model_options, format_func=humanize_label,
            )

    if len(date_range) == 2:
        start = pd.Timestamp(date_range[0], tz="UTC")
        end = pd.Timestamp(date_range[1], tz="UTC") + pd.Timedelta(days=1)
    else:
        start, end = overall_min, overall_max + pd.Timedelta(days=1)

    category_mask = (
        (jobs["role_category"].isin(selected_roles) if selected_roles else True)
        & (jobs["work_model"].isin(selected_work_models) if selected_work_models else True)
    )
    # Kept separate from the date-range mask: week-over-week deltas need the
    # dataset's actual last two weeks regardless of whatever narrower date
    # window is currently selected for the rest of the dashboard.
    jobs_role_work_filtered = jobs[category_mask]

    jobs_filtered = jobs[(jobs["scraped_at"] >= start) & (jobs["scraped_at"] < end) & category_mask]
    skills_filtered = skills[skills["job_id"].isin(set(jobs_filtered["job_id"]))]
    return jobs_filtered, skills_filtered, jobs_role_work_filtered


def _render_finding_banner(jobs: pd.DataFrame, skills: pd.DataFrame) -> None:
    if jobs.empty:
        st.markdown('<div class="finding-banner">No postings match the current filters.</div>', unsafe_allow_html=True)
        return

    regions = jobs["location"].apply(normalize_location)
    top_region = regions.value_counts().idxmax()
    top_region_pct = round(100 * regions.value_counts().max() / len(jobs), 0)

    top_skill = skills["skill"].value_counts().idxmax() if not skills.empty else None
    top_skill_pct = round(100 * skills["skill"].value_counts().max() / jobs["job_id"].nunique(), 0) if not skills.empty else None

    with_salary = with_valid_salary(jobs)
    median_salary = with_salary["salary_midpoint"].median() if not with_salary.empty else None
    top_role = humanize_label(jobs["role_category"].value_counts().idxmax())

    # One accent per view: the postings count is the single most important
    # number here — everything else in this sentence stays plain ink-bold.
    parts = [f'<span class="accent">{len(jobs):,} postings</span> tracked']
    parts.append(f"<b>{top_region}</b> leads at {top_region_pct:.0f}% of listings")
    if top_skill:
        parts.append(f"<b>{top_skill}</b> appears in {top_skill_pct:.0f}% of scraped postings")
    if median_salary:
        parts.append(f"median disclosed pay is <b>£{median_salary:,.0f}</b>")
    parts.append(f"most postings are tagged <b>{top_role}</b>")

    st.markdown(f'<div class="finding-banner">{" · ".join(parts)}.</div>', unsafe_allow_html=True)


def _render_kpis(jobs: pd.DataFrame, skills: pd.DataFrame, jobs_role_work_filtered: pd.DataFrame) -> None:
    with_salary = with_valid_salary(jobs)
    salary_pct = round(100 * len(with_salary) / len(jobs), 1) if len(jobs) else 0.0
    regions = jobs["location"].apply(normalize_location)
    top_region = regions.value_counts().idxmax() if not jobs.empty else "—"

    postings_spark = _weekly_series_trailing(jobs_role_work_filtered, "scraped_at", None)
    salary_spark = _weekly_series_trailing(with_valid_salary(jobs_role_work_filtered), "scraped_at", "salary_midpoint")

    current_week_postings = postings_spark[-1] if postings_spark else len(jobs)
    postings_delta = None
    if len(postings_spark) >= 2 and postings_spark[-2]:
        postings_delta = round(100 * (postings_spark[-1] - postings_spark[-2]) / postings_spark[-2], 0)

    current_week_salary = salary_spark[-1] if salary_spark else None

    blocks = [
        _kpi_html(
            "Postings this week", f"{current_week_postings:,.0f}",
            delta=(f"{postings_delta:+.0f}% vs prior week" if postings_delta is not None else None),
            accent=True,  # the single most important number on the page
        ),
        _kpi_html("Disclosed salary", f"{salary_pct:.0f}%", delta=f"{len(with_salary):,} of {len(jobs):,} postings"),
        _kpi_html("Median salary this week", f"£{current_week_salary:,.0f}" if current_week_salary else "—"),
        _kpi_html("Distinct skills tracked", f"{skills['skill'].nunique():,}" if not skills.empty else "0"),
        _kpi_html("Leading region", top_region),
    ]
    st.markdown(f'<div class="kpi-row">{"".join(blocks)}</div>', unsafe_allow_html=True)


def _tab_overview(jobs: pd.DataFrame) -> None:
    col_left, col_right = st.columns([3, 2])

    with col_left, st.container(border=True):
        volume_df = jobs.dropna(subset=["scraped_at"]).copy()
        if not volume_df.empty:
            volume_df["week"] = volume_df["scraped_at"].apply(week_start)
            weekly = volume_df.groupby("week").size().rename("postings").reset_index()
            peak_week = weekly.loc[weekly["postings"].idxmax()]
            st.markdown(f"#### Postings peaked at {int(peak_week['postings'])} the week of {peak_week['week'].date()}")
            fig = px.area(weekly, x="week", y="postings", labels={"week": "", "postings": ""})
            fig.update_traces(line_color=GREY_BAR, fillcolor="rgba(90,90,86,0.15)")
            peak_mask = weekly["postings"] == weekly["postings"].max()
            fig.add_scatter(
                x=weekly.loc[peak_mask, "week"], y=weekly.loc[peak_mask, "postings"],
                mode="markers", marker=dict(color=ACCENT, size=9), showlegend=False, hoverinfo="skip",
            )
            _plot(_style(fig))
        else:
            st.info("No postings in the selected filters.")

    with col_right, st.container(border=True):
        labelled = jobs["role_category"].apply(humanize_label)
        counts = labelled.value_counts().head(8).sort_values()
        if not counts.empty:
            top = counts.index[-1]
            top_pct = round(100 * counts.iloc[-1] / len(jobs), 0)
            st.markdown(f"#### {top} accounts for {top_pct:.0f}% of postings")
            colors = [ACCENT if label == top else GREY_BAR for label in counts.index]
            fig = px.bar(x=counts.values, y=counts.index, orientation="h", labels={"x": "", "y": ""})
            fig.update_traces(marker_color=colors)
            fig.update_layout(showlegend=False)
            _plot(_style(fig, height=340))
        else:
            st.info("No role category data for the current filters.")


def _tab_skills(jobs: pd.DataFrame, skills: pd.DataFrame, cooc: pd.DataFrame) -> None:
    col_left, col_right = st.columns([2, 3])

    with col_left, st.container(border=True):
        if not skills.empty:
            top = skills["skill"].value_counts().head(TOP_N_SKILLS).sort_values()
            top_skill_pct = round(100 * top.iloc[-1] / jobs["job_id"].nunique(), 0) if len(jobs) else 0
            st.markdown(f"#### {top.index[-1]} appears in {top_skill_pct:.0f}% of postings")
            colors = [ACCENT if s == top.index[-1] else GREY_BAR for s in top.index]
            fig = px.bar(x=top.values, y=top.index, orientation="h", labels={"x": "", "y": ""})
            fig.update_traces(marker_color=colors)
            fig.update_layout(showlegend=False)
            _plot(_style(fig, height=380))
        else:
            st.info("No skill tags match the current filters.")

    with col_right, st.container(border=True):
        if not cooc.empty:
            agg = cooc.groupby(["skill_a", "skill_b"])["co_count"].sum().reset_index()
            top_pair = agg.loc[agg["co_count"].idxmax()]
            st.markdown(
                f"#### {top_pair['skill_a']} and {top_pair['skill_b']} co-occur most — "
                f"{int(top_pair['co_count'])} postings"
            )
            involvement = (
                pd.concat([
                    agg[["skill_a", "co_count"]].rename(columns={"skill_a": "skill"}),
                    agg[["skill_b", "co_count"]].rename(columns={"skill_b": "skill"}),
                ])
                .groupby("skill")["co_count"].sum().sort_values(ascending=False)
            )
            top_skills = involvement.head(TOP_N_HEATMAP_SKILLS).index.tolist()
            matrix = pd.DataFrame(0, index=top_skills, columns=top_skills, dtype=float)
            for _, row in agg.iterrows():
                a, b = row["skill_a"], row["skill_b"]
                if a in top_skills and b in top_skills:
                    matrix.loc[a, b] = row["co_count"]
                    matrix.loc[b, a] = row["co_count"]
            fig = px.imshow(matrix, color_continuous_scale=GREY_SEQUENTIAL_SCALE, labels={"color": ""})
            fig.update_traces(hovertemplate="%{y} + %{x}<br>%{z:.0f} postings<extra></extra>")
            fig.update_xaxes(tickangle=45)
            fig.update_layout(coloraxis_showscale=False)
            _plot(_style(fig, height=420))
        else:
            st.info("No skill co-occurrence data in this export.")


def _tab_pay(jobs: pd.DataFrame) -> None:
    with_salary = with_valid_salary(jobs)
    st.markdown(
        '<p class="insight-caption">Excludes £0 placeholder rows; likely day-rate values remain '
        "(no pay-period field exists in this schema to filter them out).</p>",
        unsafe_allow_html=True,
    )
    col_left, col_right = st.columns(2)

    with col_left, st.container(border=True):
        if len(with_salary) >= 3:
            banded = with_salary.copy()
            banded["pay_band"] = assign_pay_band(banded["salary_midpoint"])
            p33, p66 = banded["salary_midpoint"].quantile([1 / 3, 2 / 3])
            st.markdown(f"#### Pay splits into thirds around £{p33:,.0f} and £{p66:,.0f}")
            fig = px.histogram(
                banded, x="salary_midpoint", color="pay_band",
                color_discrete_map=PAY_BAND_DARK, category_orders={"pay_band": PAY_BAND_ORDER},
                nbins=25, labels={"salary_midpoint": ""},
            )
            fig.update_layout(bargap=0.05, showlegend=False)
            _plot(_style(fig))
        else:
            st.info("Not enough salary data for the current filters.")

    with col_right, st.container(border=True):
        if not with_salary.empty:
            exp_df = with_salary.copy()
            exp_df["experience_level"] = exp_df["experience_level"].apply(humanize_label)
            medians = exp_df.groupby("experience_level")["salary_midpoint"].median().sort_values()
            top_level = medians.index[-1]
            st.markdown(f"#### {top_level} commands the highest median pay — £{medians.iloc[-1]:,.0f}")
            order = medians.index.tolist()
            colors = {level: (ACCENT if level == top_level else GREY_BAR) for level in order}
            fig = px.box(
                exp_df, x="experience_level", y="salary_midpoint", color="experience_level",
                color_discrete_map=colors, category_orders={"experience_level": order},
                points="all", hover_data=["title", "company"],
                labels={"experience_level": "", "salary_midpoint": ""},
            )
            fig.update_traces(marker=dict(size=5, opacity=0.5))
            fig.update_layout(showlegend=False)
            _plot(_style(fig))
        else:
            st.info("No salary data matches the current filters.")


def _tab_who_where(jobs: pd.DataFrame) -> None:
    col_left, col_right = st.columns(2)

    with col_left, st.container(border=True):
        if not jobs.empty:
            counts = jobs["company"].value_counts().head(TOP_N_COMPANIES).sort_values()
            recruiter_n = jobs["company"].apply(_looks_like_recruiter).sum()
            recruiter_pct = round(100 * recruiter_n / len(jobs), 0)
            st.markdown(f"#### {recruiter_pct:.0f}% of postings are agency-listed, not direct employers")
            colors = [ACCENT if _looks_like_recruiter(c) else GREY_BAR for c in counts.index]
            fig = px.bar(x=counts.values, y=counts.index, orientation="h", labels={"x": "", "y": ""})
            fig.update_traces(marker_color=colors)
            fig.update_layout(showlegend=False)
            _plot(_style(fig, height=420))
        else:
            st.info("No company data for the current filters.")

    with col_right, st.container(border=True):
        if not jobs.empty:
            regions = jobs["location"].apply(normalize_location)
            counts = regions.value_counts().head(TOP_N_LOCATIONS).sort_values()
            top_pct = round(100 * counts.iloc[-1] / len(jobs), 0)
            st.markdown(f"#### {counts.index[-1]} absorbs {top_pct:.0f}% of listings")
            colors = [ACCENT if r == counts.index[-1] else GREY_BAR for r in counts.index]
            fig = px.bar(x=counts.values, y=counts.index, orientation="h", labels={"x": "", "y": ""})
            fig.update_traces(marker_color=colors)
            fig.update_layout(showlegend=False)
            _plot(_style(fig, height=420))
        else:
            st.info("No location data for the current filters.")


def _salary_premium_by_skill(jobs: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    with_salary = with_valid_salary(jobs)[["job_id", "salary_midpoint"]]
    if with_salary.empty:
        return pd.DataFrame(columns=["skill", "premium_pct", "n"])

    market_median = with_salary["salary_midpoint"].median()
    merged = skills.merge(with_salary, on="job_id", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["skill", "premium_pct", "n"])

    grouped = merged.groupby("skill")["salary_midpoint"].agg(["median", "count"]).reset_index()
    grouped = grouped[grouped["count"] >= MIN_SALARY_SAMPLE_PER_SKILL]
    grouped["premium_pct"] = (100 * (grouped["median"] - market_median) / market_median).round(1)
    grouped = grouped.rename(columns={"count": "n"})
    return grouped[["skill", "premium_pct", "n"]].sort_values("premium_pct")


def _posting_persistence(seen: pd.DataFrame) -> dict:
    days = (seen["last_seen"] - seen["first_seen"]).dt.total_seconds() / 86400
    reposted = days > 0
    return {
        "repost_rate_pct": round(100 * reposted.sum() / len(seen), 1) if len(seen) else 0.0,
        "median_days_reposted": round(days[reposted].median(), 1) if reposted.any() else None,
        "n_reposted": int(reposted.sum()),
        "n_total": len(seen),
    }


def _rising_cooling_skills(skills: pd.DataFrame, top_n: int = TOP_N_TREND_SKILLS) -> dict[str, list[str]]:
    df = skills.dropna(subset=["extracted_at", "skill"]).copy()
    if df.empty:
        return {"Rising": [], "Cooling": [], "Stable": []}
    df["week"] = df["extracted_at"].apply(week_start)

    candidate_skills = df["skill"].value_counts().head(top_n).index.tolist()
    all_weeks = sorted(df["week"].unique())

    buckets: dict[str, list[str]] = {"Rising": [], "Cooling": [], "Stable": []}
    for skill in candidate_skills:
        counts_by_week = df[df["skill"] == skill].groupby("week").size()
        weekly_counts = [int(counts_by_week.get(w, 0)) for w in all_weeks]
        buckets[classify_rising_cooling(weekly_counts)].append(skill)
    return buckets


def _tab_deeper_analysis(jobs: pd.DataFrame, skills: pd.DataFrame, seen: pd.DataFrame) -> None:
    col_left, col_right = st.columns([3, 2])

    with col_left, st.container(border=True):
        premium = _salary_premium_by_skill(jobs, skills)
        if not premium.empty:
            top_premium = premium.iloc[-1]
            st.markdown(f"#### {top_premium['skill']} commands the largest premium — +{top_premium['premium_pct']:.0f}%")
            st.markdown(
                f'<p class="insight-caption">vs. the £{with_valid_salary(jobs)["salary_midpoint"].median():,.0f} '
                f"filtered-market median · skills under {MIN_SALARY_SAMPLE_PER_SKILL} disclosed-salary postings omitted.</p>",
                unsafe_allow_html=True,
            )
            colors = [ACCENT if s == top_premium["skill"] else GREY_BAR for s in premium["skill"]]
            fig = px.bar(premium, x="premium_pct", y="skill", orientation="h", labels={"premium_pct": "", "skill": ""}, hover_data={"n": True})
            fig.update_traces(marker_color=colors)
            fig.add_vline(x=0, line_color=LINE, line_width=1)
            fig.update_layout(showlegend=False)
            _plot(_style(fig, height=420))
        else:
            st.info(f"No skill has ≥{MIN_SALARY_SAMPLE_PER_SKILL} disclosed-salary postings in the current filters.")

    with col_right:
        with st.container(border=True):
            stats = _posting_persistence(seen)
            once_only_pct = round(100 - stats["repost_rate_pct"], 0)
            st.markdown(f"#### {once_only_pct:.0f}% of postings are seen only once")
            median_txt = f"{stats['median_days_reposted']:.0f}" if stats["median_days_reposted"] is not None else "—"
            st.markdown(
                f"""
                <div class="stat-row">
                    <div class="stat-block">
                        <div class="stat-value accent">{stats['repost_rate_pct']}%</div>
                        <div class="stat-label">Reposted / re-scraped ({stats['n_reposted']} of {stats['n_total']})</div>
                    </div>
                    <div class="stat-block">
                        <div class="stat-value">{median_txt} days</div>
                        <div class="stat-label">Median days on market, when reposted</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        with st.container(border=True):
            buckets = _rising_cooling_skills(skills)
            st.markdown(f"#### {len(buckets['Rising'])} skills accelerating, {len(buckets['Cooling'])} cooling")
            rising_txt = ", ".join(buckets["Rising"]) or "none"
            cooling_txt = ", ".join(buckets["Cooling"]) or "none"
            st.markdown(f'<p class="trend-line"><span class="accent">RISING</span> — {rising_txt}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="trend-line">COOLING — {cooling_txt}</p>', unsafe_allow_html=True)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    jobs_all = _load_jobs()
    skills_all = _load_skills()
    cooc_all = _load_cooccurrence()
    seen_all = _load_seen()

    if jobs_all.empty:
        st.warning("No data in data/exports/. Run `python scripts/export_for_viz.py` first.")
        return

    jobs, skills, jobs_role_work_filtered = _apply_filters(jobs_all, skills_all)
    seen_filtered = seen_all[seen_all["job_id"].isin(set(jobs["job_id"]))]

    _render_finding_banner(jobs, skills)
    _render_kpis(jobs, skills, jobs_role_work_filtered)
    st.write("")

    tab_overview, tab_skills, tab_pay, tab_who_where, tab_deeper = st.tabs([
        "Overview", "Skills", "Pay", "Who & Where", "Deeper Analysis",
    ])
    with tab_overview:
        _tab_overview(jobs)
    with tab_skills:
        _tab_skills(jobs, skills, cooc_all)
    with tab_pay:
        _tab_pay(jobs)
    with tab_who_where:
        _tab_who_where(jobs)
    with tab_deeper:
        _tab_deeper_analysis(jobs, skills, seen_filtered)


if __name__ == "__main__":
    main()
