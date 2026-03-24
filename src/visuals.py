from __future__ import annotations

from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CATEGORIES = ["Efficacy", "Enrolment", "Operational", "Safety", "Strategy/Business", "Unknown"]
COLORS = {
    "Efficacy": "#3A6EA5",
    "Enrolment": "#88B4D6",
    "Operational": "#C59FC9",
    "Safety": "#C0504D",
    "Strategy/Business": "#E6A817",
    "Unknown": "#404040",
}
YEARS = list(range(2015, 2025))


def prepare_publication_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year_int"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out = out[out["year_int"].between(2015, 2024)].copy()
    out["category"] = out["termination_category"].fillna("Unknown")
    out["is_p2"] = out["phase"].astype(str).str.contains("2", na=False)
    out["is_p3"] = out["phase"].astype(str).str.contains("3", na=False)
    return out


def figure_to_png_bytes(fig: plt.Figure) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, dpi=300, bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    return buffer.getvalue()


def generate_figure_1(df: pd.DataFrame) -> plt.Figure:
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(9, 7), gridspec_kw={"height_ratios": [2.5, 0.8]})
    fig.patch.set_facecolor("white")

    yearly_total = df.groupby("year_int").size().reindex(YEARS, fill_value=0)
    bars = ax_a.bar(YEARS, yearly_total.values, color="#3A6EA5", width=0.65, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, yearly_total.values):
        ax_a.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 4,
            str(int(val)),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#222",
        )
    ax_a.set_ylabel("Number of terminated trials", fontsize=10)
    ax_a.set_xticks(YEARS)
    ax_a.set_xticklabels([str(y) for y in YEARS], fontsize=9)
    ax_a.set_xlabel("Year", fontsize=10)
    ax_a.set_ylim(0, max(1, yearly_total.max()) * 1.18)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.text(-0.08, 1.02, "a", transform=ax_a.transAxes, fontsize=14, fontweight="bold", va="top")

    total_all = len(df)
    cat_counts = df["category"].value_counts().reindex(CATEGORIES, fill_value=0)
    all_pcts = (cat_counts / total_all) * 100 if total_all else cat_counts * 0

    left = 0.0
    for cat in CATEGORIES:
        pct = float(all_pcts[cat])
        if pct == 0:
            continue
        ax_b.barh(0, pct, left=left, color=COLORS[cat], height=0.55, edgecolor="white", linewidth=0.8)
        if pct > 4:
            ax_b.text(left + pct / 2, 0, f"{pct:.1f}%", ha="center", va="center", fontsize=8.5, fontweight="bold", color="white")
        left += pct

    left = 0.0
    for cat in CATEGORIES:
        pct = float(all_pcts[cat])
        if pct == 0:
            continue
        ax_b.text(left + pct / 2, -0.42, cat, ha="center", va="top", fontsize=7.5, color="#333")
        left += pct

    ax_b.set_xlim(0, 100)
    ax_b.set_ylim(-0.8, 0.6)
    ax_b.axis("off")
    ax_b.text(-0.08, 1.15, "b", transform=ax_b.transAxes, fontsize=14, fontweight="bold", va="top")

    fig.suptitle(
        "Fig. 1 | Trends in the termination of industry-sponsored phase II and\n"
        "phase III clinical trials from 2015 to 2024",
        fontsize=11,
        fontweight="bold",
        y=1.01,
    )
    fig.text(
        0.5,
        -0.03,
        "a, Number of trials terminated by year.  "
        "b, Proportion of terminated trials by reason (% of all terminated trials).\n"
        f"Data source: ClinicalTrials.gov.  n = {total_all:,} terminated trials.",
        ha="center",
        fontsize=8,
        color="#555",
        style="italic",
    )
    plt.tight_layout(h_pad=2.5)
    return fig


