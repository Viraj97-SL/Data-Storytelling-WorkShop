"""
Workshop Viz #4: Bokeh (interactive time series).

Total weekly posting volume — the fullest, most densely populated real
signal in the export (every jobs row carries a scraped_at timestamp, unlike
salary/experience_level/etc. which are partial). One line + shaded area, a
hover tool with a formatted date and exact count, and a reference line at
the median week.

Run standalone:
    python viz/04_bokeh.py

Output: viz/output/04_weekly_posting_volume.html
"""

from __future__ import annotations

import pandas as pd
from bokeh.io import output_file, save
from bokeh.models import ColumnDataSource, HoverTool, Label, Span
from bokeh.plotting import figure

from shared import (
    BASELINE,
    FONT_SIZE_AXIS_TITLE,
    FONT_SIZE_TICK,
    FONT_SIZE_TITLE,
    GRIDLINE,
    INK_MUTED,
    INK_SECONDARY,
    SEQUENTIAL_BLUE,
    ensure_output_dir,
    load_jobs,
    week_start,
)

HIGHLIGHT = SEQUENTIAL_BLUE[450]


def build_weekly_volume(jobs: pd.DataFrame) -> pd.DataFrame:
    df = jobs.dropna(subset=["scraped_at"]).copy()
    df["week"] = df["scraped_at"].apply(week_start)

    weekly = df.groupby("week").size().rename("postings").reset_index()
    all_weeks = pd.date_range(weekly["week"].min(), weekly["week"].max(), freq="W-MON")
    weekly = weekly.set_index("week").reindex(all_weeks, fill_value=0).rename_axis("week").reset_index()
    return weekly


def build_figure(weekly: pd.DataFrame):
    fig = figure(
        x_axis_type="datetime",
        width=850, height=420,
        title="Weekly job-posting volume across all sources",
        background_fill_color="#fcfcfb",
        border_fill_color="#fcfcfb",
    )
    fig.title.text_font_size = f"{FONT_SIZE_TITLE}px"

    if weekly.empty:
        fig.text(x=[0], y=[0], text=["No postings in this export"])
        return fig

    source = ColumnDataSource(weekly)

    fig.varea(x="week", y1=0, y2="postings", source=source, fill_color=HIGHLIGHT, fill_alpha=0.12)
    line = fig.line(x="week", y="postings", source=source, line_color=HIGHLIGHT, line_width=2)
    fig.scatter(x="week", y="postings", source=source, size=6, fill_color=HIGHLIGHT, line_color="white")

    hover = HoverTool(
        renderers=[line],
        tooltips=[("Week of", "@week{%F}"), ("Postings", "@postings")],
        formatters={"@week": "datetime"},
        mode="vline",
    )
    fig.add_tools(hover)

    median = weekly["postings"].median()
    ref_line = Span(location=median, dimension="width", line_color=INK_MUTED, line_dash="dashed", line_width=1)
    fig.add_layout(ref_line)
    fig.add_layout(Label(
        x=weekly["week"].iloc[0], y=median, text=f"  median {median:.0f}/week",
        text_color=INK_SECONDARY, text_font_size="10px",
    ))

    fig.xgrid.grid_line_color = None
    fig.ygrid.grid_line_color = GRIDLINE
    fig.axis.axis_line_color = BASELINE
    fig.axis.major_label_text_color = INK_SECONDARY
    fig.axis.major_label_text_font_size = f"{FONT_SIZE_TICK}px"
    fig.axis.axis_label_text_font_size = f"{FONT_SIZE_AXIS_TITLE}px"
    fig.axis.axis_label_text_color = INK_SECONDARY
    fig.yaxis.axis_label = "Postings scraped"
    fig.outline_line_color = None
    return fig


def main() -> None:
    out_dir = ensure_output_dir()
    jobs = load_jobs()
    weekly = build_weekly_volume(jobs)

    output_path = out_dir / "04_weekly_posting_volume.html"
    # mode="inline" embeds BokehJS in the file instead of loading it from
    # a CDN — needed for a workshop room that may not have internet.
    output_file(str(output_path), title="Weekly Posting Volume", mode="inline")
    fig = build_figure(weekly)
    save(fig)
    print(f"wrote {output_path} ({len(weekly)} weeks, {len(jobs)} postings)")


if __name__ == "__main__":
    main()
