"""Global Aridity Index v3.1: a climate covariate for the light analysis.

The exclusion scopes in :mod:`satimg.regions` are cut from a break in observed
*lit share*, and across 22 countries that is demonstrably not the same thing as
"desert" - the rule reaches Aleppo, Mosul and Somali riverine farmland. This
module brings in an independent measure of climate so the two can be separated:
a unit that is dark **and** arid is a desert, and a unit that is dark and **not**
arid is dark for some human reason.

Source: Zomer, Xu & Trabucco (2022), *Scientific Data* 9, 409,
doi:10.1038/s41597-022-01493-1. Global-AI_PET v3.1, 30 arc-seconds, EPSG:4326,
a **1970-2000 climate normal** built on WorldClim 2.x. CC BY 4.0 - attribution
required, but unlike GADM there is no non-commercial clause.

Version 3.1 specifically: v3.0 was deprecated for an error in net longwave
radiation that biased AI dry.

Three properties of the published files decide the whole design, and all three
were measured here rather than assumed:

* **AI is stored as an integer, AI x 10 000, in uint16.** Thresholds are
  therefore compared as integers (2000, not 0.2): the data is quantised to 1e-4
  and pixels sit exactly on the boundary, so a float comparison would let
  rounding decide the class.
* **The AI layer declares no nodata, and 0 is ambiguous** - it is the ocean fill
  *and* a genuine value where precipitation is essentially zero. Egypt's New
  Valley contains 0 on real land. Treating 0 as nodata deletes the driest desert
  on Earth; treating it as data paints the Atlantic hyper-arid.
* **The companion ET0 layer resolves it.** ET0 *does* declare nodata (65535) and
  is defined over all land, so ``ET0 != 65535`` is a land mask that comes from
  the dataset itself rather than a heuristic. Measured: it selects 28.6% of the
  grid against Earth's ~29% land fraction, marks the mid-Atlantic invalid, and
  keeps New Valley's zeros (where ET0 reads 2534-2612).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .raster import _require_numpy, _require_rasterio

DEFAULT_ROOT = Path("data/aridity")

#: figshare item 7504448, file id of the annual archive for v3.1.
FIGSHARE_FILE_ID = 56300327
ARCHIVE_URL = f"https://ndownloader.figshare.com/files/{FIGSHARE_FILE_ID}"
ARCHIVE_NAME = "Global-AI_ET0__annual_v3_1.zip"
ARCHIVE_BYTES = 645_783_906

#: Members to extract. The archive holds three GeoTIFFs - AI, ET0 and an ET0
#: standard deviation - so a bare ``*.tif`` glob would pick an arbitrary one.
AI_MEMBER = "Global-AI_ET0__annual_v3_1/ai_v31_yr.tif"
ET0_MEMBER = "Global-AI_ET0__annual_v3_1/et0_v31_yr.tif"
AI_NAME = "ai_v31_yr.tif"
ET0_NAME = "et0_v31_yr.tif"

VERSION = "3.1"
DOI = "10.1038/s41597-022-01493-1"
LANDING_PAGE = "https://doi.org/10.6084/m9.figshare.7504448"
CRS_EPSG = 4326
RESOLUTION_DEG = 1.0 / 120.0
SCALE = 1e-4
#: Both layers use 65535 as "undefined"; on the AI layer it appears only on land.
UNDEFINED = 65535
CLIMATOLOGY = "1970-2000"

CITATION = (
    "Zomer, R.J., Xu, J. & Trabucco, A. (2022). Version 3 of the Global Aridity "
    "Index and Potential Evapotranspiration Database. Scientific Data, 9, 409. "
    "https://doi.org/10.1038/s41597-022-01493-1"
)

LICENSE_NOTICE = f"""\
Global Aridity Index and Potential Evapotranspiration Database v{VERSION}
Zomer, Xu & Trabucco (2022), CC BY 4.0.

Attribution is required; there is no non-commercial restriction, so unlike the
GADM boundaries this source does not further encumber derived products.

Cite as:
  {CITATION}

