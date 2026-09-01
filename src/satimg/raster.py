"""Raster inspection and CRS repair for the nighttime-light GeoTIFFs.

Requires the optional extra::

    pip install -e ".[raster]"

The CRS repair exists because of a real defect in the published rasters: they
carry the Equal Earth parameters as a ``LOCAL_CS`` WKT rather than a projected
CRS, so ``to_epsg()`` returns ``None`` and most tools decline to reproject or
overlay them. Pixels and georeferencing are fine - only the CRS declaration is
wrong - so the fix is a metadata rewrite, not a resampling step.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from .checksums import md5_file
from .datasets.lrcc_dvnl import CRS_EPSG, DN_MAX, DN_MIN, NODATA
from .provenance import write_repair_record

#: Rows read at a time when scanning a full raster (int8, full width).
WINDOW_HEIGHT = 512

CRS_OK = "ok"
CRS_LOCAL_CS = "local_cs"
CRS_MISSING = "missing"
CRS_UNEXPECTED = "unexpected"


class RasterDependencyError(RuntimeError):
    """Raised when the optional raster dependencies are not installed."""


def _require_rasterio():
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - depends on install
        raise RasterDependencyError(
            'raster commands need rasterio and numpy: pip install -e ".[raster]"'
        ) from exc
    return rasterio


def _require_numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover - depends on install
        raise RasterDependencyError(
            'raster commands need rasterio and numpy: pip install -e ".[raster]"'
        ) from exc
    return numpy


@dataclass
class RasterInfo:
    path: str
    driver: str
    width: int
    height: int
    band_count: int
    dtype: str
    nodata: Optional[float]
    resolution: Tuple[float, float]
    bounds: Tuple[float, float, float, float]
    crs_wkt: Optional[str]
    crs_epsg: Optional[int]
    crs_status: str
    crs_note: str
    compression: Optional[str]
    tiled: bool
    size_bytes: int

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def _classify_crs(crs) -> Tuple[str, str, Optional[int]]:
    """Describe how usable a raster's CRS declaration is."""
    if crs is None:
        return (
            CRS_MISSING,
            "no CRS at all; expected EPSG:8857 (WGS 84 / Equal Earth Greenwich)",
            None,
        )
    epsg = crs.to_epsg()
    if epsg == CRS_EPSG:
        return CRS_OK, f"EPSG:{CRS_EPSG}", epsg
    wkt = crs.to_wkt() or ""
    if epsg is None and wkt.startswith("LOCAL_CS"):
        return (
            CRS_LOCAL_CS,
            (
                "CRS is an unusable LOCAL_CS even though it names EPSG:8857 - "
                "run 'satimg raster fix-crs' before reprojecting or overlaying"
            ),
            None,
        )
    if epsg is None:
        return CRS_UNEXPECTED, "CRS does not resolve to any EPSG code", None
    return CRS_UNEXPECTED, f"unexpected CRS EPSG:{epsg} (expected {CRS_EPSG})", epsg


def describe(path: str | Path) -> RasterInfo:
    """Collect the properties of a raster that matter for this dataset."""
    rasterio = _require_rasterio()
    path = Path(path)
    with rasterio.open(path) as src:
        status, note, epsg = _classify_crs(src.crs)
        return RasterInfo(
            path=str(path),
            driver=src.driver,
            width=src.width,
            height=src.height,
            band_count=src.count,
            dtype=src.dtypes[0],
            nodata=src.nodata,
            resolution=(src.res[0], src.res[1]),
            bounds=tuple(src.bounds),
            crs_wkt=src.crs.to_wkt() if src.crs else None,
            crs_epsg=epsg,
            crs_status=status,
            crs_note=note,
            compression=(
                src.profile.get("compress").lower()
                if src.profile.get("compress")
                else None
            ),
            tiled=bool(src.profile.get("tiled")),
            size_bytes=path.stat().st_size,
        )


def needs_crs_repair(path: str | Path) -> bool:
    """True when the raster's CRS is not a usable EPSG:8857 declaration."""
    return describe(path).crs_status != CRS_OK


