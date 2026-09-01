"""Charts for the country inequality series.

Faceted rather than a single axes: twelve lines on one plot would be
unreadable, and the four facets each carry three scope lines - few enough that
the categorical hues stay far apart under colour-vision deficiency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

from .datasets.lrcc_dvnl import DTYPE_ERAS

SURFACE = "#ffffff"
INK = "#1a1a1f"
INK_MUTED = "#6b7280"
GRID = "#e5e7eb"

#: Fixed hue order, assigned by scope and never cycled.
SCOPE_COLORS = {
    "all": "#2a78d6",
    "narrow": "#eb6834",
    "wide": "#1baf7a",
}
SCOPE_LABELS = {
    "all": "all units",
    "narrow": "excl. Saharan trio",
    "wide": "excl. six southern",
}

FACETS = [
    ("pixel", "zeros_included", "Pixel (1 km), all land pixels"),
    ("pixel", "lit_only", "Pixel (1 km), lit pixels only"),
    ("adm1", "", "Governorate, light density"),
    ("adm2", "", "Delegation, light density"),
]


def plot_inequality_series(
    rows: Sequence[dict],
    out_path: str | Path,
    *,
    iso3: str = "",
    break_year: int = 2014,
) -> Path:
    """Faceted index-vs-year chart, one facet per level/zero-treatment."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    grouped: Dict[tuple, List[dict]] = {}
    for row in rows:
        grouped.setdefault((row["level"], row["zeros"], row["scope"]), []).append(row)
    for series in grouped.values():
        series.sort(key=lambda r: r["year"])

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.4), dpi=200, facecolor=SURFACE)
    axes = axes.ravel()

    for ax, (level, zeros, title) in zip(axes, FACETS):
        ax.set_facecolor(SURFACE)
        for scope, color in SCOPE_COLORS.items():
            series = grouped.get((level, zeros, scope))
            if not series:
                continue
            ax.plot(
                [r["year"] for r in series],
                [r["gini"] for r in series],
                color=color,
                linewidth=2.0,
                label=SCOPE_LABELS.get(scope, scope),
                solid_capstyle="round",
            )
        # The DMSP->VIIRS handover is a candidate discontinuity, not a finding.
        ax.axvline(
            break_year - 0.5,
            color=INK_MUTED,
            linewidth=1.0,
            linestyle=(0, (4, 3)),
        )
        ax.annotate(
            "DMSP → VIIRS",
            xy=(break_year - 0.5, ax.get_ylim()[1]),
            xytext=(3, -9),
            textcoords="offset points",
            color=INK_MUTED,
            fontsize=7,
            ha="left",
            va="top",
        )
        ax.set_title(title, color=INK, fontsize=10, loc="left", pad=6)
        ax.grid(True, color=GRID, linewidth=0.7)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK_MUTED, labelsize=8)
        ax.set_ylabel("Gini", color=INK_MUTED, fontsize=8)

    handles, labels = axes[0].get_legend_handles_labels()
    legend = fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.005),
    )
    for text in legend.get_texts():
        text.set_color(INK)

    eras = ", ".join(
        f"{a}-{b}: {d}" if a != b else f"{a}: {d}" for a, b, d in DTYPE_ERAS
    )
    fig.suptitle(
        f"{iso3} nighttime-light inequality, 1992–2022".strip(),
        color=INK,
        fontsize=14,
        fontweight="bold",
        x=0.008,
        ha="left",
        y=0.985,
    )
    fig.text(
        0.008,
        0.945,
        "LRCC-DVNL (Tang et al. 2025) · boundaries GADM 4.1 · subnational Gini over "
        "light density (SOL/km²), unweighted",
        color=INK_MUTED,
        fontsize=8,
        ha="left",
    )
    fig.text(
        0.008,
        0.012,
        "In this series a lit pixel never dims - it goes out. Gradual decline is "
        "invisible, so a falling Gini is partly imposed; a collapse is real.  "
        f"Source dtype — {eras}.",
        color=INK_MUTED,
        fontsize=7,
        ha="left",
    )

    fig.tight_layout(rect=(0, 0.055, 1, 0.925))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


