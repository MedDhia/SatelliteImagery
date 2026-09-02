"""Per-unit aggregation of a raster over administrative zones.

Every year of LRCC-DVNL shares one grid, so the zone-id raster is built once
and reused across the whole series - the same trick the boundary mask uses.
Rasterizing 268 delegations 31 times over would dominate the runtime otherwise.

Zones are burned with ``all_touched=False`` so each pixel belongs to exactly
one unit. That matters twice over: it keeps the per-unit sums a true partition
(so they add back to the national total), and it was measured to leave every
Tunisian delegation with at least one pixel, whereas ``all_touched=True``
starved one unit to zero by overwriting it with a neighbour.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .raster import _require_numpy, _require_rasterio

#: Origins may disagree between years by floating-point noise in the stored
#: geotransform. Measured across the LRCC-DVNL series, the series falls into
#: three groups differing by at most 4e-4 m - 4e-7 of a 1000 m pixel. Treat
#: grids as the same when origins agree to within a centimetre; a genuine
#: half-pixel shift is 500 m and is nowhere near this.
#: Sentinel so ``read_window`` can tell "no nodata argument" from ``None``,
#: which legitimately means "this raster has no fill value at all".
_UNSET = object()

GRID_TOLERANCE_M = 0.01


def grids_compatible(a, b, tol_m: float = GRID_TOLERANCE_M) -> bool:
    """Whether two ``(width, height, transform)`` signatures address one grid.

    Exact equality would be wrong here: it would force the zone raster to be
    rebuilt three times over the series for sub-millimetre differences that
    cannot move a single pixel.
    """
    if a is None or b is None:
        return False
    (wa, ha, ta), (wb, hb, tb) = a, b
    if (wa, ha) != (wb, hb):
        return False
    # Pixel size and rotation must match exactly; only the origin may drift.
    if (ta.a, ta.b, ta.d, ta.e) != (tb.a, tb.b, tb.d, tb.e):
        return False
    return abs(ta.c - tb.c) <= tol_m and abs(ta.f - tb.f) <= tol_m


@dataclass(frozen=True)
class ZoneGrid:
    """Zone ids burned onto a raster window, plus the unit index they map to."""

    ids: object  # np.ndarray of int32; 0 means "outside every unit"
    gids: List[str]
    names: List[str]
    areas_km2: List[float]
    window: object  # rasterio Window covering the units' extent
    transform: object
    signature: Tuple

    @property
    def count(self) -> int:
        return len(self.gids)

    def pixels_per_zone(self):
        np = _require_numpy()
        return np.bincount(self.ids.ravel(), minlength=self.count + 1)[1:]


def window_for(raster_path: str | Path, bounds: Sequence[float], pad: int = 1):
    """Raster window covering ``bounds``, clipped to the raster and padded."""
    rasterio = _require_rasterio()
    from rasterio.windows import Window, from_bounds

    with rasterio.open(raster_path) as src:
        w = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        col_off = max(0, int(w.col_off) - pad)
        row_off = max(0, int(w.row_off) - pad)
        width = min(int(w.width) + 2 * pad, src.width - col_off)
        height = min(int(w.height) + 2 * pad, src.height - row_off)
        return Window(col_off, row_off, width, height)


def build_zone_grid(
    raster_path: str | Path,
    frame,
    *,
    id_field: str,
    name_field: Optional[str] = None,
) -> ZoneGrid:
    """Burn a GeoDataFrame's units onto the raster grid, once."""
    rasterio = _require_rasterio()
    np = _require_numpy()
    from rasterio.features import rasterize

    # areas_km2 below divides a planar area by 1e6, which is only metres-squared
    # in a projected CRS. In EPSG:4326 it would silently emit square degrees
    # scaled by 1e-6 - Tunisia would read 1.59e-5 "km2" - and every density
    # derived from it would be off by ten orders of magnitude while still
    # looking like a number. Refuse rather than return a poisoned field.
    if getattr(frame.crs, "is_geographic", False):
        raise ValueError(
            "build_zone_grid needs a projected CRS: areas would be square "
            f"degrees, not km2 (got {frame.crs}). Reproject the frame, or use "
            "satimg.aridity for geographic-grid work, which weights rows by "
            "true cell area instead."
        )

    frame = frame.reset_index(drop=True)
    window = window_for(raster_path, frame.total_bounds)

    with rasterio.open(raster_path) as src:
        transform = src.window_transform(window)
        shape = (int(window.height), int(window.width))
        signature = (src.width, src.height, src.transform)

    ids = rasterize(
        ((geom, i + 1) for i, geom in enumerate(frame.geometry)),
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="int32",
    )

    names = (
        frame[name_field].astype(str).tolist()
        if name_field and name_field in frame.columns
        else frame[id_field].astype(str).tolist()
    )
    return ZoneGrid(
        ids=ids.astype(np.int32),
        gids=frame[id_field].astype(str).tolist(),
        names=names,
        areas_km2=(frame.geometry.area / 1e6).tolist(),
        window=window,
        transform=transform,
        signature=signature,
    )


