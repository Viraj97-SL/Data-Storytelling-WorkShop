"""
Workshop Viz #1: Matplotlib / Seaborn baseline.

Three explanatory charts from the real exported market-intelligence data:
  1. Salary distribution by pay band (lower/mid/upper tercile) — built twice
     in one figure: a deliberately messy "exploratory default" panel on the
     left, then the polished "explanatory" version on the right. This
     dataset has no CV-match score to build tiers from (see
     README.md), so the ordinal dimension here is a salary tercile
     instead — same messy-vs-polished structure, honest substitute data.
  2. Role category distribution — which roles this market actually posts.
  3. Top hiring organisations — jobs.company, previously unused.

Run standalone:
    python viz/01_matplotlib_seaborn.py

Output: viz/output/01_salary_by_pay_band.png
        viz/output/01_role_category_distribution.png
        viz/output/01_top_hiring_organisations.png
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from shared import (
    FONT_SIZE_AXIS_TITLE,
    FONT_SIZE_TICK,
    FONT_SIZE_TITLE,
    GRIDLINE,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    PAY_BAND_COLORS,
    PAY_BAND_ORDER,
    SEQUENTIAL_BLUE,
    assign_pay_band,
    ensure_output_dir,
    humanize_label,
    load_jobs,
    style_mpl_axes,
    with_valid_salary,
)

plt.rcParams.update({
    "font.size": FONT_SIZE_TICK,
    "axes.titlesize": FONT_SIZE_TITLE,
    "axes.labelsize": FONT_SIZE_AXIS_TITLE,
    "xtick.labelsize": FONT_SIZE_TICK,
    "ytick.labelsize": FONT_SIZE_TICK,
})

# Recruitment agencies and staffing firms dominate this posting list — see
# the "Top hiring organisations" chart's caption and README.md. Not
# filtered out (a name-pattern heuristic would misclassify real companies
# too), just labelled honestly.
_RECRUITER_MARKERS = ("recruit", "staffing", "talent", "hays", "reed", "randstad", "harnham", "adria", "xcede", "matchtech", "itol")


def _looks_like_recruiter(company: str) -> bool:
    lowered = str(company).lower()
    return any(marker in lowered for marker in _RECRUITER_MARKERS)


def plot_salary_by_pay_band(jobs: pd.DataFrame, output_path) -> None:
    disclosed = with_valid_salary(jobs).copy()
    disclosed["pay_band"] = assign_pay_band(disclosed["salary_midpoint"])
    near_zero_n = int((disclosed["salary_midpoint"] < 1000).sum())

    fig, (ax_messy, ax_clean) = plt.subplots(1, 2, figsize=(14, 5.5))

    # ── Left: the exploratory default nobody should ship ──
    # Too many bins, default seaborn hue cycling (ignores band order), a
    # redundant legend for what's already the title, heavy default grid.
    sns.histplot(
        data=disclosed, x="salary_midpoint", hue="pay_band", bins=40, ax=ax_messy, legend=True
    )
    ax_messy.set_title("salary_midpoint by pay_band", fontsize=FONT_SIZE_AXIS_TITLE)
    ax_messy.grid(True, which="both")
    ax_messy.set_xlabel("salary_midpoint")
    ax_messy.set_ylabel("Count")

    # ── Right: the explanatory version ──
    # One ordinal ramp (lower -> mid -> upper, light -> dark), band
    # boundaries marked directly, counts/percentages direct-labelled
    # instead of a legend, gridlines recessive and horizontal-only.
    p33, p66 = disclosed["salary_midpoint"].quantile([1 / 3, 2 / 3])
    p01, p99 = disclosed["salary_midpoint"].quantile([0.01, 0.99])
    bin_edges = np.linspace(min(0, p01), p99, 31)
    binned = pd.cut(disclosed["salary_midpoint"], bins=bin_edges, include_lowest=True)
    counts = binned.value_counts().sort_index()
    bin_lefts = [interval.left for interval in counts.index]

    def _band_for_bin(left: float) -> str:
        if left >= p66:
            return "upper"
        if left >= p33:
            return "mid"
        return "lower"

    colors = [PAY_BAND_COLORS[_band_for_bin(left)] for left in bin_lefts]
    bin_width = bin_edges[1] - bin_edges[0]
    ax_clean.bar(bin_lefts, counts.values, width=bin_width * 0.9, color=colors, align="edge")
    ax_clean.set_xlim(bin_edges[0], bin_edges[-1])
    ax_clean.set_xlabel("Disclosed salary midpoint (£)")
    ax_clean.set_ylabel("")
    ax_clean.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax_clean.set_axisbelow(True)
    style_mpl_axes(ax_clean)

    for boundary in (p33, p66):
        ax_clean.axvline(boundary, color=INK_MUTED, linestyle="--", linewidth=1)

    total = len(disclosed)
    band_counts = disclosed["pay_band"].value_counts()
    y_top = ax_clean.get_ylim()[1]
    label_x = {"lower": p33 / 2, "mid": (p33 + p66) / 2, "upper": (p66 + bin_edges[-1]) / 2}
    label_y = {"lower": 0.95, "mid": 0.95, "upper": 0.78}
    for band in PAY_BAND_ORDER:
        n = int(band_counts.get(band, 0))
        pct = round(100 * n / total, 1) if total else 0.0
        boundary_label = {"lower": p33, "mid": p66, "upper": bin_edges[-1]}[band]
        ax_clean.text(
            label_x[band], y_top * label_y[band],
            f"{band.title()}\n£{int(boundary_label):,}\n{n} ({pct}%)",
            ha="center", va="top", color=INK_PRIMARY, fontsize=FONT_SIZE_TICK,
        )

    ax_clean.set_title(
        f"Pay splits roughly into thirds around £{p33:,.0f} and £{p66:,.0f}",
        color=INK_PRIMARY, fontsize=FONT_SIZE_TITLE, loc="left",
    )
    ax_clean.text(
        0.0, 1.1, f"1st-99th pct view; {near_zero_n} likely day-rate values sit near £0",
        transform=ax_clean.transAxes, color=INK_SECONDARY, fontsize=FONT_SIZE_TICK - 1, va="bottom",
    )

    fig.suptitle("Exploratory default (left) vs. explanatory chart (right) — same data", fontsize=FONT_SIZE_TITLE + 1)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor="white")
    plt.close(fig)


def plot_role_category_distribution(jobs: pd.DataFrame, output_path) -> None:
    labelled = jobs["role_category"].fillna("unknown").apply(humanize_label)
    counts = labelled.value_counts().sort_values(ascending=True)
    total = len(jobs)

    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.barh(counts.index, counts.values, color=SEQUENTIAL_BLUE[450])

    for label, value in zip(counts.index, counts.values):
        pct = round(100 * value / total, 1) if total else 0.0
        ax.text(value + total * 0.006, label, f"{value} ({pct}%)", va="center", color=INK_PRIMARY, fontsize=FONT_SIZE_TICK)

    ax.set_xlim(0, counts.max() * 1.2)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    style_mpl_axes(ax, hide_spines=("top", "right"))
    ax.set_xlabel("Postings")

    top_label = counts.idxmax()
    top_pct = round(100 * counts.max() / total, 1) if total else 0.0
    ax.set_title(
        f"'{top_label}' dominates postings at {top_pct}% (n={total})",
        color=INK_PRIMARY, fontsize=FONT_SIZE_TITLE, loc="left",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor="white")
    plt.close(fig)


def plot_top_hiring_organisations(jobs: pd.DataFrame, output_path, top_n: int = 15) -> None:
    counts = jobs["company"].value_counts().head(top_n).sort_values(ascending=True)
    recruiter_n = jobs["company"].apply(_looks_like_recruiter).sum()
    recruiter_pct = round(100 * recruiter_n / len(jobs), 1) if len(jobs) else 0.0

    colors = [SEQUENTIAL_BLUE[650] if _looks_like_recruiter(c) else SEQUENTIAL_BLUE[450] for c in counts.index]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(counts.index, counts.values, color=colors)

    for label, value in zip(counts.index, counts.values):
        ax.text(value + 1, label, str(value), va="center", color=INK_PRIMARY, fontsize=FONT_SIZE_TICK)

    ax.set_xlim(0, counts.max() * 1.12)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    style_mpl_axes(ax, hide_spines=("top", "right"))
    ax.set_xlabel("Postings")
    ax.tick_params(axis="y", labelsize=FONT_SIZE_TICK - 1)

    ax.set_title(
        f"Top {top_n} hiring organisations",
        color=INK_PRIMARY, fontsize=FONT_SIZE_TITLE, loc="left",
    )
    ax.text(
        0.0, 1.05,
        f"Darker bars read as agency names by pattern — ~{recruiter_pct}% of postings are agency-listed",
        transform=ax.transAxes, color=INK_SECONDARY, fontsize=FONT_SIZE_TICK - 2, va="bottom",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor="white")
    plt.close(fig)


def main() -> None:
    sns.set_style("white")
    out_dir = ensure_output_dir()
    jobs = load_jobs()

    salary_path = out_dir / "01_salary_by_pay_band.png"
    plot_salary_by_pay_band(jobs, salary_path)
    print(f"wrote {salary_path}")

    role_path = out_dir / "01_role_category_distribution.png"
    plot_role_category_distribution(jobs, role_path)
    print(f"wrote {role_path} ({len(jobs)} postings)")

    companies_path = out_dir / "01_top_hiring_organisations.png"
    plot_top_hiring_organisations(jobs, companies_path)
    print(f"wrote {companies_path}")


if __name__ == "__main__":
    main()