#: Former name, kept so existing callers keep working.
plot_gini_series = plot_inequality_series


# --------------------------------------------------------------------------- #
# Theil decomposition
# --------------------------------------------------------------------------- #
#: Ordinal ramp: the three nested components are stages of one hierarchy, so
#: they take one hue at increasing lightness rather than three identities.
NESTED_COLORS = ("#1a4b8c", "#3a86d6", "#a8cbf0")
NESTED_LABELS = (
    "between governorates",
    "between delegations, within governorate",
    "within delegations",
)


def plot_decomposition(
    rows,
    out_path: str | Path,
    *,
    iso3: str = "",
    measure: str = "theil_t",
    scope: str = "all",
    break_year: int = 2014,
) -> Path:
    """Stacked composition of the nested Theil split, per zero treatment.

    Stacked because the three parts are exactly a whole - the decomposition is
    additive - so the stack is the identity, not a visual convenience. Shown as
    shares so the composition is readable even as the total halves; the total
    itself is drawn on a companion axis.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    treatments = [
        ("zeros_included", "All land pixels"),
        ("lit_only", "Lit pixels only"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), dpi=200, facecolor=SURFACE)

    for column, (zeros, title) in enumerate(treatments):
        nested = sorted(
            (
                r
                for r in rows
                if r["measure"] == measure
                and r["grouping"] == "nested"
                and r["scope"] == scope
                and r["zeros"] == zeros
            ),
            key=lambda r: r["year"],
        )
        share_ax, total_ax = axes[0][column], axes[1][column]
        for ax in (share_ax, total_ax):
            ax.set_facecolor(SURFACE)
            ax.grid(True, color=GRID, linewidth=0.7)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                ax.spines[side].set_color(GRID)
            ax.tick_params(colors=INK_MUTED, labelsize=8)

        usable = [r for r in nested if r["total"] == r["total"]]
        if not usable:
            share_ax.text(
                0.5,
                0.5,
                f"{measure} undefined\nwith unlit pixels",
                transform=share_ax.transAxes,
                ha="center",
                va="center",
                color=INK_MUTED,
                fontsize=10,
            )
            total_ax.set_axis_off()
            share_ax.set_title(title, color=INK, fontsize=10, loc="left", pad=6)
            continue

        years = [r["year"] for r in usable]
        totals = [r["total"] for r in usable]
        parts = [
            [r["between"] / r["total"] for r in usable],
            [r["between_deleg_within_gov"] / r["total"] for r in usable],
            [r["within"] / r["total"] for r in usable],
        ]
        share_ax.stackplot(
            years,
            *parts,
            colors=NESTED_COLORS,
            labels=NESTED_LABELS,
            edgecolor=SURFACE,
            linewidth=0.6,
        )
        share_ax.set_ylim(0, 1)
        share_ax.set_ylabel("share of total", color=INK_MUTED, fontsize=8)
        share_ax.set_title(title, color=INK, fontsize=10, loc="left", pad=6)

        total_ax.plot(years, totals, color=NESTED_COLORS[0], linewidth=2.0)
        total_ax.set_ylabel(f"total {measure}", color=INK_MUTED, fontsize=8)
        total_ax.set_ylim(bottom=0)

        for ax in (share_ax, total_ax):
            ax.axvline(
                break_year - 0.5,
                color=INK_MUTED,
                linewidth=1.0,
                linestyle=(0, (4, 3)),
            )

    handles, labels = axes[0][0].get_legend_handles_labels()
    legend = fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.005),
    )
    for text in legend.get_texts():
        text.set_color(INK)

    fig.suptitle(
        f"{iso3} nighttime-light inequality: nested Theil decomposition".strip(),
        color=INK,
        fontsize=14,
        fontweight="bold",
        x=0.008,
        ha="left",
        y=0.985,
    )
    fig.text(
        0.008,
        0.945,
        "Pixels nested in delegations nested in governorates · the three parts "
        "sum exactly to the total (Theil is additively decomposable) · dashed "
        "line marks the DMSP→VIIRS handover",
        color=INK_MUTED,
        fontsize=8,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.925))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path
