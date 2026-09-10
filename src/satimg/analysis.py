"""Country-level nighttime-light inequality series.

Ties the pieces together: :mod:`satimg.regions` for country scoping,
:mod:`satimg.zonal` for per-unit aggregation and :mod:`satimg.inequality` for
the measure itself.

Twelve series are produced per country, all over the same years:

===========  ==============================  ========================
level        scopes                          zero treatment
===========  ==============================  ========================
pixel        all, and each desert exclusion  zeros-in and lit-only
admin-1      all, and each desert exclusion  n/a
admin-2      all, and each desert exclusion  n/a
===========  ==============================  ========================

Pixel series are the distribution of DN over land pixels. Subnational series
are the distribution of **light density** (sum of lights per km²) over units,
unweighted, so a governorate does not score high merely for being large.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import regions as R
from . import zonal as Z
from .inequality import (
    THEIL_L,
    THEIL_T,
    decompose_theil_by_ids,
    gini,
    theil_l,
    theil_t,
)

PIXEL_LEVEL = "pixel"
ZEROS_INCLUDED = "zeros_included"
ZEROS_EXCLUDED = "lit_only"


def build_grids(
    iso3: str,
    reference_raster: str | Path,
    *,
    root: str | Path = R.DEFAULT_ROOT,
    levels: Sequence[int] = R.COUNTRY_LEVELS,
) -> Dict[int, dict]:
    """Prepare each admin level once: layer, units and burned zone raster.

    Every level is burned onto **one shared window**, the union of all their
    extents, because GADM does not guarantee that a country's admin levels
    cover the same ground. The United Kingdom is the case that proved it: its
    ADM_2 "Shetland Islands" unit reaches 17.6 km further north than the
    Scotland ADM_1 polygon that contains it, so deriving each level's window
    from its own bounds gave a 1008-row admin-1 array and a 1026-row admin-2
    one, and the nested decomposition could not combine them.

    A shared window is also the only *safe* arrangement. Two levels whose
    extents differ but whose pixel shapes happen to coincide would broadcast
    without complaint and be silently misaligned - wrong numbers, no error.
    Checked across all 113 analysed countries with an admin-2 layer: only the
    United Kingdom's extents differ at all, and none has that coincidence. The
    guard is here so it stays that way.

    Pixels inside the shared window but outside a given level's units are zone
    0 there, which is what they already were. In the British case that means
    the northern Shetland pixels belong to an admin-2 unit and to no admin-1
    unit, exactly as GADM has it, rather than being quietly reassigned.
    """
    grids: Dict[int, dict] = {}
    prepared = {}
    for level in levels:
        layer = R.country_layer(iso3, level, root=root)
        prepared[level] = (layer, R.load_units(layer))

    shared = country_windows(reference_raster, [u for _, u in prepared.values()])

    for level in levels:
        layer, units = prepared[level]
        id_field, name_field = R.id_fields(level)
        grid = Z.build_zone_grid(
            reference_raster,
            units,
            id_field=id_field,
            name_field=name_field,
            window=shared,
        )
        grids[level] = {"layer": layer, "units": units, "grid": grid}
    return grids


#: Longitude gap, in degrees, that starts a new analysis window.
#:
#: Below this a country is one window and nothing changes. Above it the land is
#: far enough apart that a single lon/lat box would be mostly ocean - or, across
#: the antimeridian, would span the globe.
WINDOW_GAP_DEG = 20.0


def antimeridian_clusters(frame, gap_deg: float = WINDOW_GAP_DEG):
    """Boxes covering a frame's land without crossing 180 degrees.

    Returns a sorted list of ``(min_lon, min_lat, max_lon, max_lat)`` in
    degrees. One entry for almost every country. More where the land is
    scattered, because a flat lon/lat bounding box has no idea the antimeridian
    exists: GADM's ``FJI`` reports -180..180 for a country 500 km across, and
    ``UMI`` reports -178..167 for nine specks, one of which is in the Caribbean.

    The boxes are *measured*, not inferred from a country's own bounds. A unit
    whose bounds straddle the wrap is clipped into its two hemispheres and each
    part contributes its real extent - New Zealand's "Northern Islands" spans
    -178.83..172.17 and Fiji's "Northern" the full -180..180, so their bounds
    alone say nothing useful. Splitting the space rather than assigning each
    unit to a side is what keeps a straddling unit whole: its pixels accumulate
    across windows under the same zone id.

    Each box carries **its own** latitude range, not the country's. Sharing one
    latitude span across windows is what made a two-window United States 100
    megapixels against the 52.6 a plain crop achieved: the 7-degree Aleutian
    sliver inherited the height of a country reaching from Hawaii to the Arctic.
    """
    from shapely.geometry import box as _box

    geo = frame
    if frame.crs is not None and frame.crs.to_epsg() != 4326:
        geo = frame.to_crs("EPSG:4326")

    parts = []
    for geom in geo.geometry:
        if geom is None or geom.is_empty:
            continue
        lo, la, hi, ha = geom.bounds
        if lo < -150 and hi > 150:
            for clip in (_box(-180.0, -90.0, 0.0, 90.0), _box(0.0, -90.0, 180.0, 90.0)):
                piece = geom.intersection(clip)
                if not piece.is_empty:
                    b = piece.bounds
                    parts.append((b[0], b[1], b[2], b[3]))
        else:
            parts.append((lo, la, hi, ha))

    parts.sort()
    merged = []
    for lo, la, hi, ha in parts:
        if merged and lo - merged[-1][2] <= gap_deg:
            m = merged[-1]
            merged[-1] = (m[0], min(m[1], la), max(m[2], hi), max(m[3], ha))
        else:
            merged.append((lo, la, hi, ha))
    return merged


def country_windows(reference_raster, frames, gap_deg: float = WINDOW_GAP_DEG):
    """Analysis windows for a country: one per land cluster, none wrapping.

    Derived from every level's geometry together, so all levels share the same
    window set and their arrays line up - the property ``build_grids`` needs.

    Each window comes from the **projected bounds of the geometry inside that
    cluster**, never from a lon/lat box. Equal Earth compresses x toward the
    poles, so projecting a degree box gives a wider frame than projecting the
    land within it: Australia measured 35.1 megapixels as a box against 22.7 as
    geometry. That also makes the single-cluster case exactly what it has
    always been - clipping to the one cluster is a no-op, so the window equals
    ``window_for(raster, frame.total_bounds)`` and no existing country moves.
    """
    import geopandas as gpd
    from shapely.geometry import box as _box

    geo = []
    for f in frames:
        if not len(f):
            continue
        geo.append(f.to_crs("EPSG:4326") if f.crs.to_epsg() != 4326 else f)
    if not geo:
        raise ValueError("no geometry to build windows from")

    boxes = []
    for f in geo:
        boxes.extend(antimeridian_clusters(f, gap_deg))
    boxes.sort()
    merged = []
    for lo, la, hi, ha in boxes:
        if merged and lo - merged[-1][2] <= gap_deg:
            m = merged[-1]
            merged[-1] = (m[0], min(m[1], la), max(m[2], hi), max(m[3], ha))
        else:
            merged.append((lo, la, hi, ha))

    windows = []
    for lo, la, hi, ha in merged:
        clip = _box(lo, la, hi, ha)
        pieces = []
        for f in geo:
            hit = f[f.geometry.intersects(clip)]
            if len(hit):
                pieces.append(gpd.GeoSeries(hit.geometry.intersection(clip), crs=4326))
        if not pieces:
            continue
        bounds = [p.to_crs("EPSG:8857").total_bounds for p in pieces]
        union = (
            min(b[0] for b in bounds),
            min(b[1] for b in bounds),
            max(b[2] for b in bounds),
            max(b[3] for b in bounds),
        )
        windows.append(Z.window_for(reference_raster, union))
    if not windows:
        raise ValueError("no geometry to build windows from")

    # Overlapping windows would double-count every pixel in the overlap,
    # inflating a unit's pixel count and sum of lights with no error anywhere.
    # The clusters are gap_deg apart so this cannot happen by construction, but
    # `window_for` pads by a pixel and the whole point of this function is that
    # the arithmetic downstream is a plain concatenation - so it is asserted
    # rather than assumed.
    for i, a in enumerate(windows):
        for b in windows[i + 1 :]:
            if _windows_overlap(a, b):
                raise ValueError(
                    f"derived analysis windows overlap ({a} and {b}); pixels in "
                    "the overlap would be counted twice"
                )
    return tuple(windows)


def _windows_overlap(a, b) -> bool:
    ax0, ay0 = int(a.col_off), int(a.row_off)
    ax1, ay1 = ax0 + int(a.width), ay0 + int(a.height)
    bx0, by0 = int(b.col_off), int(b.row_off)
    bx1, by1 = bx0 + int(b.width), by0 + int(b.height)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _excluded_zone_indices(units, level: int, iso3: str, scope: str):
    """1-based zone ids to drop for a scope, matching build_zone_grid's ids."""
    excluded = R.excluded_gid1(iso3, scope)
    if not excluded:
        return set()
    parents = R.parent_gid1(units, level)
    if parents is None:
        return set()
    return {i + 1 for i, gid in enumerate(parents) if gid in excluded}