def read_window(raster_path: str | Path, window, *, nodata=_UNSET):
    """Read band 1 over a window as float64, with nodata as NaN.

    ``nodata`` must be given when the file declares none. This used to fall back
    to the LRCC-DVNL sentinel of 127, which is a trap for any other dataset: in
    the Global Aridity Index, stored as AI x 10 000, 127 is a perfectly ordinary
    hyper-arid value, and silently turning it into NaN drops real pixels from
    both the numerator and the denominator of every share computed from them.
    A general-purpose reader must not know one dataset's sentinel.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()

    with rasterio.open(raster_path) as src:
        declared = src.nodata
        data = src.read(1, window=window).astype("float64")
        signature = (src.width, src.height, src.transform)

    if nodata is _UNSET:
        if declared is None:
            raise ValueError(
                f"{raster_path} declares no nodata; pass nodata= explicitly "
                "(there is no safe default - a wrong sentinel silently deletes "
                "real pixels)"
            )
        fill = float(declared)
    else:
        fill = None if nodata is None else float(nodata)

    if fill is not None:
        data[data == fill] = np.nan
    return data, signature


def zonal_sums(values, zone_ids, n_zones: int):
    """Sum and valid-pixel count per zone, ignoring NaN.

    Returns ``(sums, counts)``, each length ``n_zones``, indexed from zone 1.
    """
    np = _require_numpy()

    flat_ids = zone_ids.ravel()
    flat_values = values.ravel()
    valid = ~np.isnan(flat_values) & (flat_ids > 0)

    ids = flat_ids[valid]
    vals = flat_values[valid]
    sums = np.bincount(ids, weights=vals, minlength=n_zones + 1)[1:]
    counts = np.bincount(ids, minlength=n_zones + 1)[1:]
    return sums, counts


def zonal_table(
    rasters: Iterable[Tuple[int, Path]],
    grid: ZoneGrid,
    *,
    progress=None,
) -> List[dict]:
    """Per-unit, per-year aggregates as a list of row dicts.

    Emits sum of lights, pixel count, mean DN and light density (SOL per km²),
    plus the unit's area so a reader can re-derive any of them.
    """
    rows: List[dict] = []
    for year, path in rasters:
        values, signature = read_window(path, grid.window)
        if not grids_compatible(signature, grid.signature):
            raise ValueError(
                f"{path} is on a different grid than the zone raster "
                f"({signature} vs {grid.signature}); rebuild the zone grid"
            )
        sums, counts = zonal_sums(values, grid.ids, grid.count)
        for i in range(grid.count):
            pixels = int(counts[i])
            area = float(grid.areas_km2[i])
            total = float(sums[i])
            rows.append(
                {
                    "year": year,
                    "gid": grid.gids[i],
                    "name": grid.names[i],
                    "pixels": pixels,
                    "area_km2": round(area, 4),
                    "sum_of_lights": total,
                    "mean_dn": (total / pixels) if pixels else float("nan"),
                    "density_sol_per_km2": (total / area) if area > 0 else float("nan"),
                }
            )
        if progress:
            progress(year)
    return rows