Downloaded from {LANDING_PAGE}
"""


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AridityClass:
    """One UNEP aridity class and the raw integer range that defines it."""

    code: int
    key: str
    label: str
    lower_raw: int  # inclusive
    upper_raw: Optional[int]  # exclusive; None = unbounded

    @property
    def lower_ai(self) -> float:
        return self.lower_raw * SCALE

    @property
    def upper_ai(self) -> Optional[float]:
        return None if self.upper_raw is None else self.upper_raw * SCALE


#: UNEP classes. Half-open intervals [lower, upper), so a pixel sitting exactly
#: on 2000 is semi-arid, never both or neither. Code 0 is reserved for nodata so
#: a classified raster can use 0 as its fill without colliding with a class.
CLASSES: Tuple[AridityClass, ...] = (
    AridityClass(1, "hyper_arid", "hyper-arid", 0, 300),
    AridityClass(2, "arid", "arid", 300, 2000),
    AridityClass(3, "semi_arid", "semi-arid", 2000, 5000),
    AridityClass(4, "dry_subhumid", "dry sub-humid", 5000, 6500),
    AridityClass(5, "humid", "humid", 6500, None),
)
NODATA_CODE = 0

#: UNEP's drylands definition of desert: hyper-arid plus arid.
DESERT_MAX_RAW = 2000
#: Everything below dry sub-humid's upper bound is a "dryland".
DRYLAND_MAX_RAW = 6500

CLASS_BY_KEY: Dict[str, AridityClass] = {c.key: c for c in CLASSES}
DESERT_KEYS = ("hyper_arid", "arid")
#: Every class below DRYLAND_MAX_RAW - which is to say all of them but humid.
#: Derived from CLASSES rather than listed, because writing the members out by
#: hand is exactly how dry sub-humid came to be left out of the sum once.
DRYLAND_KEYS = tuple(
    c.key for c in CLASSES if c.upper_raw is not None and c.upper_raw <= DRYLAND_MAX_RAW
)


def classify(raw, land_mask=None):
    """Class codes for raw AI values, 0 where undefined.

    ``raw`` is the stored integer (AI x 10 000), compared as an integer. Pass
    ``land_mask`` (True on land) to mark ocean as undefined: the AI layer fills
    ocean with 0, which is otherwise a legitimate hyper-arid value.
    """
    np = _require_numpy()

    raw = np.asarray(raw)
    codes = np.zeros(raw.shape, dtype="uint8")
    valid = raw != UNDEFINED
    if land_mask is not None:
        valid &= np.asarray(land_mask, dtype=bool)

    for item in CLASSES:
        in_class = raw >= item.lower_raw
        if item.upper_raw is not None:
            in_class &= raw < item.upper_raw
        codes[valid & in_class] = item.code
    return codes


# --------------------------------------------------------------------------- #
# true cell area on a geographic grid
# --------------------------------------------------------------------------- #
#: WGS84 ellipsoid, matching the CRS the source is published in.
SEMI_MAJOR_KM = 6378.137
ECC_SQ = 0.00669437999014


def _authalic_q(lat_deg):
    """The authalic integrand q(phi); (q2 - q1)/2 is the sine-like area factor."""
    np = _require_numpy()

    phi = np.radians(np.asarray(lat_deg, dtype="float64"))
    e = math.sqrt(ECC_SQ)
    sin_phi = np.sin(phi)
    return (1 - ECC_SQ) * (
        sin_phi / (1 - ECC_SQ * sin_phi**2)
        - (1 / (2 * e)) * np.log((1 - e * sin_phi) / (1 + e * sin_phi))
    )


def row_areas_km2(transform, height: int, width: int = 1):
    """Area of one cell in each row of a geographic grid, in km2.

    A 30 arc-second cell shrinks poleward, so counting pixels is not measuring
    area. Uses the exact ellipsoidal formula rather than cos(latitude): the
    difference is under a percent for shares, but it makes the absolute km2
    directly comparable to the equal-area figures already committed elsewhere,
    which turns a loose sanity check into a real one.

    Returns one value per row - the caller broadcasts across columns.
    """
    np = _require_numpy()

    rows = np.arange(height + 1, dtype="float64")
    # Row edges: transform maps (col, row) -> (x, y) at cell corners.
    lat_edges = transform.f + rows * transform.e
    q = _authalic_q(lat_edges)
    d_lon = abs(transform.a)
    areas = math.radians(d_lon) * SEMI_MAJOR_KM**2 * (q[:-1] - q[1:]) / 2.0
    return np.abs(areas) * width


# --------------------------------------------------------------------------- #
# acquisition
# --------------------------------------------------------------------------- #
def archive_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "global-ai" / ARCHIVE_NAME


def ai_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "global-ai" / AI_NAME


def et0_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "global-ai" / ET0_NAME


def license_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "global-ai" / "LICENSE-GlobalAI.txt"


def write_license_notice(root: str | Path = DEFAULT_ROOT) -> Path:
    target = license_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(LICENSE_NOTICE, encoding="utf-8")
    return target


def fetch(
    root: str | Path = DEFAULT_ROOT, *, keep_archive: bool = False, progress=None
):
    """Download and extract the annual AI and ET0 layers."""
    import zipfile

    from .download import download_file

    root = Path(root)
    write_license_notice(root)
    ai, et0 = ai_path(root), et0_path(root)
    if ai.exists() and et0.exists():
        return ai, et0

    archive = archive_path(root)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        # figshare redirects to a presigned S3 URL that expires in seconds, so a
        # resumed attempt must re-request this URL rather than the redirect
        # target; download_file follows redirects per attempt.
        download_file(
            ARCHIVE_URL, archive, expected_size=ARCHIVE_BYTES, progress=progress
        )

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        for member, target in ((AI_MEMBER, ai), (ET0_MEMBER, et0)):
            if member not in names:
                raise RuntimeError(f"{archive} does not contain {member}")
            with bundle.open(member) as src, open(target, "wb") as dst:
                while chunk := src.read(1 << 22):
                    dst.write(chunk)

    if not keep_archive:
        archive.unlink()
    return ai, et0


def check_source(root: str | Path = DEFAULT_ROOT) -> Dict[str, object]:
    """Assert the extracted layers are the grid we think they are.

    Cheap, and it turns a silently-wrong mirror into a loud failure. Different
    redistributions of this dataset ship different conventions; nothing here is
    hard-coded from memory.
    """
    rasterio = _require_rasterio()

    ai, et0 = ai_path(root), et0_path(root)
    for path in (ai, et0):
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `satimg aridity fetch`")

    facts: Dict[str, object] = {}
    with rasterio.open(ai) as a, rasterio.open(et0) as e:
        if a.crs.to_epsg() != CRS_EPSG:
            raise ValueError(f"aridity CRS is {a.crs}, expected EPSG:{CRS_EPSG}")
        if abs(a.res[0] - RESOLUTION_DEG) > 1e-9:
            raise ValueError(f"aridity resolution {a.res[0]}, expected 1/120")
        if (a.width, a.height) != (e.width, e.height) or a.transform != e.transform:
            raise ValueError("AI and ET0 layers are not on the same grid")
        if e.nodata is None:
            raise ValueError(
                "ET0 declares no nodata, so it cannot serve as the land mask"
            )
        facts.update(
            width=a.width,
            height=a.height,
            ai_dtype=a.dtypes[0],
            ai_nodata=a.nodata,
            et0_nodata=e.nodata,
            transform=a.transform,
            bounds=tuple(a.bounds),
        )
    return facts


# --------------------------------------------------------------------------- #
# pass A: per-unit class shares on the source's own geographic grid
# --------------------------------------------------------------------------- #
def country_units(iso3: str, level: int = 1, *, boundaries_root=None):
    """Admin units in EPSG:4326 - the CRS both GADM and this dataset use.

    No reprojection happens anywhere in pass A. ``tolerance_m=0`` and
    ``segmentize_deg=0`` are not optional: the default tolerance is 500 *metres*,
    which in a geographic CRS would be handed to ``simplify`` as 500 degrees and
    collapse every polygon - and the result would be cached under a
    plausible-looking name and reused forever.
    """
    import geopandas as gpd

    from . import boundaries as B

    layer = B.prepare_level(
        boundaries_root or B.DEFAULT_ROOT,
        level=level,
        epsg=CRS_EPSG,
        tolerance_m=0.0,
        segmentize_deg=0.0,
        iso3=iso3,
    )
    return gpd.read_file(layer.path, engine="pyogrio")


def unit_shares(
    iso3: str,
    *,
    root: str | Path = DEFAULT_ROOT,
    boundaries_root=None,
    level: int = 1,
) -> List[dict]:
    """Area share of each aridity class, per admin unit.

    Shares are of **area**, not of pixels: a 30 arc-second cell at 37N is 20%
    smaller than one at the equator, so a pixel count is not an area fraction.
    Both numerator and denominator are weighted, and both come from the same
    pixel set, so the shares sum to exactly 1.
    """
    np = _require_numpy()
    rasterio = _require_rasterio()
    from rasterio.features import rasterize

    from . import regions as R
    from . import zonal as Z

    units = country_units(iso3, level, boundaries_root=boundaries_root)
    units = units.reset_index(drop=True)
    id_field, name_field = R.id_fields(level)

    ai, et0 = ai_path(root), et0_path(root)
    window = Z.window_for(ai, units.total_bounds)
    with rasterio.open(ai) as src:
        transform = src.window_transform(window)
        ai_values = src.read(1, window=window)
    with rasterio.open(et0) as src:
        et0_values = src.read(1, window=window)
        et0_fill = src.nodata

    shapes = ((geom, i + 1) for i, geom in enumerate(units.geometry))
    zone_ids = rasterize(
        shapes,
        out_shape=ai_values.shape,
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="int32",
    )

    land = et0_values != et0_fill
    codes = classify(ai_values, land_mask=land)

    # One weight per row, broadcast across columns. Latitudes come from the
    # WINDOW transform, not the global one - the global grid puts Tunisia around
    # row 6300, and using it would shift every latitude by ~52 degrees while
    # still yielding shares in [0, 1] that sum to 1.
    height, width = ai_values.shape
    weights = np.repeat(row_areas_km2(transform, height)[:, None], width, axis=1)

    count = len(units)
    flat_zone = zone_ids.ravel()
    flat_code = codes.ravel()
    flat_weight = weights.ravel()
    inside = flat_zone > 0
    classified = inside & (flat_code != NODATA_CODE)

    def weighted(mask):
        return np.bincount(
            flat_zone[mask], weights=flat_weight[mask], minlength=count + 1
        )[1:]

    total_area = weighted(classified)
    pixels_total = np.bincount(flat_zone[inside], minlength=count + 1)[1:]
    pixels_classified = np.bincount(flat_zone[classified], minlength=count + 1)[1:]

    per_class = {
        item.key: weighted(classified & (flat_code == item.code)) for item in CLASSES
    }

    rows: List[dict] = []
    for index in range(count):
        area = float(total_area[index])
        row = {
            "iso3": iso3,
            "gid": str(units[id_field].iloc[index]),
            "name": str(units[name_field].iloc[index]),
            "area_km2": round(area, 4),
            "pixels_total": int(pixels_total[index]),
            "pixels_classified": int(pixels_classified[index]),
            "pixels_unclassified": int(pixels_total[index] - pixels_classified[index]),
        }
        for item in CLASSES:
            row[f"{item.key}_share"] = (
                float(per_class[item.key][index] / area) if area > 0 else float("nan")
            )
        row["desert_share"] = sum(row[f"{key}_share"] for key in DESERT_KEYS)
        # Every class below AI 0.65, dry sub-humid included. Omitting it here
        # understated the share for 60 of the first 317 units published - most
        # extremely Beirut, which is wholly dry sub-humid and was reported as
        # 0% dryland.
        row["dryland_share"] = sum(row[f"{key}_share"] for key in DRYLAND_KEYS)
        # Which admin level the row describes. Emitted here rather than added by
        # the caller: it is a property of the rows, and the published tables
        # document the column, so a writer that omits it produces a table
        # `satimg results build` will refuse - as it did.
        row["level"] = f"adm{level}"
        rows.append(row)
    return rows


def shares_sum_to_one(row, tol: float = 1e-9) -> bool:
    """The one assertion that catches a wrong nodata, a wrong denominator and a
    weighted-over-unweighted division all at once."""
    total = sum(row[f"{item.key}_share"] for item in CLASSES)
    return total != total or abs(total - 1.0) < tol  # nan passes: no valid pixels


# --------------------------------------------------------------------------- #
# pass B: onto the 1 km analysis grid
# --------------------------------------------------------------------------- #
def class_raster_path(root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root) / "global-ai" / "ai_class_v31.tif"


def build_class_raster(
    root: str | Path = DEFAULT_ROOT, *, force: bool = False, progress=None
) -> Path:
    """Classify the global grid once, into a uint8 class raster.

    Classifying before warping rather than after is deliberate and free: nearest
    -neighbour resampling is a pure selection, so it commutes with a pointwise
    map and the two orders give identical output. Doing it first means the
    warped product is a small uint8 raster whose nodata is 0 - a value that is
    not a class - instead of a uint16 whose every possible value is legitimate
    aridity, leaving no safe sentinel.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()

    out = class_raster_path(root)
    if out.exists() and not force:
        return out

    ai, et0 = ai_path(root), et0_path(root)
    with rasterio.open(ai) as src_ai, rasterio.open(et0) as src_et0:
        profile = src_ai.profile.copy()
        profile.update(
            dtype="uint8", nodata=NODATA_CODE, compress="lzw", predictor=2, tiled=True
        )
        et0_fill = src_et0.nodata
        height = src_ai.height
        out.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out, "w", **profile) as dst:
            for row in range(0, height, 1024):
                rows = min(1024, height - row)
                window = rasterio.windows.Window(0, row, src_ai.width, rows)
                values = src_ai.read(1, window=window)
                land = src_et0.read(1, window=window) != et0_fill
                dst.write(classify(values, land_mask=land), 1, window=window)
                if progress:
                    progress(min(row + rows, height), height)
            dst.set_band_description(
                1, f"UNEP aridity class from Global-AI v{VERSION} ({CLIMATOLOGY})"
            )
    del np
    return out