def gini_series(
    iso3: str,
    rasters: Iterable[Tuple[int, Path]],
    *,
    root: str | Path = R.DEFAULT_ROOT,
    min_pixels: int = 0,
    levels: Sequence[int] = R.COUNTRY_LEVELS,
) -> Tuple[List[dict], Dict[int, List[dict]]]:
    """Compute every Gini series, plus the per-unit zonal tables behind them.

    ``min_pixels`` drops subnational units smaller than that many pixels, for
    the sensitivity run; 0 keeps all of them.
    """
    import numpy as np

    rasters = list(rasters)
    if not rasters:
        raise ValueError("no rasters given")
    # Drop levels GADM does not have for this country (Libya has no ADM_2)
    # rather than failing on an empty layer part-way through.
    levels, _ = R.resolve_levels(iso3, levels)
    grids = build_grids(iso3, rasters[0][1], root=root, levels=levels)
    scopes = R.scope_keys(iso3)

    # Pixel membership comes from the admin-1 grid: it defines both "inside the
    # country" and which governorate a pixel belongs to, so pixel-level scopes
    # line up exactly with the subnational ones.
    adm1 = grids[1]
    adm1_ids = adm1["grid"].ids
    pixel_masks = {}
    for scope in scopes:
        drop = _excluded_zone_indices(adm1["units"], 1, iso3, scope)
        mask = adm1_ids > 0
        if drop:
            mask &= ~np.isin(adm1_ids, list(drop))
        pixel_masks[scope] = mask

    rows: List[dict] = []
    tables: Dict[int, List[dict]] = {}

    # --- subnational levels -------------------------------------------------
    for level in (lv for lv in levels if lv >= 1):
        entry = grids[level]
        table = Z.zonal_table(rasters, entry["grid"])
        tables[level] = table
        by_year: Dict[int, List[dict]] = {}
        for row in table:
            by_year.setdefault(row["year"], []).append(row)

        for scope in scopes:
            drop = _excluded_zone_indices(entry["units"], level, iso3, scope)
            dropped_gids = {entry["grid"].gids[i - 1] for i in drop}
            for year, unit_rows in sorted(by_year.items()):
                kept = [
                    r
                    for r in unit_rows
                    if r["gid"] not in dropped_gids and r["pixels"] >= min_pixels
                ]
                density = [r["density_sol_per_km2"] for r in kept]
                total = sum(r["sum_of_lights"] for r in kept)
                rows.append(
                    {
                        "year": year,
                        "level": f"adm{level}",
                        "level_label": R.level_title(iso3, level),
                        "scope": scope,
                        "zeros": "",
                        "n": len(kept),
                        "gini": gini(density) if density else float("nan"),
                        "theil_t": theil_t(density) if density else float("nan"),
                        "theil_l": theil_l(density) if density else float("nan"),
                        "sum_of_lights": total,
                        "lit_share": float("nan"),
                    }
                )

    # --- pixel level --------------------------------------------------------
    for year, path in rasters:
        values, signature = Z.read_window(path, adm1["grid"].read_windows)
        if not Z.grids_compatible(signature, adm1["grid"].signature):
            raise ValueError(f"{path} is on a different grid than the zone raster")
        for scope in scopes:
            inside = pixel_masks[scope] & ~np.isnan(values)
            v = values[inside]
            lit = v[v > 0]
            lit_share = float(lit.size / v.size) if v.size else float("nan")
            for zeros, sample in (
                (ZEROS_INCLUDED, v),
                (ZEROS_EXCLUDED, lit),
            ):
                rows.append(
                    {
                        "year": year,
                        "level": PIXEL_LEVEL,
                        "level_label": "pixel (1 km)",
                        "scope": scope,
                        "zeros": zeros,
                        "n": int(sample.size),
                        "gini": gini(sample),
                        "theil_t": theil_t(sample),
                        "theil_l": theil_l(sample),
                        "sum_of_lights": float(v.sum()),
                        "lit_share": lit_share,
                    }
                )

    rows.sort(key=lambda r: (r["level"], r["scope"], r["zeros"], r["year"]))
    return rows, tables


