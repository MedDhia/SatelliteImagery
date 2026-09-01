"""Choropleth maps: administrative units filled by their nighttime-light level.

A different question from the overlay maps. Those show the raster and draw
boundaries on top, so the reader sees where light is. These fill each unit by
its own aggregate, so the reader compares units - which is the thing the Gini
and Theil numbers are computed over. The choropleth is the visual form of the
same table.

Two framings, and they answer different questions:

* **absolute** - the unit's mean DN on a fixed scale shared by every year, so
  1992 and 2022 are directly comparable and growth is visible.
* **relative** - the unit's mean DN divided by the national mean *for that
  year*. Growth is divided out, leaving each unit's standing against its own
  country. This is exactly the quantity the Theil between-group component is
  built from (mu_g / mu), so the map is a picture of that component.

Both framings use one warm sequential ramp, white -> yellow -> orange -> red,
built on the ColorBrewer YlOrRd steps with a white anchor added at the bottom.
Warm-for-bright is the intuitive mapping for light, and using the same ramp for
both framings keeps the figure set on one colour language.

This means the relative maps are rendered sequentially rather than divergingly,
even though the ratio has a real midpoint at 1.0. The trade is deliberate:
consistency across the set over the at-a-glance above/below-average split. The
1.25x break still sits at the class edge either side of the mean, so the
crossover is readable from the legend.

One consequence has to be handled rather than ignored: the lowest class is
white, which is the page colour. Unit edges are therefore drawn in a light
grey, not white - otherwise a unit in the lowest class would have no visible
outline and simply disappear.

Requires the ``overlay`` extra.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence

#: White -> yellow -> orange -> red. ColorBrewer YlOrRd with a white anchor
#: prepended, so the lowest class is the page colour and the top is deep red.
WHITE_YLORRD = (
    "#ffffff",
    "#ffffcc",
    "#ffeda0",
    "#fed976",
    "#feb24c",
    "#fd8d3c",
    "#fc4e2a",
    "#e31a1c",
    "#bd0026",
    "#800026",
)

#: Documented house sequential ramp (palette.md, blue steps 100 -> 700). Kept
#: available for callers that want to stay strictly inside the design system.
HOUSE_BLUE = (
    "#cde2fb",
    "#b7d3f6",
    "#9ec5f4",
    "#86b6ef",
    "#6da7ec",
    "#5598e7",
    "#3987e5",
    "#2a78d6",
    "#256abf",
    "#1c5cab",
    "#184f95",
    "#104281",
    "#0d366b",
)

#: Class breaks on the DN scale for the absolute maps. Fixed, not per-year
#: quantiles: quantile breaks would rescale every year and hide the growth the
#: series exists to show.
DN_BREAKS = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 35.0, 63.0)

#: Ratio breaks for the relative maps, symmetric in log space about 1.0.
RATIO_BREAKS = (0.0, 0.125, 0.25, 0.5, 0.8, 1.25, 2.0, 4.0, 8.0, 1e9)

SURFACE = "#ffffff"
INK = "#1a1a1f"
INK_MUTED = "#6b7280"
#: Light grey, not white: the lowest fill class *is* white, so a white edge
#: would leave those units with no outline at all.
EDGE = "#9ca3af"
MISSING_FILL = "#d1d5db"

ABSOLUTE = "absolute"
RELATIVE = "relative"


def _norm_and_cmap(scale: str, classes: Optional[int] = None):
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap

    if scale == ABSOLUTE:
        breaks = list(DN_BREAKS)
    elif scale == RELATIVE:
        breaks = list(RATIO_BREAKS)
    else:
        raise ValueError(f"scale must be {ABSOLUTE!r} or {RELATIVE!r}, got {scale!r}")
    cmap = LinearSegmentedColormap.from_list(
        "white_ylorrd", list(WHITE_YLORRD), N=len(breaks) - 1
    )
    del classes, plt
    cmap = cmap.copy()
    cmap.set_bad(MISSING_FILL)
    return BoundaryNorm(breaks, len(breaks) - 1), cmap, breaks


def _tick_labels(scale: str, breaks: Sequence[float]) -> Sequence[str]:
    if scale == ABSOLUTE:
        return [f"{b:g}" for b in breaks]
    labels = []
    for b in breaks:
        if b == 0:
            labels.append("0")
        elif b >= 1e8:
            labels.append("")
        elif b < 1:
            labels.append(f"1/{1 / b:g}")
        else:
            labels.append(f"{b:g}×")
    return labels


def render_choropleth(
    units,
    values: Dict[str, float],
    out_path: str | Path,
    *,
    id_field: str,
    scale: str = ABSOLUTE,
    year: Optional[int] = None,
    level_label: str = "",
    iso3: str = "",
    national_mean: Optional[float] = None,
    width_in: float = 6.4,
    dpi: int = 200,
    edge_width: float = 0.3,
) -> Path:
    """Fill each unit by ``values[gid]`` and write a PNG.

    ``values`` maps the unit id to its already-aggregated level - mean DN for
    ``absolute``, or the ratio to the national mean for ``relative``. Units
    missing from the mapping are drawn in a neutral grey and called out in the
    legend, rather than silently reading as the lowest class.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    norm, cmap, breaks = _norm_and_cmap(scale)
    frame = units.copy()
    frame["_value"] = [values.get(str(gid), np.nan) for gid in frame[id_field]]
    missing = int(frame["_value"].isna().sum())

    minx, miny, maxx, maxy = frame.total_bounds
    aspect = (maxy - miny) / (maxx - minx)
    # Reserve the header and footer in inches, not fractions: a tall country
    # (Tunisia is 2.6:1) otherwise leaves the legend band overlapping the map.
    header_in, footer_in = 0.62, 1.18
    map_in = width_in * aspect
    fig_h = map_in + header_in + footer_in
    fig = plt.figure(figsize=(width_in, fig_h), dpi=dpi, facecolor=SURFACE)
    ax = fig.add_axes((0.0, footer_in / fig_h, 1.0, map_in / fig_h))
    ax.set_facecolor(SURFACE)

    frame.plot(
        column="_value",
        ax=ax,
        cmap=cmap,
        norm=norm,
        edgecolor=EDGE,
        linewidth=edge_width,
        missing_kwds={"color": MISSING_FILL, "edgecolor": EDGE},
    )
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    headline = f"{iso3} nighttime lights"
    if year is not None:
        headline += f" {year}"
    if level_label:
        headline += f" · by {level_label}"
    fig.text(
        0.012,
        1.0 - 0.20 * header_in / fig_h,
        headline,
        color=INK,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="left",
    )

    subtitle = (
        "mean DN per unit, fixed scale across years"
        if scale == ABSOLUTE
        else "mean DN relative to the national mean of the same year"
    )
    if scale == RELATIVE and national_mean is not None:
        subtitle += f" (national mean {national_mean:.2f} DN)"
    fig.text(
        0.012,
        1.0 - 0.68 * header_in / fig_h,
        subtitle,
        color=INK_MUTED,
        fontsize=8,
        va="top",
        ha="left",
    )

    bar_ax = fig.add_axes(
        (0.06, 0.55 * footer_in / fig_h, 0.60, 0.22 * footer_in / fig_h)
    )
    bar = fig.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=cmap),
        cax=bar_ax,
        orientation="horizontal",
        spacing="uniform",
    )
    bar.set_ticks(list(breaks))
    bar.set_ticklabels(_tick_labels(scale, breaks))
    bar.ax.tick_params(colors=INK_MUTED, labelsize=6.5, width=0.4, length=2)
    bar.outline.set_edgecolor(INK_MUTED)
    bar.outline.set_linewidth(0.4)
    bar.set_label(
        "mean DN (0–63)" if scale == ABSOLUTE else "× national mean",
        color=INK_MUTED,
        fontsize=7.5,
    )

    note = (
        "LRCC-DVNL · doi:10.7910/DVN/15IKI5 · EPSG:8857 · "
        "boundaries GADM 4.1 (non-commercial)"
    )
    if missing:
        note += f" · {missing} unit(s) without data shown grey"
    fig.text(
        0.012, 0.07 * footer_in / fig_h, note, color=INK_MUTED, fontsize=6.5, ha="left"
    )

    fig.savefig(out_path, dpi=dpi, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def unit_values(
    rows: Sequence[dict],
    year: int,
    *,
    scale: str = ABSOLUTE,
    field: str = "mean_dn",
) -> tuple:
    """Per-unit values for one year, plus that year's national mean.

    The national mean is the light-weighted mean over the units present, i.e.
    total sum of lights over total pixels - not the mean of the per-unit means,
    which would weight a one-pixel delegation like a 39,000 km² governorate.
    """
    selected = [r for r in rows if int(r["year"]) == year]
    if not selected:
        return {}, float("nan")

    total_light = sum(float(r["sum_of_lights"]) for r in selected)
    total_pixels = sum(int(r["pixels"]) for r in selected)
    national = total_light / total_pixels if total_pixels else float("nan")

    values: Dict[str, float] = {}
    for row in selected:
        raw = float(row[field])
        if scale == RELATIVE:
            values[str(row["gid"])] = (
                raw / national if national and national > 0 else float("nan")
            )
        else:
            values[str(row["gid"])] = raw
    return values, national


def render_choropleth_panel(
    units,
    values_by_year: Dict[int, Dict[str, float]],
    out_path: str | Path,
    *,
    id_field: str,
    scale: str = ABSOLUTE,
    level_label: str = "",
    iso3: str = "",
    columns: int = 8,
    tile_in: float = 1.55,
    dpi: int = 200,
) -> Path:
    """Small-multiple panel of choropleths on one shared class scheme.

    The shared scheme is the point: tiles are only comparable across years if
    the class breaks do not move, which is why the breaks are fixed constants
    rather than per-year quantiles.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not values_by_year:
        raise ValueError("render_choropleth_panel needs at least one year")

    norm, cmap, breaks = _norm_and_cmap(scale)
    years = sorted(values_by_year)
    rows = -(-len(years) // columns)

    minx, miny, maxx, maxy = units.total_bounds
    aspect = (maxy - miny) / (maxx - minx)
    fig_w = columns * tile_in
    header_in, footer_in = 0.52, 0.78
    fig_h = rows * tile_in * aspect + header_in + footer_in
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi, facecolor=SURFACE)

    top = 1.0 - header_in / fig_h
    bottom = footer_in / fig_h
    grid_h = top - bottom

    frame = units.copy()
    for index, year in enumerate(years):
        r, c = divmod(index, columns)
        ax = fig.add_axes(
            (c / columns, top - (r + 1) * grid_h / rows, 1.0 / columns, grid_h / rows)
        )
        ax.set_facecolor(SURFACE)
        frame["_value"] = [
            values_by_year[year].get(str(gid), np.nan) for gid in frame[id_field]
        ]
        frame.plot(
            column="_value",
            ax=ax,
            cmap=cmap,
            norm=norm,
            edgecolor=EDGE,
            linewidth=0.08,
            missing_kwds={"color": MISSING_FILL},
        )
        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)
        ax.set_axis_off()
        ax.text(
            0.06,
            0.97,
            str(year),
            transform=ax.transAxes,
            color=INK,
            fontsize=6.5,
            fontweight="bold",
            va="top",
            ha="left",
        )

    label = "mean DN per unit" if scale == ABSOLUTE else "× national mean of that year"
    fig.text(
        0.008,
        1.0 - 0.30 * header_in / fig_h,
        f"{iso3} nighttime lights 1992–2022 · by {level_label} · {label}".strip(),
        color=INK,
        fontsize=12,
        fontweight="bold",
        va="center",
        ha="left",
    )

    bar_ax = fig.add_axes(
        (0.008, 0.50 * footer_in / fig_h, 0.30, 0.16 * footer_in / fig_h)
    )
    bar = fig.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=cmap),
        cax=bar_ax,
        orientation="horizontal",
        spacing="uniform",
    )
    bar.set_ticks(list(breaks))
    bar.set_ticklabels(_tick_labels(scale, breaks))
    bar.ax.tick_params(colors=INK_MUTED, labelsize=6, width=0.4, length=2)
    bar.outline.set_edgecolor(INK_MUTED)
    bar.outline.set_linewidth(0.4)

    fig.text(
        0.35,
        0.55 * footer_in / fig_h,
        "shared class breaks across all years, so tiles are comparable\n"
        "LRCC-DVNL · doi:10.7910/DVN/15IKI5 · boundaries GADM 4.1 (non-commercial)",
        color=INK_MUTED,
        fontsize=6.5,
        va="center",
        ha="left",
        linespacing=1.6,
    )

    fig.savefig(out_path, dpi=dpi, facecolor=SURFACE)
    plt.close(fig)
    return out_path