def country_class_raster(
    iso3: str,
    reference_raster: str | Path,
    *,
    root: str | Path = DEFAULT_ROOT,
    dest: str | Path = "data/regions",
    resampling: str = "nearest",
    suffix: str = "",
) -> Path:
    """Warp the class raster onto one country's existing 1 km grid."""
    from .raster import warp_to_grid

    out = Path(dest) / iso3 / "aridity" / f"{iso3}_aridity_class{suffix}.tif"
    return warp_to_grid(
        class_raster_path(root),
        reference_raster,
        out,
        src_nodata=NODATA_CODE,
        dst_nodata=NODATA_CODE,
        dtype="uint8",
        resampling=resampling,
        description=f"UNEP aridity class, Global-AI v{VERSION} ({CLIMATOLOGY})",
    )


def transition_crosstab(
    class_path: str | Path,
    raster_a: str | Path,
    raster_b: str | Path,
    *,
    nodata=None,
    threshold: float = 0.0,
) -> Dict[str, object]:
    """Cross-tabulate aridity against a lit -> unlit transition between two years.

    Reports the whole contingency table with its row totals, plus relative risk
    and lift. The bare share of losses that were non-arid is **not** reported
    alone: it is close to determined by the share of *lit* pixels that were
    non-arid, so it can look striking while carrying no information. Only a
    relative risk away from 1 says aridity is related to going dark.
    """
    np = _require_numpy()
    rasterio = _require_rasterio()

    def read(path):
        with rasterio.open(path) as src:
            fill = src.nodata if nodata is None else nodata
            data = src.read(1).astype("float64")
            if fill is not None:
                data[data == fill] = np.nan
            return data

    codes = read(class_path)
    before, after = read(raster_a), read(raster_b)
    valid = ~np.isnan(before) & ~np.isnan(after) & (codes > 0)

    lit_before = valid & (before > threshold)
    lost = lit_before & ~(after > threshold)
    desert = np.isin(codes, [c.code for c in CLASSES if c.key in DESERT_KEYS])

    def counts(mask):
        return {item.key: int((mask & (codes == item.code)).sum()) for item in CLASSES}

    lit_desert = int((lit_before & desert).sum())
    lit_other = int((lit_before & ~desert).sum())
    lost_desert = int((lost & desert).sum())
    lost_other = int((lost & ~desert).sum())

    risk_desert = lost_desert / lit_desert if lit_desert else float("nan")
    risk_other = lost_other / lit_other if lit_other else float("nan")
    lost_total = lost_desert + lost_other
    lit_total = lit_desert + lit_other
    share_lost = lost_other / lost_total if lost_total else float("nan")
    share_lit = lit_other / lit_total if lit_total else float("nan")

    return {
        "pixels_valid": int(valid.sum()),
        "lit_before": lit_total,
        "lost": lost_total,
        "lit_desert": lit_desert,
        "lit_nondesert": lit_other,
        "lost_desert": lost_desert,
        "lost_nondesert": lost_other,
        "loss_rate_desert": risk_desert,
        "loss_rate_nondesert": risk_other,
        # >1 means a non-desert lit pixel was likelier to go dark than a desert one.
        "relative_risk_nondesert": (
            risk_other / risk_desert if risk_desert else float("nan")
        ),
        "nondesert_share_of_losses": share_lost,
        "nondesert_share_of_lit": share_lit,
        "lift": share_lost / share_lit if share_lit else float("nan"),
        "lit_by_class": counts(lit_before),
        "lost_by_class": counts(lost),
    }