def generate_figure_2(df: pd.DataFrame) -> plt.Figure:
    p2 = df[df["is_p2"]].copy()
    p3 = df[df["is_p3"]].copy()

    def calculate_yearly_pcts(phase_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        counts = (
            phase_df.groupby(["year_int", "category"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=YEARS, columns=CATEGORIES, fill_value=0)
        )
        totals = counts.sum(axis=1)
        pcts = counts.div(totals.replace(0, 1), axis=0).multiply(100)
        return counts, totals, pcts

    _, p2_totals, p2_pcts = calculate_yearly_pcts(p2)
    _, p3_totals, p3_pcts = calculate_yearly_pcts(p3)

    fig = plt.figure(figsize=(14, 15))
    fig.patch.set_facecolor("white")
    gs_top = fig.add_gridspec(2, 1, top=0.97, bottom=0.52, hspace=0.38)
    gs_bot = fig.add_gridspec(2, 3, top=0.46, bottom=0.02, hspace=0.55, wspace=0.35)
    ax_a = fig.add_subplot(gs_top[0])
    ax_b = fig.add_subplot(gs_top[1])

    def draw_stacked_bars(ax: plt.Axes, totals: pd.Series, pcts: pd.DataFrame, phase_label: str, letter: str) -> None:
        bottoms = np.zeros(len(YEARS))
        for cat in CATEGORIES:
            vals = pcts[cat].values
            ax.bar(YEARS, vals, bottom=bottoms, color=COLORS[cat], width=0.65, edgecolor="white", linewidth=0.4, label=cat)
            for xi, (bot, val) in enumerate(zip(bottoms, vals)):
                if val >= 0.9:
                    text_color = "black" if cat == "Strategy/Business" else "white"
                    ax.text(YEARS[xi], bot + val / 2, f"{val:.1f}", ha="center", va="center", fontsize=5.5, color=text_color, fontweight="bold")
            bottoms += vals
        for xi, tot in enumerate(totals.values):
            ax.text(YEARS[xi], bottoms[xi] + 0.5, str(int(tot)), ha="center", va="bottom", fontsize=8, fontweight="bold", color="#222")
        ax.set_ylabel(f"Percentage of {phase_label}\nterminations", fontsize=10)
        ax.set_xticks(YEARS)
        ax.set_xticklabels([str(y) for y in YEARS], fontsize=9)
        ax.set_xlim(min(YEARS) - 0.6, max(YEARS) + 0.6)
        ax.set_ylim(0, 115)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.text(-0.06, 1.04, letter, transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")
        if letter == "a":
            handles = [mpatches.Patch(color=COLORS[c], label=c) for c in CATEGORIES]
            ax.legend(handles=handles, loc="upper left", fontsize=8, ncol=3, framealpha=0.9, columnspacing=0.8, handlelength=1.2)

    draw_stacked_bars(ax_a, p2_totals, p2_pcts, "phase II", "a")
    draw_stacked_bars(ax_b, p3_totals, p3_pcts, "phase III", "b")

    line_cats = ["Efficacy", "Enrolment", "Operational", "Safety", "Strategy/Business"]
    positions = [(0, 0), (0, 1), (1, 0), (1, 1), (0, 2)]
    fig.text(0.02, 0.455, "c", fontsize=13, fontweight="bold", va="top")

    for cat, pos in zip(line_cats, positions):
        ax = fig.add_subplot(gs_bot[pos])
        p2_line = p2_pcts[cat].values
        p3_line = p3_pcts[cat].values
        ax.plot(YEARS, p2_line, color="#3A6EA5", linewidth=1.8, marker="o", markersize=4)
        ax.plot(YEARS, p3_line, color="#C0504D", linewidth=1.8, marker="s", markersize=4)
        ax.set_title(cat, fontsize=10, fontweight="bold")
        ax.set_ylabel("% of terminations", fontsize=8)
        ax.set_xticks(YEARS[::2])
        ax.set_xticklabels([str(y) for y in YEARS[::2]], fontsize=8)
        ymax = max(float(np.max(p2_line)), float(np.max(p3_line)))
        ax.set_ylim(0, ymax * 1.35 if ymax > 0 else 1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    ax_leg = fig.add_subplot(gs_bot[1, 2])
    ax_leg.axis("off")
    leg_handles = [
        plt.Line2D([0], [0], color="#3A6EA5", linewidth=2, marker="o", markersize=5, label="Phase II"),
        plt.Line2D([0], [0], color="#C0504D", linewidth=2, marker="s", markersize=5, label="Phase III"),
    ]
    ax_leg.legend(handles=leg_handles, loc="center", fontsize=11, framealpha=0.9, title="Phase", title_fontsize=10)

    fig.suptitle("Fig. 2 | Trends in clinical trial terminations by phase from 2015 to 2024", fontsize=13, fontweight="bold", y=0.995)
    fig.text(
        0.5,
        -0.01,
        "a, Phase II trials.  b, Phase III trials.  Numbers above bars = total terminations "
        "for that year.  Numbers within segments = % of that year's terminations.\n"
        "c, Trends in the % of terminations attributed to each reason by phase.  "
        "Data source: ClinicalTrials.gov.",
        ha="center",
        fontsize=9,
        color="#555",
        style="italic",
    )
    return fig
