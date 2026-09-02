"""Charts for the country inequality series.

Faceted rather than a single axes: twelve lines on one plot would be
unreadable, and the four facets each carry three scope lines - few enough that
the categorical hues stay far apart under colour-vision deficiency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

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

#: (level, zero treatment) pairs. The subnational titles are built per country
#: at draw time: "Delegation" is Tunisia's word, and stamping it on a Syrian or
#: Algerian chart is the same error as labelling Algeria's communes "daira".
FACET_SPEC = [
    ("pixel", "zeros_included", "Pixel (1 km), all land pixels"),
    ("pixel", "lit_only", "Pixel (1 km), lit pixels only"),
    ("adm1", "", None),
    ("adm2", "", None),
]


def facets(iso3: str):
    """Facet definitions with this country's own words for its admin levels."""
    from . import regions as R

    out = []
    for level, zeros, title in FACET_SPEC:
        if title is not None:
            out.append((level, zeros, title))
            continue
        depth = int(level[-1])
        if not R.has_level(iso3, depth):
            continue
        word = R.level_title(iso3, depth)
        out.append((level, zeros, f"{word.capitalize()}, light density"))
    return out


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

    panels = facets(iso3)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.4), dpi=200, facecolor=SURFACE)
    axes = axes.ravel()
    # A country with no admin-2 layer gets three facets, not a blank fourth.
    for ax in axes[len(panels) :]:
        ax.set_axis_off()

    for ax, (level, zeros, title) in zip(axes, panels):
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


class NoNestedHierarchy(Exception):
    """Raised when a country has no admin-2 layer to nest inside admin-1.

    Drawing the chart anyway produces two empty axes captioned "theil_t
    undefined with unlit pixels" - a true-sounding statement about the wrong
    thing. The honest output is no file, and a caller that says why.
    """


def nested_labels(iso3: str):
    """Component labels in the country's own admin vocabulary."""
    from . import regions as R

    outer, inner = R.level_title(iso3, 1), R.level_title(iso3, 2)
    return (
        f"between {outer}s",
        f"between {inner}s, within {outer}",
        f"within {inner}s",
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
    from . import regions as R

    if not R.has_level(iso3, 2):
        raise NoNestedHierarchy(
            f"GADM 4.1 has no admin-2 layer for {iso3}, so there is no nested "
            "hierarchy to decompose"
        )

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
            labels=nested_labels(iso3),
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
        f"Pixels nested in {R.level_title(iso3, 2)}s nested in "
        f"{R.level_title(iso3, 1)}s · the three parts sum exactly to the total "
        "(Theil is additively decomposable) · dashed line marks the DMSP→VIIRS "
        "handover",
        color=INK_MUTED,
        fontsize=8,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.925))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


#: The two ends of the dumbbell. Two series, so hue carries identity and a
#: legend is mandatory; both are slots from the same fixed order as SCOPE_COLORS
#: and validated as an all-pairs set.
PACE_COLORS = {
    "total": "#2a78d6",
    "intensive": "#eb6834",
}
PACE_LABELS = {
    "total": "all land pixels (total)",
    "intensive": "lit pixels only (intensive margin)",
}

PACE_SPANS = {"full": "1992–2022", "dmsp": "1992–2013", "viirs": "2014–2022"}


def _pace_rows(rows, measure: str, window: str):
    return {
        row["iso3"]: row
        for row in rows
        if row["measure"] == measure and row["window"] == window
    }


def _wrapped(text: str, width: int) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width))