# --------------------------------------------------------------------------- #
# aridity against darkness, across countries
# --------------------------------------------------------------------------- #
#: The published cross-country table, per pool. As with the trends table, the
#: Arab League keeps its unprefixed name so adding a pool moves no published
#: file.
VS_LIGHT_TABLE = "aridity_vs_light.csv"


def vs_light_table(pool: str) -> str:
    from . import regions as R

    return VS_LIGHT_TABLE if pool == R.DEFAULT_POOL else f"{pool}_{VS_LIGHT_TABLE}"


#: The published figure, relative to the gallery root.
BANDS_FIGURE = "aridity/arid_vs_lit.png"

#: Where the per-country inputs live. Everything below reads committed CSVs
#: only - no rasters, no GADM, no network - so the table can be rebuilt on a
#: clone where ``data/`` is empty.
RESULTS_DIR = "results"

#: A unit counts as desert when more than half its area is hyper-arid or arid.
MAJORITY = 0.5

#: Darkness is defined against the **cross-country median** of the same column,
#: compared with a strict ``<``. Both halves of that sentence are load-bearing:
#: Iraq's Ninawa sits exactly on the median, so ``<=`` would move it and change
#: the counts. The cut is a choice, not a finding, and the figure built from
#: this table shows the whole continuum rather than only this one line.
DARK_QUANTILES = (0.10, 0.25, 0.50)
DARK_QUANTILE = 0.50

