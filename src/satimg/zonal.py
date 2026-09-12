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
    #: Every window this grid covers. One for almost every country, so ``ids``
    #: stays 2-D and identical to what a single-window build produced. More than
    #: one where a country's land sits on both sides of the antimeridian, in
    #: which case ``ids`` is the 1-D concatenation of each window's flattened
    #: ids and ``window``/``transform`` describe the first window only - enough
    #: to draw the main landmass, not enough to reconstruct the whole set.
    windows: Tuple = ()

    @property
    def read_windows(self):
        """What to hand :func:`read_window` so the values match ``ids``."""
        return self.windows if len(self.windows) > 1 else self.window

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
    window=None,
) -> ZoneGrid:
    """Burn a GeoDataFrame's units onto the raster grid, once.

    ``window`` overrides the one derived from ``frame``'s own extent. Pass a
    shared window when several admin levels of the same country must produce
    arrays that line up: their extents are not guaranteed to agree, and where
    they disagree the arrays cannot be combined. See ``analysis.build_grids``.
    """
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
    if window is None:
        window = window_for(raster_path, frame.total_bounds)

    # One window keeps the 2-D array this has always produced. Several windows
    # burn the same units into each and concatenate the flattened results, so a
    # unit straddling the antimeridian accumulates its pixels across windows
    # rather than being assigned to one side of it. Ids are per-unit, so the
    # same unit gets the same id in every window and the accumulation is exact.
    windows = tuple(window) if isinstance(window, tuple) else (window,)

    with rasterio.open(raster_path) as src:
        signature = (src.width, src.height, src.transform)
        transforms = [src.window_transform(w) for w in windows]

    geoms = list(enumerate(frame.geometry))
    burned = []
    for w, tf in zip(windows, transforms):
        burned.append(
            rasterize(
                ((geom, i + 1) for i, geom in geoms),
                out_shape=(int(w.height), int(w.width)),
                transform=tf,
                fill=0,
                all_touched=False,
                dtype="int32",
            )
        )
    ids = burned[0] if len(burned) == 1 else np.concatenate([b.ravel() for b in burned])

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
        window=windows[0],
        transform=transforms[0],
        signature=signature,
        windows=windows,
    )


def _is_window(obj) -> bool:
    """True for a single rasterio Window, which is itself tuple-like."""
    return hasattr(obj, "col_off") and hasattr(obj, "row_off")


def read_window(raster_path: str | Path, window, *, nodata=_UNSET):
    """Read band 1 over a window as float64, with nodata as NaN.

    ``window`` may be a single window - the array comes back 2-D, as it always
    has - or a **tuple of windows**, in which case each is read and their
    flattened contents are concatenated into one 1-D array. That is what lets a
    country occupying both sides of the antimeridian be analysed without
    dropping anything: every consumer of these values ravels before use
    (``zonal_sums``, ``decompose_theil_by_ids``, the scope masks), so a
    concatenation across windows is exactly equivalent to one contiguous read,
    while a single lon/lat box spanning the wrap would be a globe-wide frame.

    ``nodata`` must be given when the file declares none. This used to fall back
    to the LRCC-DVNL sentinel of 127, which is a trap for any other dataset: in
    the Global Aridity Index, stored as AI x 10 000, 127 is a perfectly ordinary
    hyper-arid value, and silently turning it into NaN drops real pixels from
    both the numerator and the denominator of every share computed from them.
    A general-purpose reader must not know one dataset's sentinel.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()

    multi = isinstance(window, tuple) and not _is_window(window)
    with rasterio.open(raster_path) as src:
        declared = src.nodata
        if multi:
            if not window:
                raise ValueError("read_window got an empty window tuple")
            parts = [src.read(1, window=w).astype("float64").ravel() for w in window]
            data = np.concatenate(parts)
        else:
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
        values, signature = read_window(path, grid.read_windows)
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