def decomposition_series(
    iso3: str,
    rasters: Iterable[Tuple[int, Path]],
    *,
    root: str | Path = R.DEFAULT_ROOT,
) -> Tuple[List[dict], List[dict]]:
    """Between/within decomposition of pixel-level Theil, per year and scope.

    Two groupings of the same pixels - governorates and delegations - plus the
    nested three-way split they permit. Delegations nest exactly inside
    governorates here (verified: the two zone rasters agree on all 154,885
    Tunisian pixels), and the governorate label is derived from each
    delegation's ``GID_1`` so the nesting is exact by construction rather than
    by coincidence of two independent rasterisations.

    Returns ``(summary_rows, group_rows)``: the additive split, and each unit's
    own index and within-contribution.
    """
    import numpy as np

    rasters = list(rasters)
    if not rasters:
        raise ValueError("no rasters given")

    # Libya has no ADM_2 in GADM 4.1, so the nested three-way split is simply
    # unavailable there. Reporting the two-way pixel -> admin-1 split is the
    # honest outcome; inventing a second tier would not be.
    levels, _ = R.resolve_levels(iso3, (1, 2))
    nested = 2 in levels
    grids = build_grids(iso3, rasters[0][1], root=root, levels=levels)
    adm1 = grids[1]
    ids1 = adm1["grid"].ids

    outer_label = R.level_title(iso3, 1)
    inner_label = R.level_title(iso3, 2) if nested else None

    if nested:
        adm2 = grids[2]
        ids2 = adm2["grid"].ids
        # Admin-1 id implied by each admin-2 unit, so the hierarchy nests
        # exactly rather than by coincidence of two rasterisations.
        outer_index = {gid: i + 1 for i, gid in enumerate(adm1["grid"].gids)}
        parents = R.parent_gid1(adm2["units"], 2)
        inner_to_outer = np.zeros(adm2["grid"].count + 1, dtype=np.int64)
        for i, parent in enumerate(parents):
            inner_to_outer[i + 1] = outer_index.get(parent, 0)
        nested_outer_ids = inner_to_outer[ids2]
    else:
        nested_outer_ids = ids1

    scopes = R.scope_keys(iso3)
    pixel_masks = {}
    for scope in scopes:
        drop = _excluded_zone_indices(adm1["units"], 1, iso3, scope)
        mask = ids1 > 0
        if drop:
            mask &= ~np.isin(ids1, list(drop))
        pixel_masks[scope] = mask

    groupings = [
        (outer_label, nested_outer_ids, adm1["grid"].count, adm1["grid"].names),
    ]
    if nested:
        groupings.append((inner_label, ids2, adm2["grid"].count, adm2["grid"].names))

    summary: List[dict] = []
    group_rows: List[dict] = []

    for year, path in rasters:
        values, signature = Z.read_window(path, adm1["grid"].read_windows)
        if not Z.grids_compatible(signature, adm1["grid"].signature):
            raise ValueError(f"{path} is on a different grid than the zone raster")
        clean = np.nan_to_num(values, nan=0.0)

        for scope in scopes:
            base = pixel_masks[scope] & ~np.isnan(values)
            # Theil L needs strictly positive values, and 55-86% of Tunisian
            # pixels are unlit, so the zeros-included L is genuinely undefined.
            # The lit-only pass is where L becomes usable.
            for zeros, keep in (
                (ZEROS_INCLUDED, base),
                (ZEROS_EXCLUDED, base & (values > 0)),
            ):
                for measure in (THEIL_T, THEIL_L):
                    parts = {}
                    for label, ids, count, names in groupings:
                        scoped_ids = np.where(keep, ids, 0)
                        decomposition = decompose_theil_by_ids(
                            clean, scoped_ids, count, measure, keys=names
                        )
                        parts[label] = decomposition
                        summary.append(
                            {
                                "year": year,
                                "scope": scope,
                                "zeros": zeros,
                                "measure": measure,
                                "grouping": label,
                                "total": decomposition.total,
                                "between": decomposition.between,
                                "within": decomposition.within,
                                "between_share": decomposition.between_share,
                                "within_share": decomposition.within_share,
                                "between_deleg_within_gov": float("nan"),
                                "residual": decomposition.residual(),
                                "n_groups": len(decomposition.groups),
                            }
                        )
                        if measure == THEIL_T:
                            for part in decomposition.groups:
                                group_rows.append(
                                    {
                                        "year": year,
                                        "scope": scope,
                                        "zeros": zeros,
                                        "grouping": label,
                                        "unit": part.key,
                                        "pixels": part.n,
                                        "mean_dn": part.mean,
                                        "population_share": part.population_share,
                                        "value_share": part.value_share,
                                        "theil_t": part.index,
                                        "within_contribution": part.within_contribution,
                                    }
                                )

                    if not nested:
                        continue
                    outer, inner = parts[outer_label], parts[inner_label]
                    summary.append(
                        {
                            "year": year,
                            "scope": scope,
                            "zeros": zeros,
                            "measure": measure,
                            "grouping": "nested",
                            "total": inner.total,
                            "between": outer.between,
                            "within": inner.within,
                            "between_share": (
                                outer.between / inner.total
                                if inner.total
                                else float("nan")
                            ),
                            "within_share": (
                                inner.within / inner.total
                                if inner.total
                                else float("nan")
                            ),
                            "between_deleg_within_gov": inner.between - outer.between,
                            "residual": abs(
                                inner.total
                                - (
                                    outer.between
                                    + (inner.between - outer.between)
                                    + inner.within
                                )
                            ),
                            "n_groups": len(inner.groups),
                        }
                    )
    summary.sort(
        key=lambda r: (r["measure"], r["grouping"], r["zeros"], r["scope"], r["year"])
    )
    return summary, group_rows