#: Published to 4 decimals, matching the per-country tables it is joined from.
ROUND_DP = 4

CELL_ANOMALOUS = "anomalously_dark"
CELL_DESERT_DARK = "desert_dark"
CELL_LIT_DESERT = "lit_desert"
CELL_ORDINARY = "ordinary"


def _read_csv(path) -> List[dict]:
    import csv

    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def light_scopes_for(iso3: str, gid: str) -> str:
    """Which light-derived exclusion scopes selected this unit, if any.

    The scopes are cut from observed darkness, not from climate; this column is
    what lets the two be compared rather than assumed equal.
    """
    from . import regions as R

    keys = [
        key
        for key in R.scope_keys(iso3)
        if key != R.SCOPE_ALL and gid in R.desert_scopes(iso3)[key].gid1
    ]
    return ";".join(keys)


def cell_of(majority_arid: bool, dark: bool) -> str:
    """The 2x2 of climate against light. Named so the join is checkable."""
    if majority_arid:
        return CELL_DESERT_DARK if dark else CELL_LIT_DESERT
    return CELL_ANOMALOUS if dark else CELL_ORDINARY


def dark_cut(values: Sequence[float], quantile: float = DARK_QUANTILE) -> float:
    """The darkness threshold, from the pooled cross-country distribution."""
    import statistics

    ordered = sorted(values)
    if not ordered:
        return float("nan")
    if quantile == 0.5:
        return statistics.median(ordered)
    return statistics.quantiles(ordered, n=100)[round(quantile * 100) - 1]


