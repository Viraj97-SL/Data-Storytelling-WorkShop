"""
Workshop Viz #3: Altair.

Two charts from the real exported market-intelligence data:
  1. Work-model mix over time (layered: share + volume, shared x-axis) —
     chosen because it's the best-populated categorical field with a real
     time dimension in this schema (100% of postings have a work_model, vs.
     <1% for offers_sponsorship/citizens_only, which is why a
     "sponsorship over time" chart isn't viable here — see README.md).
  2. Top UK locations — jobs.location, previously unused (normalised via
     shared.normalize_location, real postcode/city matching).

Run standalone:
    python viz/03_altair.py

Output: viz/output/03_work_model_mix_over_time.html
        viz/output/03_top_locations.html
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from shared import (
    FONT_SIZE_AXIS_TITLE,
    FONT_SIZE_TICK,
    FONT_SIZE_TITLE,
    GRIDLINE,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    SEQUENTIAL_BLUE,
    categorical_color_map,
    ensure_output_dir,
    load_jobs,
    normalize_location,
    week_start,
)

alt.data_transformers.disable_max_rows()

_AXIS_CONFIG = dict(labelFontSize=FONT_SIZE_TICK, titleFontSize=FONT_SIZE_AXIS_TITLE, gridColor=GRIDLINE, labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)


def build_weekly_work_model(jobs: pd.DataFrame) -> pd.DataFrame:
    df = jobs.dropna(subset=["scraped_at"]).copy()
    df["week"] = df["scraped_at"].apply(week_start)
    df["work_model"] = df["work_model"].fillna("unknown")

    weekly = df.groupby(["week", "work_model"]).size().rename("postings").reset_index()

    all_weeks = pd.date_range(weekly["week"].min(), weekly["week"].max(), freq="W-MON")
    all_models = sorted(weekly["work_model"].unique())
    dense_index = pd.MultiIndex.from_product([all_weeks, all_models], names=["week", "work_model"])
    weekly = weekly.set_index(["week", "work_model"]).reindex(dense_index, fill_value=0).reset_index()

    totals = weekly.groupby("week")["postings"].transform("sum")
    weekly["share_pct"] = (100 * weekly["postings"] / totals.replace(0, pd.NA)).fillna(0).round(1)
    return weekly


def build_work_model_chart(weekly: pd.DataFrame):
    if weekly.empty:
        return alt.Chart(pd.DataFrame({"msg": ["No postings in this export"]})).mark_text(size=16).encode(
            text="msg:N"
        )

    all_models = sorted(weekly["work_model"].unique())
    color_map = categorical_color_map(all_models)
    domain = list(color_map.keys())
    range_ = list(color_map.values())

    total_by_week = weekly.groupby("week")["postings"].sum()

    share_chart = alt.Chart(weekly).mark_area(interpolate="monotone").encode(
        x=alt.X("week:T", title=None, axis=alt.Axis(grid=False, domainColor=INK_SECONDARY)),
        y=alt.Y("share_pct:Q", stack="normalize", title="Share of postings"),
        color=alt.Color(
            "work_model:N", scale=alt.Scale(domain=domain, range=range_),
            legend=alt.Legend(title="Work model", labelFontSize=FONT_SIZE_TICK, titleFontSize=FONT_SIZE_AXIS_TITLE),
        ),
        tooltip=[
            alt.Tooltip("week:T", title="Week"),
            alt.Tooltip("work_model:N", title="Work model"),
            alt.Tooltip("postings:Q", title="Postings"),
            alt.Tooltip("share_pct:Q", title="Share (%)"),
        ],
    ).properties(
        width=700, height=240,
        title=alt.TitleParams(
            "Work-model mix over time — 'unknown' dominates (see README.md)",
            anchor="start", color=INK_PRIMARY, fontSize=FONT_SIZE_TITLE,
        ),
    )

    volume_chart = alt.Chart(total_by_week.reset_index()).mark_bar(color=INK_MUTED, size=14).encode(
        x=alt.X("week:T", title=None, axis=alt.Axis(grid=False, domainColor=INK_SECONDARY)),
        y=alt.Y("postings:Q", title="Postings / week"),
        tooltip=[alt.Tooltip("week:T", title="Week"), alt.Tooltip("postings:Q", title="Postings")],
    ).properties(width=700, height=110)

    return alt.vconcat(share_chart, volume_chart).resolve_scale(x="shared").configure_view(
        strokeWidth=0
    ).configure_axis(**_AXIS_CONFIG)


def build_locations_chart(jobs: pd.DataFrame, top_n: int = 12):
    regions = jobs["location"].apply(normalize_location)
    counts = regions.value_counts().head(top_n).reset_index()
    counts.columns = ["region", "postings"]
    total = len(jobs)
    counts["pct"] = (100 * counts["postings"] / total).round(1)
    order = counts.sort_values("postings", ascending=False)["region"].tolist()

    top_region = counts.iloc[0]

    chart = alt.Chart(counts).mark_bar(color=SEQUENTIAL_BLUE[450], cornerRadiusTopRight=3, cornerRadiusBottomRight=3).encode(
        x=alt.X("postings:Q", title="Postings"),
        y=alt.Y("region:N", sort=order, title=None),
        tooltip=[
            alt.Tooltip("region:N", title="Region"),
            alt.Tooltip("postings:Q", title="Postings"),
            alt.Tooltip("pct:Q", title="Share (%)"),
        ],
    ).properties(
        width=650, height=340,
        title=alt.TitleParams(
            f"{top_region['region']} leads at {top_region['pct']}% of postings (n={total})",
            anchor="start", color=INK_PRIMARY, fontSize=FONT_SIZE_TITLE,
        ),
    )
    labels = alt.Chart(counts).mark_text(align="left", dx=4, color=INK_PRIMARY, fontSize=FONT_SIZE_TICK).encode(
        x="postings:Q", y=alt.Y("region:N", sort=order), text=alt.Text("postings:Q"),
    )
    return (chart + labels).configure_axis(**_AXIS_CONFIG)


def main() -> None:
    out_dir = ensure_output_dir()
    jobs = load_jobs()

    weekly = build_weekly_work_model(jobs)
    work_model_chart = build_work_model_chart(weekly)
    work_model_path = out_dir / "03_work_model_mix_over_time.html"
    # inline=True embeds vega/vega-lite/vega-embed directly in the file
    # instead of loading them from a CDN — needed for a workshop room that
    # may not have internet.
    work_model_chart.save(str(work_model_path), inline=True)
    print(f"wrote {work_model_path} ({weekly['week'].nunique()} weeks, {len(jobs)} postings)")

    locations_chart = build_locations_chart(jobs)
    locations_path = out_dir / "03_top_locations.html"
    locations_chart.save(str(locations_path), inline=True)
    print(f"wrote {locations_path}")


if __name__ == "__main__":
    main()
