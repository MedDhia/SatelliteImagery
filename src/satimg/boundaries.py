"""GADM administrative boundaries, prepared for overlay on the NTL rasters.

GADM is **not redistributable**. Its license reads:

    The data are freely available for academic use and other non-commercial
    use. Redistribution or commercial use is not allowed without prior
    permission.

So nothing here is committed to the repository: the archive is downloaded on
demand into a gitignored directory, and a copy of the license notice is written
alongside it. Producing maps for academic publication is explicitly permitted;
redistributing the boundary data, or overlay products that embed it, is not.

Preparation pipeline, per admin level:

1. read the level's layer from the world GeoPackage (EPSG:4326),
2. segmentize in degrees, so long straight lon/lat spans become curves in the
   projected CRS instead of chords,
3. reproject to the raster's CRS (EPSG:8857, Equal Earth),
4. simplify with a metric tolerance below one pixel,
5. cache the result so later renders skip all of the above.

Requires the ``overlay`` extra::

    pip install -e ".[overlay]"
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .datasets.lrcc_dvnl import CRS_EPSG, RESOLUTION_M
from .download import download_file

GADM_VERSION = "4.1"
GADM_ARCHIVE_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"
GADM_ARCHIVE_NAME = "gadm_410-levels.zip"
GADM_ARCHIVE_BYTES = 2_683_857_383
GADM_GPKG_NAME = "gadm_410-levels.gpkg"
GADM_HOMEPAGE = "https://gadm.org/"

GADM_LICENSE_NOTICE = f"""\
GADM {GADM_VERSION} administrative boundaries
Source: {GADM_HOMEPAGE} ({GADM_ARCHIVE_URL})