def vs_light(
    results_dir=RESULTS_DIR,
    countries: Optional[Sequence[str]] = None,
    *,
    pool: Optional[str] = None,
):
    """Join per-unit aridity to per-unit light, across one pool.

    **The darkness cut is pooled.** ``dark_2022`` compares each unit against the
    median ``mean_dn_2022`` *of the countries passed here*, so the same unit can
    be dark in one pool and lit in another. That is correct - "dark for this
    continent" and "dark for the Arab world" are different questions - and it
    means `dark_2022` and `cell` must never be compared across pools.

    ``mean_dn_*`` is the zonal table's ``mean_dn`` - the mean DN over the unit's
    land pixels - **not** a sum-of-lights density. The distinction matters
    because this project publishes a genuine ``density_sol_per_km2`` elsewhere,
    and the two differ by a few percent on a 1 km grid.
    """
    from . import regions as R

    if countries is not None:
        isos = list(countries)
    else:
        isos = list(R.pool_countries(pool or R.DEFAULT_POOL))
    root = Path(results_dir)

    rows: List[dict] = []
    for iso3 in isos:
        arid = _read_csv(root / iso3 / f"{iso3}_adm1_aridity.csv")
        zonal = _read_csv(root / iso3 / f"{iso3}_adm1_zonal.csv")
        if not arid or not zonal:
            continue
        by_year = {
            year: {r["gid"]: r for r in zonal if r["year"] == str(year)}
            for year in (1992, 2022)
        }
        for unit in arid:
            gid = unit["gid"]
            # A unit present in one source and not the other is dropped whole
            # rather than emitted with a hole in it.
            if any(gid not in by_year[year] for year in by_year):
                continue
            desert = float(unit["desert_share"])
            scopes = light_scopes_for(iso3, gid)
            rows.append(
                {
                    "iso3": iso3,
                    "gid": gid,
                    "name": unit["name"],
                    "desert_share": desert,
                    "dryland_share": float(unit["dryland_share"]),
                    "humid_share": float(unit["humid_share"]),
                    "area_km2": float(unit["area_km2"]),
                    "pixels_classified": int(unit["pixels_classified"]),
                    "mean_dn_1992": float(by_year[1992][gid]["mean_dn"]),
                    "mean_dn_2022": float(by_year[2022][gid]["mean_dn"]),
                    "majority_arid": desert > MAJORITY,
                    "light_scopes": scopes,
                    "in_light_scope": bool(scopes),
                }
            )

    cut = dark_cut([r["mean_dn_2022"] for r in rows])
    for row in rows:
        row["dark_2022"] = row["mean_dn_2022"] < cut
        row["cell"] = cell_of(row["majority_arid"], row["dark_2022"])
        for key in (
            "desert_share",
            "dryland_share",
            "humid_share",
            "area_km2",
            "mean_dn_1992",
            "mean_dn_2022",
        ):
            row[key] = round(row[key], ROUND_DP)
    return rows


def write_vs_light(
    results_dir=RESULTS_DIR,
    countries: Optional[Sequence[str]] = None,
    *,
    pool: Optional[str] = None,
):
    """Write the pool's aridity-against-light table; return (path, rows)."""
    from . import regions as R
    from .analysis import write_csv

    pool = pool or R.DEFAULT_POOL
    rows = vs_light(results_dir, countries, pool=pool)
    if not rows:
        return None, rows
    return write_csv(rows, Path(results_dir) / vs_light_table(pool)), rows
