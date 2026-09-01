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

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import regions as R
from . import zonal as Z
from .inequality import gini

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
    """Prepare each admin level once: layer, units and burned zone raster."""
    grids: Dict[int, dict] = {}
    for level in levels:
        layer = R.country_layer(iso3, level, root=root)
        units = R.load_units(layer)
        id_field, name_field = R.id_fields(level)
        grid = Z.build_zone_grid(
            reference_raster, units, id_field=id_field, name_field=name_field
        )
        grids[level] = {"layer": layer, "units": units, "grid": grid}
    return grids


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
                        "level_label": R.LEVEL_TITLES[level],
                        "scope": scope,
                        "zeros": "",
                        "n": len(kept),
                        "gini": gini(density) if density else float("nan"),
                        "sum_of_lights": total,
                        "lit_share": float("nan"),
                    }
                )

    # --- pixel level --------------------------------------------------------
    for year, path in rasters:
        values, signature = Z.read_window(path, adm1["grid"].window)
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
                        "sum_of_lights": float(v.sum()),
                        "lit_share": lit_share,
                    }
                )

    rows.sort(key=lambda r: (r["level"], r["scope"], r["zeros"], r["year"]))
    return rows, tables


def write_csv(
    rows: Sequence[dict], path: str | Path, fields: Optional[Sequence] = None
):
    """Write row dicts to CSV, creating parent directories."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(fields) if fields else list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path