def cell(value):
    """What a value looks like in a published CSV.

    A non-finite float has no printable value, and ``csv`` writes the literal
    ``nan`` - a string ``float()`` accepts without complaint and ``sorted``
    then mis-orders, so a median over the column comes back *wrong* rather
    than absent. Oceania's read 63.0, the DN ceiling, for a pool whose units
    are mostly below 1.0.

    Blank is the encoding this repository already uses for a cell that does
    not apply, and :func:`number` reads it back as the NaN it was, so nothing
    computed changes.
    """
    try:
        finite = math.isfinite(value)
    except TypeError:  # a string, None, anything not a number
        return value
    return value if finite else ""


def number(value):
    """The float in a published cell; NaN where there is no measurement.

    The inverse of :func:`cell`. A blank means the quantity does not apply -
    Theil L where a unit has zero light, a half-life where the trend rises,
    the nested split where there is no nesting - and NaN is what every caller
    here read back when that cell still said ``nan``.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


#: Column order of the per-unit contribution table. Named rather than taken
#: from ``rows[0]`` because a country can legitimately produce no rows at all:
#: Tokelau's 17 pixels are unlit in all 31 years, so it has no lit unit to
#: contribute anything, and a zero-byte file cannot be told apart from a
#: failed write. With the schema stated, the table is written header-only and
#: says what it would have contained.
GROUP_ROW_FIELDS: Tuple[str, ...] = (
    "year",
    "scope",
    "zeros",
    "grouping",
    "unit",
    "pixels",
    "mean_dn",
    "population_share",
    "value_share",
    "theil_t",
    "within_contribution",
)


def write_csv(
    rows: Sequence[dict], path: str | Path, fields: Optional[Sequence] = None
):
    """Write row dicts to CSV, creating parent directories."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fields:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(fields) if fields else list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: cell(v) for k, v in row.items()})
    return path