def repair_crs(
    path: str | Path,
    *,
    out: Optional[str | Path] = None,
    epsg: int = CRS_EPSG,
    record: bool = True,
) -> Path:
    """Stamp a proper EPSG CRS onto a raster.

    Rewrites georeferencing metadata only; pixel values are untouched. Edits
    ``path`` in place unless ``out`` is given, in which case the file is copied
    first and the copy is fixed.

    Rewriting the headers changes the file's digest, so unless ``record`` is
    False a provenance sidecar is written recording the pre-repair MD5. That is
    what lets ``satimg lrcc-dvnl verify`` still recognise the file afterwards.
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS

    source = Path(path)
    target = Path(out) if out is not None else source

    if record:
        before_md5 = md5_file(source)
        before_size = source.stat().st_size

    if target != source:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    with rasterio.open(target, "r+") as dst:
        dst.crs = CRS.from_epsg(epsg)

    if record:
        write_repair_record(
            target,
            original_md5=before_md5,
            original_size=before_size,
            operation="fix-crs",
            details={"epsg": epsg},
        )
    return target


def clip_raster(
    path: str | Path,
    out_path: str | Path,
    window,
    *,
    epsg: int = CRS_EPSG,
    mask_geometries=None,
) -> Path:
    """Write a windowed copy of a raster, preserving its dtype and values.

    Used to cut a country out of the global grid. The dtype is taken from the
    source rather than fixed, because the series mixes int8, int16 and float32
    and a hardcoded profile would truncate the fractional VIIRS-era years. The
    output carries a real EPSG CRS instead of the published LOCAL_CS.

    ``mask_geometries`` sets everything outside those shapes to nodata, so the
    result is the country itself rather than its bounding box - otherwise a
    Tunisia "extract" still carries Algerian and Libyan light. The burn uses
    ``all_touched=False``, matching :mod:`satimg.zonal`, so the retained pixel
    set is exactly the one the zonal statistics aggregate over.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()
    from rasterio.crs import CRS
    from rasterio.features import rasterize

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(path) as src:
        dtype = src.dtypes[0]
        profile = src.profile.copy()
        profile.update(
            width=int(window.width),
            height=int(window.height),
            transform=src.window_transform(window),
            dtype=dtype,
            compress="lzw",
            tiled=False,
            crs=CRS.from_epsg(epsg),
            predictor=3 if dtype.startswith("float") else 2,
        )
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        nodata = NODATA if src.nodata is None else src.nodata
        profile["nodata"] = nodata
        transform = src.window_transform(window)
        data = src.read(1, window=window)

    if mask_geometries is not None:
        keep = rasterize(
            ((geom, 1) for geom in mask_geometries),
            out_shape=data.shape,
            transform=transform,
            fill=0,
            all_touched=False,
            dtype="uint8",
        ).astype(bool)
        data = np.where(keep, data, np.asarray(nodata).astype(data.dtype))

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.set_band_description(1, f"LRCC-DVNL nighttime light DN (0-63, {dtype})")
    return out_path


@dataclass
class RasterStats:
    """Nighttime-light summary statistics for one annual raster."""

    path: str
    total_pixels: int
    nodata_pixels: int
    valid_pixels: int
    lit_pixels: int
    zero_pixels: int
    out_of_range_pixels: int
    min_dn: Optional[float]
    max_dn: Optional[float]
    sum_of_lights: float
    mean_dn_valid: Optional[float]
    mean_dn_lit: Optional[float]
    histogram: Dict[int, int] = field(default_factory=dict)
    #: Source dtype - the series mixes int8, int16 and float32 across years.
    dtype: str = ""
    #: True when the source held fractional DN, so histogram keys are floors.
    histogram_is_binned: bool = False

    @property
    def lit_fraction(self) -> Optional[float]:
        if not self.valid_pixels:
            return None
        return self.lit_pixels / self.valid_pixels

    def as_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["lit_fraction"] = self.lit_fraction
        return data


def summarize(
    path: str | Path,
    *,
    nodata: Optional[int] = None,
    max_dn: int = DN_MAX,
    window_height: int = WINDOW_HEIGHT,
) -> RasterStats:
    """Compute DN statistics for a raster, reading it in horizontal strips.

    Streams the raster so a full 34488x15315 global grid can be summarized
    without holding all ~528 million pixels in memory at once.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()
    from rasterio.windows import Window

    path = Path(path)
    with rasterio.open(path) as src:
        fill = nodata if nodata is not None else src.nodata
        fill = NODATA if fill is None else float(fill)
        dtype = src.dtypes[0]
        # 1992 is int8, 1993-2013 int16, 2014-2022 float32 with fractional DN.
        # Integer years can be counted exactly; float years cannot, so their
        # histogram bins by floor and the summary statistics are accumulated.
        is_float = dtype.startswith("float")

        counts = np.zeros(int(max_dn) + 2, dtype=np.int64)
        nodata_pixels = 0
        valid_pixels = 0
        out_of_range = 0
        sum_of_lights = 0.0
        observed_min = None
        observed_max = None

        for row_start in range(0, src.height, window_height):
            rows = min(window_height, src.height - row_start)
            block = src.read(1, window=Window(0, row_start, src.width, rows)).astype(
                np.float64
            )
            is_fill = block == fill
            nodata_pixels += int(is_fill.sum())

            valid = (~is_fill) & (block >= DN_MIN) & (block <= max_dn)
            values = block[valid]
            valid_pixels += int(values.size)
            out_of_range += (
                int(rows) * int(src.width) - int(is_fill.sum()) - values.size
            )

            if values.size:
                sum_of_lights += float(values.sum())
                low, high = float(values.min()), float(values.max())
                observed_min = low if observed_min is None else min(observed_min, low)
                observed_max = high if observed_max is None else max(observed_max, high)
                bins = np.floor(values).astype(np.int64)
                counts += np.bincount(bins, minlength=counts.size)[: counts.size]

        total = int(src.height) * int(src.width)

    zero_pixels = int(counts[0]) if fill != 0 else 0
    lit_pixels = valid_pixels - zero_pixels
    histogram = {int(dn): int(n) for dn, n in enumerate(counts) if n}

    def _round(value):
        if value is None:
            return None
        return value if is_float else int(value)

    return RasterStats(
        path=str(path),
        total_pixels=total,
        nodata_pixels=nodata_pixels,
        valid_pixels=valid_pixels,
        lit_pixels=lit_pixels,
        zero_pixels=zero_pixels,
        out_of_range_pixels=int(out_of_range),
        min_dn=_round(observed_min),
        max_dn=_round(observed_max),
        sum_of_lights=sum_of_lights if is_float else int(sum_of_lights),
        mean_dn_valid=(sum_of_lights / valid_pixels) if valid_pixels else None,
        mean_dn_lit=(sum_of_lights / lit_pixels) if lit_pixels else None,
        histogram=histogram,
        dtype=dtype,
        histogram_is_binned=is_float,
    )