def plot_pace_dumbbell(
    rows,
    out_path: str | Path,
    *,
    window: str = "full",
) -> Path:
    """Total vs lit-only pace of Theil T change, one row per country.

    A dumbbell rather than two bar charts: the reader's question is the *gap*
    between the two ends - how much of a country's falling inequality is
    convergence among places that already had light, and how much is light
    simply arriving somewhere new. A gap is read directly off a connector and
    only inferred from paired bars.

    Emphasis is carried by the label ink, not by a third hue: countries whose
    lit-only rate is positive - inequality rising among the already-lit - are
    the finding, and their names are set in primary ink while the rest recede.
    A hollow marker is the second non-colour channel, and marks a fit whose
    R-squared is too low for one slope to describe the series.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from . import figures as F
    from . import trends as T

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = _pace_rows(rows, "total", window)
    intensive = _pace_rows(rows, "intensive", window)

    items = []
    for iso3, row in total.items():
        other = intensive.get(iso3)
        if other is None:
            continue
        a, b = float(row["percent_per_year"]), float(other["percent_per_year"])
        if a != a or b != b:  # nan: no usable fit on one end
            continue
        items.append(
            {
                "iso3": iso3,
                "total": a,
                "intensive": b,
                "total_monotone": str(row["monotone"]) == "True",
                "intensive_monotone": str(other["monotone"]) == "True",
            }
        )
    if not items:
        raise ValueError(f"no country has both ends fit over the {window} window")
    items.sort(key=lambda d: d["total"])

    # The title, subtitle and footnote take a fixed slab of inches, so a
    # short chart still needs a floor or they crowd out the plot.
    height = max(4.5, 2.4 + 0.34 * len(items))
    fig, ax = plt.subplots(figsize=(10.5, height), dpi=200, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    ys = list(range(len(items)))
    for y, item in zip(ys, items):
        ax.plot(
            [item["total"], item["intensive"]],
            [y, y],
            color=GRID,
            linewidth=2.0,
            solid_capstyle="round",
            zorder=1,
        )
        for key in ("total", "intensive"):
            ax.plot(
                [item[key]],
                [y],
                marker="o",
                markersize=8,
                markerfacecolor=(
                    PACE_COLORS[key] if item[f"{key}_monotone"] else SURFACE
                ),
                markeredgecolor=PACE_COLORS[key],
                markeredgewidth=2.0,
                linestyle="none",
                zorder=3,
                label=PACE_LABELS[key] if y == 0 else None,
            )

    ax.axvline(0, color=INK_MUTED, linewidth=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels(
        [F.COUNTRY_NAMES.get(item["iso3"], item["iso3"]) for item in items]
    )
    for label, item in zip(ax.get_yticklabels(), items):
        rising = item["intensive"] > 0
        label.set_color(INK if rising else INK_MUTED)
        label.set_fontweight("bold" if rising else "normal")
    ax.set_ylim(-0.7, len(items) - 0.3)

    ax.set_xlabel("change in Theil T, % per year", color=INK_MUTED, fontsize=9)
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=8.5)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    legend = ax.legend(
        loc="lower right",
        frameon=False,
        fontsize=9,
        numpoints=1,
        handletextpad=0.4,
    )
    for text in legend.get_texts():
        text.set_color(INK)

    top = 1.0 - 0.30 / height
    fig.suptitle(
        "How fast is nighttime-light inequality falling — and is it convergence?",
        color=INK,
        fontsize=13.5,
        fontweight="bold",
        x=0.008,
        ha="left",
        y=top,
    )
    fig.text(
        0.008,
        top - 0.42 / height,
        _wrapped(
            "Log-linear rate of change in Theil T, "
            f"{PACE_SPANS.get(window, window)}. Left of the line is falling "
            "inequality. A bold name marks a country whose lit-only end sits "
            "right of zero: inequality among places that already had light is "
            "rising there, so whatever fall the total shows is light reaching "
            "new ground, not places growing closer together.",
            150,
        ),
        color=INK_MUTED,
        fontsize=8.5,
        ha="left",
        va="top",
        linespacing=1.5,
    )
    fig.text(
        0.008,
        0.34 / height,
        _wrapped(
            "A hollow marker marks a fit with R² below "
            f"{T.MONOTONE_R2:g} — one slope does not describe that series, so "
            "read it as a direction, not a pace. A lit pixel in this series "
            "never dims, it goes out, so a falling total is partly imposed; "
            "that is exactly why the lit-only end is drawn beside it. Rates "
            "either side of the 2014 sensor handover are not comparable.",
            150,
        ),
        color=INK_MUTED,
        fontsize=7.5,
        ha="left",
        va="bottom",
        linespacing=1.5,
    )
    fig.tight_layout(rect=(0, 0.80 / height, 1, top - 0.85 / height))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# aridity against darkness
# --------------------------------------------------------------------------- #
#: Emphasis form: one accent, graded, plus a de-emphasis grey. The three accent
#: steps are an *ordinal* ramp of the same hue - a unit's step says at which
#: darkness cut it joins the anomalous set, which is ordered information, not
#: identity. Validated as an ordinal ramp against this surface.
ANOMALY_TIERS = ("#104281", "#2a78d6", "#86b6ef")

#: Everything that is not the story. Deliberately achromatic: in an emphasis
#: chart the context is meant to read as "not a series".
CONTEXT = "#898781"

#: Rows, most-arid first. Bounds are exact because the variable is: half the
#: units are wholly desert and a sixth are wholly not.
ARIDITY_BANDS = (
    ("fully arid", lambda s: s == 1.0),
    ("partly arid", lambda s: 0.0 < s < 1.0),
    ("not arid", lambda s: s == 0.0),
)

#: Below this the axis is log-scaled; one unit sits at exactly 0 and is drawn
#: on the floor line rather than dropped or given a broken axis of its own.
AXIS_FLOOR = 0.0005


def _swarm(values, half_width: float, bins: int = 64):
    """Vertical offsets that spread coincident points without moving them on x.

    A dot-density layout, not jitter: the offset encodes how many units share
    a neighbourhood, and is symmetric about the row. Honest here only because
    the vertical axis is a category - on a share axis this would misstate
    position, which is why the earlier scatter design was abandoned.
    """
    import math

    if not values:
        return []
    lo = math.log10(max(min(values), AXIS_FLOOR))
    hi = math.log10(max(max(values), AXIS_FLOOR * 10))
    span = (hi - lo) or 1.0
    seen: Dict[int, int] = {}
    offsets = []
    for value in values:
        slot = int((math.log10(max(value, AXIS_FLOOR)) - lo) / span * (bins - 1))
        rank = seen.get(slot, 0)
        seen[slot] = rank + 1
        # 0, +1, -1, +2, -2 ... so a stack grows evenly either side of the row.
        step = (rank + 1) // 2 * (1 if rank % 2 else -1)
        offsets.append(step)
    tallest = max(abs(o) for o in offsets) or 1
    return [o / tallest * half_width for o in offsets]


def plot_aridity_bands(
    rows,
    out_path: str | Path,
    *,
    cuts=None,
) -> Path:
    """Light against climate, as three aridity bands on one log axis.

    Not a scatter, deliberately. ``desert_share`` cannot carry a continuous
    axis - 156 of 317 units sit at exactly 1.0 and 54 at exactly 0.0 - and,
    more decisively, the relationship is a **step rather than a slope**: median
    2022 mean DN is 14.1 where nothing is arid against 3.8 and 3.7 for the two
    arid bands, which are indistinguishable from each other. A scatter can only
    encode "weak"; it would draw a monotone drift the data does not contain.

    The anomalous set - non-arid yet dark - has no crisp boundary, so its
    members are shaded by *which cut they enter at* rather than flagged as
    members. The sets are strictly nested, and only the six that survive the
    tightest cut are named.
    """
    import statistics

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from . import aridity as A

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [dict(r) for r in rows]
    if not rows:
        raise ValueError("no units to draw; run `satimg aridity vs-light` first")
    for row in rows:
        row["desert_share"] = float(row["desert_share"])
        row["mean_dn_2022"] = float(row["mean_dn_2022"])
        row["majority_arid"] = str(row["majority_arid"]) == "True"

    quantiles = cuts if cuts is not None else A.DARK_QUANTILES
    values = [r["mean_dn_2022"] for r in rows]
    cut_at = [A.dark_cut(values, q) for q in quantiles]

    def tier_of(row) -> Optional[int]:
        """Which cut this unit joins the anomalous set at, if it ever does."""
        if row["majority_arid"]:
            return None
        for index, cut in enumerate(cut_at):
            if row["mean_dn_2022"] < cut:
                return index
        return None

    for row in rows:
        row["tier"] = tier_of(row)

    fig, ax = plt.subplots(figsize=(11.0, 6.4), dpi=200, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    half = 0.34
    centres = {}
    for index, (label, predicate) in enumerate(ARIDITY_BANDS):
        centre = len(ARIDITY_BANDS) - 1 - index
        centres[label] = centre
        band = [r for r in rows if predicate(r["desert_share"])]
        band.sort(key=lambda r: r["mean_dn_2022"])
        xs = [max(r["mean_dn_2022"], AXIS_FLOOR) for r in band]
        offsets = _swarm(xs, half)

        for row, x, dy in zip(band, xs, offsets):
            tier = row["tier"]
            ax.plot(
                [x],
                [centre + dy],
                marker="o",
                markersize=5.5 if tier is None else 6.5,
                markerfacecolor=CONTEXT if tier is None else ANOMALY_TIERS[tier],
                markeredgecolor=SURFACE,
                markeredgewidth=0.6,
                linestyle="none",
                alpha=0.75 if tier is None else 1.0,
                zorder=2 if tier is None else 4,
            )

        # statistics.median, not the upper-middle element: for an even-sized
        # band the two differ, and this number is quoted in the docs.
        median = statistics.median(r["mean_dn_2022"] for r in band)
        ax.plot(
            [median, median],
            [centre - half - 0.10, centre + half + 0.10],
            color=INK,
            linewidth=2.0,
            zorder=5,
            solid_capstyle="butt",
        )
        ax.text(
            median,
            centre + half + 0.15,
            f"median {median:.1f}",
            color=INK,
            fontsize=8,
            ha="center",
            va="bottom",
            zorder=6,
        )

    for cut, quantile in zip(cut_at, quantiles):
        count = sum(
            1 for r in rows if not r["majority_arid"] and r["mean_dn_2022"] < cut
        )
        ax.axvline(cut, color=INK_MUTED, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
        ax.text(
            cut,
            -0.72,
            f"p{round(quantile * 100)}\n{count} units",
            color=INK_MUTED,
            fontsize=7.5,
            ha="center",
            va="top",
        )

    # Only the units that survive the tightest cut are named. Labels hang
    # below their own band - above it would place them inside the band above,
    # where they would read as belonging to units they have nothing to do with.
    bottom = ARIDITY_BANDS[-1][0]
    by_band: Dict[str, List[dict]] = {}
    for row in sorted(
        (r for r in rows if r["tier"] == 0), key=lambda r: r["mean_dn_2022"]
    ):
        band = next(label for label, pred in ARIDITY_BANDS if pred(row["desert_share"]))
        by_band.setdefault(band, []).append(row)

    for band, members in by_band.items():
        up = band == bottom
        for order, row in enumerate(members):
            step = 26 + 12 * (order % 3)
            ax.annotate(
                row["name"],
                xy=(max(row["mean_dn_2022"], AXIS_FLOOR), centres[band]),
                xytext=(0, step if up else -step),
                textcoords="offset points",
                color=ANOMALY_TIERS[0],
                fontsize=7.5,
                ha="center",
                va="bottom" if up else "top",
                zorder=7,
                arrowprops={
                    "arrowstyle": "-",
                    "color": ANOMALY_TIERS[0],
                    "linewidth": 0.6,
                    "shrinkA": 1,
                    "shrinkB": 3,
                },
            )

    ax.set_xscale("log")
    ax.set_xlim(AXIS_FLOOR * 0.7, 100)
    ax.set_ylim(-1.15, len(ARIDITY_BANDS) - 0.25)
    ax.set_yticks([centres[label] for label, _ in ARIDITY_BANDS])
    ax.set_yticklabels(
        [
            f"{label}\nn={sum(1 for r in rows if pred(r['desert_share']))}"
            for label, pred in ARIDITY_BANDS
        ]
    )
    ax.tick_params(axis="y", length=0, labelsize=9, colors=INK)
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=8.5)
    ax.set_xlabel(
        "mean DN over the unit's land pixels, 2022 (log scale)",
        color=INK_MUTED,
        fontsize=9,
    )
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    fig.suptitle(
        "Dark because it is desert, or dark for other reasons?",
        color=INK,
        fontsize=13.5,
        fontweight="bold",
        x=0.008,
        ha="left",
        y=0.985,
    )
    fig.text(
        0.008,
        0.930,
        _wrapped(
            "Every admin-1 unit in the 22 Arab League countries, by how much of "
            "its area is desert. Aridity barely predicts light: the two arid "
            "bands are indistinguishable from each other, and the whole "
            "relationship is one step at 'not arid at all'. Shaded units are "
            "dark despite not being majority-desert — darker shading means they "
            "stay in that set at a tighter darkness cut.",
            132,
        ),
        color=INK_MUTED,
        fontsize=8.5,
        ha="left",
        va="top",
        linespacing=1.5,
    )
    fig.text(
        0.008,
        0.018,
        _wrapped(
            "Vertical spread within a band is a dot-density stack showing how "
            "many units share a neighbourhood; it carries no value. Cuts are "
            "percentiles of the pooled 2022 distribution, compared strictly "
            "below, and the sets they define are strictly nested. Somalia's "
            "Bakool has no lit pixels at all in 2022 and is drawn on the axis "
            "floor. Mean DN is not a per-km² density.",
            140,
        ),
        color=INK_MUTED,
        fontsize=7.5,
        ha="left",
        va="bottom",
        linespacing=1.5,
    )
    fig.tight_layout(rect=(0, 0.085, 1, 0.87))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path