License (https://gadm.org/license.html):

    The data are freely available for academic use and other non-commercial
    use. Redistribution or commercial use is not allowed without prior
    permission.

Austria's data is covered separately by CC BY-SA 2.0.

Consequences for this repository:
  * These files are gitignored and must never be committed.
  * Overlay products derived from them inherit the restriction: they may be
    used in academic publications, but not redistributed commercially or
    republished as data without permission from GADM.

Cite as: GADM, version {GADM_VERSION}. https://gadm.org/
"""

#: Admin level -> layer name in the world "levels" GeoPackage.
LEVEL_LAYERS: Dict[int, str] = {
    0: "ADM_0",
    1: "ADM_1",
    2: "ADM_2",
    3: "ADM_3",
    4: "ADM_4",
    5: "ADM_5",
}

#: Admin level -> human label used in titles and filenames.
LEVEL_LABELS: Dict[int, str] = {
    0: "country",
    1: "subnational",
    2: "admin-2",
    3: "admin-3",
    4: "admin-4",
    5: "admin-5",
}

DEFAULT_ROOT = Path("data/boundaries")

#: Simplification tolerance. Half a pixel: invisible at 1 km, but it cuts the
#: ~36M vertices of GADM ADM_0 by well over an order of magnitude.
DEFAULT_TOLERANCE_M = RESOLUTION_M / 2

#: Max segment length before reprojection, in degrees (~55 km at the equator).
DEFAULT_SEGMENTIZE_DEG = 0.5


class BoundaryDependencyError(RuntimeError):
    """Raised when the optional overlay dependencies are not installed."""


class BoundaryDataMissing(RuntimeError):
    """Raised when the GADM source data has not been downloaded yet."""


def _require_geopandas():
    try:
        import geopandas
    except ImportError as exc:  # pragma: no cover - depends on install
        raise BoundaryDependencyError(
            'boundary overlays need geopandas and shapely: pip install -e ".[overlay]"'
        ) from exc
    return geopandas


def check_level(level: int) -> int:
    if level not in LEVEL_LAYERS:
        raise ValueError(
            f"unsupported admin level {level!r}; choose one of {sorted(LEVEL_LAYERS)}"
        )
    return level


def archive_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "gadm" / GADM_ARCHIVE_NAME


def gpkg_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "gadm" / GADM_GPKG_NAME


def license_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "gadm" / "LICENSE-GADM.txt"


def cache_path(
    root: str | Path = DEFAULT_ROOT,
    *,
    level: int = 0,
    epsg: int = CRS_EPSG,
    tolerance_m: float = DEFAULT_TOLERANCE_M,
    iso3: Optional[str] = None,
) -> Path:
    """Path of the reprojected, simplified cache for one admin level.

    A country-scoped cache is kept separate from the world one: preparing all
    47,217 world ADM_2 features to reach one country's 268 would be wasteful,
    and the two are not interchangeable.
    """
    check_level(level)
    tolerance = f"{tolerance_m:g}".replace(".", "p")
    scope = f"_{iso3.upper()}" if iso3 else ""
    return (
        Path(root) / "cache" / f"gadm{GADM_VERSION.replace('.', '')}"
        f"_adm{level}{scope}_epsg{epsg}_simp{tolerance}m.gpkg"
    )


@dataclass(frozen=True)
class BoundaryLayer:
    """A prepared boundary layer ready to draw or rasterize."""

    level: int
    path: Path
    epsg: int
    feature_count: int
    tolerance_m: float
    iso3: Optional[str] = None

    @property
    def label(self) -> str:
        return LEVEL_LABELS[self.level]

    @property
    def attribution(self) -> str:
        return f"Boundaries: GADM {GADM_VERSION} (gadm.org), non-commercial use"


def write_license_notice(root: str | Path = DEFAULT_ROOT) -> Path:
    target = license_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(GADM_LICENSE_NOTICE, encoding="utf-8")
    return target


def fetch_gadm(
    root: str | Path = DEFAULT_ROOT,
    *,
    keep_archive: bool = False,
    progress=None,
) -> Path:
    """Download and extract the GADM world "levels" GeoPackage.

    Returns the path to the extracted GeoPackage. Skips work that is already
    done, so this is safe to re-run.
    """
    target = gpkg_path(root)
    write_license_notice(root)
    if target.exists():
        return target

    archive = archive_path(root)
    # GADM publishes no checksums, so size is the only integrity signal.
    download_file(
        GADM_ARCHIVE_URL,
        archive,
        expected_size=GADM_ARCHIVE_BYTES,
        progress=progress,
    )

    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if GADM_GPKG_NAME not in names:
            raise RuntimeError(
                f"{GADM_ARCHIVE_NAME} did not contain {GADM_GPKG_NAME}; got {names}"
            )
        bundle.extract(GADM_GPKG_NAME, path=archive.parent)

    if not keep_archive:
        archive.unlink()
    return target


def _is_geographic(epsg: int) -> bool:
    """True when an EPSG code denotes a lat/lon CRS rather than a projected one."""
    from pyproj import CRS

    return bool(CRS.from_epsg(epsg).is_geographic)


def prepare_level(
    root: str | Path = DEFAULT_ROOT,
    *,
    level: int = 0,
    epsg: int = CRS_EPSG,
    tolerance_m: float = DEFAULT_TOLERANCE_M,
    segmentize_deg: float = DEFAULT_SEGMENTIZE_DEG,
    force: bool = False,
    source: Optional[str | Path] = None,
    iso3: Optional[str] = None,
) -> BoundaryLayer:
    """Reproject and simplify one admin level, caching the result.

    ``iso3`` restricts to one country (GADM ``GID_0``). The filter is pushed
    down into the read, so a country's ADM_2 costs seconds instead of the
    minutes a world-wide ADM_2 prepare would take.
    """
    gpd = _require_geopandas()
    check_level(level)
    iso3 = iso3.upper() if iso3 else None

    cache = Path(
        cache_path(root, level=level, epsg=epsg, tolerance_m=tolerance_m, iso3=iso3)
    )
    meta = cache.with_suffix(".json")

    if cache.exists() and meta.exists() and not force:
        recorded = json.loads(meta.read_text(encoding="utf-8"))
        return BoundaryLayer(
            level=level,
            path=cache,
            epsg=epsg,
            feature_count=recorded.get("feature_count", 0),
            tolerance_m=tolerance_m,
            iso3=iso3,
        )

    origin = Path(source) if source is not None else gpkg_path(root)
    if not origin.exists():
        raise BoundaryDataMissing(
            f"GADM data not found at {origin}. Run 'satimg boundaries fetch' first "
            "(2.5 GiB download; GADM is non-commercial use only)."
        )

    read_kwargs = {"layer": LEVEL_LAYERS[level], "engine": "pyogrio"}
    if iso3:
        read_kwargs["where"] = f"GID_0 = '{iso3}'"
    frame = gpd.read_file(origin, **read_kwargs)
    if iso3 and frame.empty:
        raise ValueError(
            f"no GADM {LEVEL_LAYERS[level]} features for country code {iso3!r}"
        )

    # Densify in degrees first: long straight lon/lat spans (Antarctica's polar
    # edge, ruler-straight desert borders) would otherwise become chords once
    # projected, cutting visibly across the true boundary.
    # DEFAULT_TOLERANCE_M is 500 (half a pixel), which is right for EPSG:8857
    # and catastrophic for a geographic target: simplify() would be handed 500
    # *degrees* and collapse every polygon - and the wreckage would be cached
    # under a plausible filename and silently reused forever after.
    if tolerance_m and _is_geographic(epsg):
        raise ValueError(
            f"tolerance_m={tolerance_m} is metres, but EPSG:{epsg} is a "
            "geographic CRS where simplify() takes degrees. Pass "
            "tolerance_m=0.0 for a lat/lon target."
        )

    if segmentize_deg:
        frame["geometry"] = frame.geometry.segmentize(segmentize_deg)

    frame = frame.to_crs(epsg=epsg)

    if tolerance_m:
        frame["geometry"] = frame.geometry.simplify(tolerance_m, preserve_topology=True)

    keep = [
        c
        for c in ("GID_0", "COUNTRY", "GID_1", "NAME_1", "GID_2", "NAME_2")
        if c in frame.columns
    ]
    frame = frame[[*keep, "geometry"]]

    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(cache, driver="GPKG", layer=f"adm{level}")
    meta.write_text(
        json.dumps(
            {
                "source": "GADM",
                "gadm_version": GADM_VERSION,
                "level": level,
                "iso3": iso3,
                "layer": LEVEL_LAYERS[level],
                "epsg": epsg,
                "tolerance_m": tolerance_m,
                "segmentize_deg": segmentize_deg,
                "feature_count": len(frame),
                "license": "non-commercial; redistribution not permitted",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return BoundaryLayer(
        level=level,
        path=cache,
        epsg=epsg,
        feature_count=len(frame),
        tolerance_m=tolerance_m,
        iso3=iso3,
    )


def load_lines(layer: BoundaryLayer):
    """Boundary geometries of a prepared layer, as lines ready to draw."""
    gpd = _require_geopandas()
    frame = gpd.read_file(layer.path, engine="pyogrio")
    return frame.geometry.boundary
