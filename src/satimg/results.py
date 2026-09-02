"""Publish the analysis outputs into the committed ``results/`` directory.

The figures show the findings; these are the findings. Five CSVs, all plain
text and diffable — a re-run that changes a number shows up in review rather
than silently repainting a picture — plus the 31 clipped Tunisia GeoTIFFs the
whole analysis is computed from, which at 2.6 MB are small enough to carry and
are the one artefact that lets someone recompute rather than merely re-read.

They are copied rather than regenerated because the analysis needs the rasters
and the GADM layers (8.2 GB, both gitignored); the point of committing them is
that a reader can check the numbers *without* that. A digest per table records
what was copied, so a stale ``results/`` is detectable with
``satimg results build --check``.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import regions as R
from .datasets.lrcc_dvnl import CRS_EPSG, NODATA, dtype_for_year

DEFAULT_SOURCE = Path("data/regions")
DEFAULT_DEST = Path("results")
INDEX_NAME = "README.md"


@dataclass(frozen=True)
class ResultTable:
    """One analysis table, and what its columns mean."""

    key: str
    source: str  # relative to the source root; "" if written straight to dest
    dest: str  # relative to the results root
    title: str
    description: str
    columns: Tuple[Tuple[str, str], ...]

    @property
    def in_place(self) -> bool:
        """True for a table its own command writes into ``results/`` directly.

        The cross-country tables read the published per-country CSVs, so they
        have nothing under ``data/`` to be copied from. They are catalogued all
        the same, because a committed table missing from the data dictionary is
        a number nobody can check.
        """
        return not self.source

    def source_path(self, root: str | Path) -> Optional[Path]:
        return None if self.in_place else Path(root) / self.source

    def dest_path(self, root: str | Path) -> Path:
        return Path(root) / self.dest


#: Shared column glosses. Kept in one place because the same words mean the
#: same thing in every table and every country, and a data dictionary that
#: contradicts itself is worse than none.
COUNTRY_NAMES = {
    "MAR": "Morocco",
    "DZA": "Algeria",
    "TUN": "Tunisia",
    "LBY": "Libya",
    "MRT": "Mauritania",
    "EGY": "Egypt",
    "SDN": "Sudan",
    "SAU": "Saudi Arabia",
    "YEM": "Yemen",
    "OMN": "Oman",
    "ARE": "United Arab Emirates",
    "QAT": "Qatar",
    "BHR": "Bahrain",
    "KWT": "Kuwait",
    "IRQ": "Iraq",
    "SYR": "Syria",
    "LBN": "Lebanon",
    "JOR": "Jordan",
    "PSE": "Palestine",
    "SOM": "Somalia",
    "DJI": "Djibouti",
    "COM": "Comoros",
}

_YEAR = "calendar year, 1992–2022"
_ZEROS = (
    "pixel zero treatment: `zeros_included` (all land pixels) or `lit_only` "
    "(DN > 0). Blank for subnational rows, where the unit is the observation"
)


def _scope_gloss(iso3: str) -> str:
    """The scope column, spelled out with this country's own scope keys."""
    parts = []
    for key in R.scope_keys(iso3):
        if key == R.SCOPE_ALL:
            parts.append("`all` (every unit)")
            continue
        scope = R.desert_scopes(iso3)[key]
        kind = "derived" if scope.derived else "hand-picked"
        parts.append(f"`{key}` ({kind}: {scope.label})")
    return "unit set — " + ", ".join(parts)


def _series_columns(iso3: str):
    level_words = ", ".join(
        f"`adm{lv}` ({R.level_title(iso3, lv)})"
        for lv in R.available_levels(iso3)
        if lv >= 1
    )
    return (
        ("year", _YEAR),
        ("level", f"`pixel`, {level_words}"),
        ("level_label", "human-readable form of `level`"),
        ("scope", _scope_gloss(iso3)),
        ("zeros", _ZEROS),
        ("n", "observations behind the index: pixels, or units"),
        ("gini", "Gini coefficient; `nan` if the distribution is all-zero"),
        ("theil_t", "Theil T = GE(1); maximum is ln(n)"),
        (
            "theil_l",
            (
                "Theil L = GE(0); `nan` whenever any value is 0, since ln(μ/x) "
                "diverges — which is why the zeros-included pixel rows are "
                "undefined rather than large"
            ),
        ),
        ("sum_of_lights", "total DN over the scope, for reference"),
        ("lit_share", "fraction of land pixels with DN > 0; pixel rows only"),
    )


def _decomposition_columns(iso3: str):
    inner = R.level_title(iso3, 2) if R.has_level(iso3, 2) else None
    outer = R.level_title(iso3, 1)
    grouping = f"`{outer}`" + (
        f", `{inner}`, or `nested` — the three-way pixel → {inner} → {outer} split"
        if inner
        else " only; GADM has no admin-2 layer for this country, so there is no "
        "`nested` row"
    )
    return (
        ("year", _YEAR),
        ("scope", _scope_gloss(iso3)),
        ("zeros", _ZEROS),
        ("measure", "`theil_t` or `theil_l`"),
        ("grouping", grouping),
        ("total", "the index over all pixels in scope"),
        ("between", "between-group component"),
        ("within", "within-group component"),
        ("between_share", "`between` ÷ `total`"),
        ("within_share", "`within` ÷ `total`"),
        (
            "between_deleg_within_gov",
            (
                "the middle term of the nested split: variation between "
                "admin-2 units of the same admin-1 unit. `nan` otherwise"
            ),
        ),
        ("residual", "|total − (between + within)|; a correctness check"),
        ("n_groups", "groups with at least one pixel in scope"),
    )


def _by_unit_columns(iso3: str):
    levels = [R.level_title(iso3, lv) for lv in R.available_levels(iso3) if lv >= 1]
    return (
        ("year", _YEAR),
        ("scope", _scope_gloss(iso3)),
        ("zeros", _ZEROS),
        ("grouping", " or ".join(f"`{w}`" for w in levels)),
        ("unit", "unit name"),
        ("pixels", "land pixels in the unit, within scope"),
        ("mean_dn", "mean DN over those pixels"),
        ("population_share", "the unit's share of pixels"),
        ("value_share", "the unit's share of total light"),
        ("theil_t", "Theil T computed within the unit alone"),
        (
            "within_contribution",
            (
                "the unit's term in the within component: `value_share` × its "
                "own `theil_t`. These sum to `within` in the decomposition"
            ),
        ),
    )


def _zonal_columns(level: int):
    return (
        ("year", _YEAR),
        (
            "gid",
            f"GADM `GID_{level}` code — stable across releases, unlike names",
        ),
        ("name", f"GADM `NAME_{level}`"),
        ("pixels", "land pixels assigned to the unit"),
        ("area_km2", "unit area from the GADM geometry, in EPSG:8857"),
        ("sum_of_lights", "Σ DN over the unit's pixels"),
        ("mean_dn", "`sum_of_lights` ÷ `pixels`"),
        (
            "density_sol_per_km2",
            (
                "`sum_of_lights` ÷ `area_km2` — the quantity the subnational "
                "Gini and Theil are computed over"
            ),
        ),
    )


def _aridity_columns(iso3: str):
    word = R.level_title(iso3, 1)
    return (
        ("iso3", "ISO 3166-1 alpha-3 country code"),
        ("gid", f"GADM identifier of the {word}"),
        ("name", f"GADM name of the {word}"),
        ("area_km2", "unit area on the WGS 84 ellipsoid"),
        ("pixels_total", "aridity cells falling in the unit"),
        (
            "pixels_classified",
            "cells carrying a real aridity value; the rest are ocean or "
            "permanent ice, and are excluded from every share below",
        ),
        ("pixels_unclassified", "`pixels_total` − `pixels_classified`"),
        ("hyper_arid_share", "area share with aridity index < 0.03"),
        ("arid_share", "0.03 ≤ AI < 0.20"),
        ("semi_arid_share", "0.20 ≤ AI < 0.50"),
        ("dry_subhumid_share", "0.50 ≤ AI < 0.65"),
        ("humid_share", "AI ≥ 0.65"),
        (
            "desert_share",
            "`hyper_arid_share` + `arid_share` — the UNEP definition of desert",
        ),
        ("dryland_share", "everything below AI 0.65, i.e. 1 − `humid_share`"),
        ("level", "admin level the row describes; always `adm1` here"),
    )


#: Tables computed *from* the published per-country CSVs rather than from the
#: rasters, and so written straight into ``results/`` by their own commands.
CROSS_TABLES = (
    ResultTable(
        key="aridity-vs-light",
        source="",
        dest="aridity_vs_light.csv",
        title="Aridity against darkness, every admin-1 unit",
        description=(
            "One row per admin-1 unit across all 22 countries, pairing what "
            "the climate says with what the light says. The table behind "
            "[`../docs/aridity.md`](../docs/aridity.md), which refutes most of "
            "what this repository previously asserted about which dark regions "
            "are desert."
        ),
        columns=(
            ("iso3", "ISO 3166-1 alpha-3 country code"),
            ("gid", "GADM identifier of the unit"),
            ("name", "GADM name of the unit"),
            ("desert_share", "area share that is hyper-arid or arid"),
            ("dryland_share", "area share below aridity index 0.65"),
            ("humid_share", "area share at or above 0.65"),
            ("area_km2", "unit area on the WGS 84 ellipsoid"),
            ("pixels_classified", "aridity cells carrying a real value"),
            (
                "mean_dn_1992",
                "mean DN over the unit's land pixels in 1992 — the zonal "
                "tables' `mean_dn`, **not** a density: `density_sol_per_km2` "
                "elsewhere in `results/` is that, and the two differ by a few "
                "percent on a 1 km grid",
            ),
            ("mean_dn_2022", "the same for 2022; the column darkness is cut on"),
            ("majority_arid", "`desert_share` > 0.5"),
            (
                "light_scopes",
                "the light-derived exclusion scopes this unit belongs to, if "
                "any; blank when the light rule never selected it",
            ),
            ("in_light_scope", "whether `light_scopes` is non-empty"),
            (
                "dark_2022",
                "whether `mean_dn_2022` is strictly below the cross-country "
                "median — the cut is a choice, and the set it produces is "
                "sensitive to it; Iraq's Ninawa sits exactly on the median, so "
                "the strict `<` is load-bearing",
            ),
            (
                "cell",
                "which of the four aridity × darkness cells the unit falls in",
            ),
        ),
    ),
    ResultTable(
        key="trends-by-country",
        source="",
        dest="trends_by_country.csv",
        title="Pace of inequality change, all 22 countries",
        description=(
            "Log-linear rates of change fitted to the published inequality "
            "series — how fast spatial inequality is moving, and whether the "
            "movement is convergence among lit places or light reaching new "
            "ground. Three fit windows per measure, because 18 of 22 countries "
            "change pace at exactly the 2014 sensor handover and the eras must "
            "not be compared. See [`../docs/arab-world.md`]"
            "(../docs/arab-world.md)."
        ),
        columns=(
            ("iso3", "ISO 3166-1 alpha-3 country code"),
            (
                "measure",
                "`total` (Theil T over all land pixels), `intensive` (Theil T "
                "over lit pixels only), `extensive` (share of land pixels "
                "lit), `between_share` (share of Theil T lying between "
                "admin-1 units)",
            ),
            ("measure_note", "the same, spelled out"),
            (
                "window",
                "`full` 1992–2022, `dmsp` 1992–2013, `viirs` 2014–2022; the "
                "two eras are not comparable to each other",
            ),
            ("first_year", "first year with a usable value in the window"),
            ("last_year", "last such year"),
            ("n_years", "usable observations behind the fit"),
            (
                "percent_per_year",
                "the fitted slope of ln(value) against year, as a percentage",
            ),
            (
                "r_squared",
                "goodness of the straight-line fit; `nan` for a series with no "
                "variation at all, which has no slope to explain",
            ),
            (
                "half_life_years",
                "ln(2) ÷ |rate| — years to halve; `nan` for a series that is "
                "not falling, because a rising series has no half-life",
            ),
            ("direction", "`falling`, `rising`, `flat` or `undefined`"),
            (
                "monotone",
                "whether `r_squared` clears the threshold; `False` means one "
                "slope does not describe the series and the rate is a "
                "direction, not a pace",
            ),
            ("trajectory", "the country's typology label, assigned by rule"),
            ("trajectory_reason", "which rule assigned it, in one clause"),
        ),
    ),
)


def _country_tables(iso3: str):
    """The analysis tables for one country."""
    name = COUNTRY_NAMES.get(iso3, iso3)
    tables = [
        ResultTable(
            key=f"{iso3}-inequality-series",
            source=f"{iso3}/inequality/{iso3}_inequality_series.csv",
            dest=f"{iso3}/{iso3}_inequality_series.csv",
            title=f"{name}: inequality series",
            description=(
                "The headline result. Pixel-level rows are the distribution of "
                "DN over land pixels; subnational rows are the distribution of "
                "**light density** (SOL/km²) over units, unweighted, so a large "
                "unit does not score high merely for being large."
            ),
            columns=_series_columns(iso3),
        ),
        ResultTable(
            key=f"{iso3}-theil-decomposition",
            source=f"{iso3}/inequality/{iso3}_theil_decomposition.csv",
            dest=f"{iso3}/{iso3}_theil_decomposition.csv",
            title=f"{name}: Theil decomposition",
            description=(
                "Additive between/within splits of pixel-level Theil. "
                "`residual` is the identity check: it stays at machine "
                "precision on every defined row, so the split is exact rather "
                "than approximate."
            ),
            columns=_decomposition_columns(iso3),
        ),
        ResultTable(
            key=f"{iso3}-theil-by-unit",
            source=f"{iso3}/inequality/{iso3}_theil_by_unit.csv",
            dest=f"{iso3}/{iso3}_theil_by_unit.csv",
            title=f"{name}: per-unit Theil contributions",
            description=(
                "What each unit contributes to the total, for Theil T. The "
                "table that answers *which* unit drives a movement in the "
                "headline series."
            ),
            columns=_by_unit_columns(iso3),
        ),
    ]
    tables.append(
        ResultTable(
            key=f"{iso3}-adm1-aridity",
            source=f"{iso3}/aridity/{iso3}_adm1_aridity.csv",
            dest=f"{iso3}/{iso3}_adm1_aridity.csv",
            title=f"{name}: {R.level_title(iso3, 1)} aridity",
            description=(
                "Climate, measured independently of light. Each unit's share "
                "of the five UNEP aridity classes from the Global Aridity "
                "Index v3.1, on true cell areas rather than pixel counts. This "
                "is what the light-derived exclusion scopes are checked "
                "against in [`../docs/aridity.md`](../docs/aridity.md)."
            ),
            columns=_aridity_columns(iso3),
        )
    )
    for level in (lv for lv in R.available_levels(iso3) if lv >= 1):
        word = R.level_title(iso3, level)
        note = (
            " **Check `pixels` before trusting a density**: the smallest units "
            "cover only a pixel or two, so their densities are extremely noisy. "
            "They are kept rather than dropped silently, so the choice is yours "
            "and visible."
            if level == 2
            else ""
        )
        tables.append(
            ResultTable(
                key=f"{iso3}-zonal-adm{level}",
                source=f"{iso3}/zonal/{iso3}_adm{level}_zonal.csv",
                dest=f"{iso3}/{iso3}_adm{level}_zonal.csv",
                title=f"{name}: {word} zonal table",
                description=(
                    f"Per-{word} aggregation, the basis of every subnational "
                    "number above. Each land pixel belongs to exactly one unit, "
                    "so `sum_of_lights` totals to the national figure for every "
                    "year." + note
                ),
                columns=_zonal_columns(level),
            )
        )
    return tables


TABLES = (
    tuple(t for iso3 in R.ARAB_LEAGUE for t in _country_tables(iso3)) + CROSS_TABLES
)


@dataclass(frozen=True)
class RasterSet:
    """A directory of published rasters, and what a reader needs to know."""

    key: str
    source: str  # glob, relative to the source root
    dest: str  # directory, relative to the results root
    title: str
    description: str
    notes: Tuple[str, ...] = ()

    def sources(self, root: str | Path) -> List[Path]:
        return sorted(Path(root).glob(self.source))


def _country_rasters(iso3: str) -> RasterSet:
    name = COUNTRY_NAMES.get(iso3, iso3)
    return RasterSet(
        key=f"{iso3}-clipped",
        source=f"{iso3}/raster/*.tif",
        dest=f"{iso3}/raster",
        title=f"{name}: clipped rasters",
        description=(
            f"The 31 annual LRCC-DVNL grids cut to {name} at 1 km, "
            "`EPSG:8857`, nodata 127, LZW. Pixels outside the GADM national "
            "boundary are masked, not merely cropped, so a neighbour's light "
            "does not leak into a bounding box. Every number in this country's "
            "tables is computed from exactly these files."
        ),
        notes=(
            (
                "**The series is not dtype-homogeneous.** 1992 is `int8`, "
                "1993–2013 `int16`, and 2014–2022 `float32` carrying "
                "*fractional* DN. Reading the stack with one fixed dtype "
                "silently truncates the VIIRS era — a downward bias in exactly "
                "the half of the series where lit area grows fastest."
            ),
            (
                "**Geotransforms are not identical across years.** They differ "
                "by fractions of a millimetre, inherited from the published "
                "rasters. Same pixel grid for every practical purpose, but an "
                "exact-equality check on the transform will reject the stack; "
                "compare with a tolerance."
            ),
            (
                "These carry a real `EPSG:8857`, unlike the published files, "
                "whose `LOCAL_CS` declaration needs `satimg raster fix-crs`."
            ),
        ),
    )


RASTER_SETS: Tuple[RasterSet, ...] = tuple(
    _country_rasters(iso3) for iso3 in R.ARAB_LEAGUE
)


def raster_set_by_key(key: str) -> RasterSet:
    for raster_set in RASTER_SETS:
        if raster_set.key == key:
            return raster_set
    raise KeyError(f"unknown raster set {key!r}")


def year_of(path: str | Path) -> Optional[int]:
    """Year encoded in a published filename, e.g. ``LACC_1992_TUN.tif``."""
    for chunk in Path(path).stem.split("_"):
        if len(chunk) == 4 and chunk.isdigit():
            return int(chunk)
    return None


def table_by_key(key: str) -> ResultTable:
    for table in TABLES:
        if table.key == key:
            return table
    raise KeyError(f"unknown result table {key!r}")


# --------------------------------------------------------------------------- #
# inspection
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TableStats:
    """Measured facts about a published table, for the index and the check."""

    rows: int
    size_bytes: int
    sha256: str
    header: Tuple[str, ...]


def digest(path: str | Path, chunk: int = 1 << 20) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            sha.update(block)
    return sha.hexdigest()


def inspect(path: str | Path) -> TableStats:
    """Row count and header read from the file, never from the catalogue."""
    path = Path(path)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader, []))
        rows = sum(1 for _ in reader)
    return TableStats(
        rows=rows, size_bytes=path.stat().st_size, sha256=digest(path), header=header
    )


def undocumented_columns(table: ResultTable, header: Sequence[str]) -> List[str]:
    """Columns present in the file that the catalogue does not explain."""
    documented = {name for name, _ in table.columns}
    return [name for name in header if name not in documented]


def missing_columns(table: ResultTable, header: Sequence[str]) -> List[str]:
    """Columns the catalogue documents that the file does not have."""
    present = set(header)
    return [name for name, _ in table.columns if name not in present]


@dataclass(frozen=True)
class RasterStats:
    """Measured facts about a published raster.

    The georeferencing fields are ``None`` when rasterio is not installed: the
    digest and the size still work on a bare clone, so ``--check`` keeps
    functioning without the raster extra.
    """

    size_bytes: int
    sha256: str
    year: Optional[int] = None
    dtype: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    epsg: Optional[int] = None
    nodata: Optional[float] = None


def inspect_raster(path: str | Path) -> RasterStats:
    """Size, digest and — when rasterio is available — the raster profile."""
    path = Path(path)
    base = dict(size_bytes=path.stat().st_size, sha256=digest(path), year=year_of(path))
    try:
        import rasterio
    except ImportError:
        return RasterStats(**base)
    with rasterio.open(path) as src:
        return RasterStats(
            **base,
            dtype=src.dtypes[0],
            width=src.width,
            height=src.height,
            epsg=src.crs.to_epsg() if src.crs else None,
            nodata=src.nodata,
        )


def raster_problems(stats: Sequence[RasterStats]) -> List[str]:
    """Reasons these rasters should not be published as one coherent set.

    The dtype rule is the one that matters: a year stored at the wrong width is
    the bug this project already shipped once, and committing it would bake a
    silently truncated series into the repository.
    """
    problems: List[str] = []
    if not stats:
        return problems

    for item in stats:
        if item.year is None:
            problems.append(f"{item.sha256[:12]}: no year in the filename")
            continue
        if item.dtype is None:
            continue  # rasterio absent; nothing to check against
        expected = dtype_for_year(item.year)
        if item.dtype != expected:
            problems.append(
                f"{item.year}: dtype {item.dtype}, documented era says {expected}"
            )
        if item.epsg != CRS_EPSG:
            problems.append(f"{item.year}: EPSG {item.epsg}, expected {CRS_EPSG}")
        if item.nodata != NODATA:
            problems.append(f"{item.year}: nodata {item.nodata}, expected {NODATA}")

    # One country, one window: a differing size means two different clips got
    # mixed into one directory.
    shapes = {(s.width, s.height) for s in stats if s.width is not None}
    if len(shapes) > 1:
        problems.append(f"mixed raster sizes: {sorted(shapes)}")
    return problems


# --------------------------------------------------------------------------- #
# publishing
# --------------------------------------------------------------------------- #
@dataclass
class PublishResult:
    copied: List[Path] = field(default_factory=list)
    unchanged: List[Path] = field(default_factory=list)
    missing: List[object] = field(default_factory=list)
    stats: Dict[str, TableStats] = field(default_factory=dict)
    #: Per raster set, its files' stats ordered by year.
    rasters: Dict[str, List[RasterStats]] = field(default_factory=dict)

    @property
    def table_bytes(self) -> int:
        return sum(s.size_bytes for s in self.stats.values())

    @property
    def raster_bytes(self) -> int:
        return sum(r.size_bytes for group in self.rasters.values() for r in group)

    @property
    def total_bytes(self) -> int:
        return self.table_bytes + self.raster_bytes

    @property
    def raster_count(self) -> int:
        return sum(len(group) for group in self.rasters.values())

    @property
    def total_rows(self) -> int:
        return sum(s.rows for s in self.stats.values())


def _publish_one(src: Path, dest: Path, result: PublishResult, check: bool) -> bool:
    """Copy ``src`` to ``dest`` unless identical. Returns True if it differed."""
    same = dest.exists() and digest(dest) == digest(src)
    if not same and not check:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    (result.unchanged if same else result.copied).append(dest)
    return not same


def build(
    source_root: str | Path = DEFAULT_SOURCE,
    dest_root: str | Path = DEFAULT_DEST,
    *,
    tables: Sequence[ResultTable] = TABLES,
    raster_sets: Sequence[RasterSet] = RASTER_SETS,
    check: bool = False,
) -> PublishResult:
    """Copy the analysis tables into ``results/``.

    ``check`` inspects without writing, so CI can fail on a stale directory
    rather than shipping numbers that no longer match the figures beside them.
    """
    result = PublishResult()
    for table in tables:
        src = table.source_path(source_root)
        dest = table.dest_path(dest_root)
        if src is None or not src.exists():
            # A published table with no source is not an error here: the check
            # run happens on a clone, where data/ is empty by design.
            if dest.exists():
                result.stats[table.key] = inspect(dest)
                result.unchanged.append(dest)
            else:
                result.missing.append(table)
            continue

        _publish_one(src, dest, result, check)
        result.stats[table.key] = inspect(dest if dest.exists() else src)

    for raster_set in raster_sets:
        sources = raster_set.sources(source_root)
        dest_dir = Path(dest_root) / raster_set.dest
        if not sources:
            # Same reasoning as the tables: on a clone the source is absent but
            # the published copies are what we should describe.
            published = sorted(dest_dir.glob("*.tif"))
            if published:
                result.unchanged.extend(published)
                result.rasters[raster_set.key] = [
                    inspect_raster(path) for path in published
                ]
            else:
                result.missing.append(raster_set)
            continue

        stats = []
        for src in sources:
            dest = dest_dir / src.name
            _publish_one(src, dest, result, check)
            stats.append(inspect_raster(dest if dest.exists() else src))
        result.rasters[raster_set.key] = sorted(
            stats, key=lambda s: (s.year is None, s.year)
        )
    return result


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
_PREAMBLE = """\
# Results

The numbers behind every figure in [`figures/`](../figures/), and the rasters
they were computed from — {tables} tables ({rows} rows) and {rasters} GeoTIFFs
across {countries} countries, {size} in all.

*This file is generated by `satimg results build`; edit
[`src/satimg/results.py`](../src/satimg/results.py), not this page.*

These are committed while the 8.2 GB behind them is not, so the findings can be
checked, re-analysed or disputed — and, with the clipped rasters here,
**recomputed from scratch** — without downloading the LRCC-DVNL deposit and the
GADM world layer first. Regenerate them with:

```bash
ISOS=$(python -c "from satimg.regions import ARAB_LEAGUE as A; print(*A)")
for ISO in $ISOS; do
  satimg lrcc-dvnl extract    --country "$ISO" --levels 0,1,2
  satimg lrcc-dvnl inequality --country "$ISO"
done
satimg results build            # copy into results/
satimg results build --check    # or just report drift, writing nothing
```

GADM 4.1 has no ADM_2 layer for **Libya, Bahrain, Comoros, Kuwait or Qatar**,
so those analyses stop at admin-1 and have no nested three-way Theil split.
That gap is real, not an omission.

## Read this before quoting a number

1. **A lit pixel never dims here — it goes out.** Every decrease in this series
   is a lit → unlit transition, so gradual dimming is invisible and a falling
   Gini is partly imposed. Catastrophic loss, though, is real signal: Syria's
   national sum of lights falls 54% between 2010 and 2016.
2. **2014 is a sensor handover** (DMSP → VIIRS) and a dtype change. Treat any
   2013 → 2014 step as a candidate artefact.
3. **DN is a relative index, not radiance.** A Gini of DN is not a Gini of
   income or output.
4. **`theil_l` is `nan` wherever any value is zero**, which is most
   zeros-included pixel rows. That is the measure being undefined, not a bug.

Full method and the remaining caveats:
[`../docs/arab-world.md`](../docs/arab-world.md).

## Terms

Derived from GADM 4.1 boundaries (unit codes, names, areas, and the national
outline the rasters are masked to) and LRCC-DVNL imagery. Like the figures,
**nothing here is covered by the repository's MIT licence** — GADM is
non-commercial with no redistribution. No GADM geometry is included as
geometry; the `gid`/`name`/`area_km2` columns are the attributes needed to
interpret a row at all, and the rasters carry the boundary only as a 1 km
nodata footprint. See [`../figures/NOTICE.md`](../figures/NOTICE.md).

"""


def _human_bytes(total: int) -> str:
    value = float(total)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def write_index(
    result: PublishResult,
    dest_root: str | Path = DEFAULT_DEST,
    *,
    tables: Sequence[ResultTable] = TABLES,
    raster_sets: Sequence[RasterSet] = RASTER_SETS,
) -> Path:
    """Write the data dictionary that documents every published column."""
    dest_root = Path(dest_root)
    published = [t for t in tables if t.key in result.stats]
    lines = [
        _PREAMBLE.format(
            tables=len(published),
            rows=f"{result.total_rows:,}",
            rasters=result.raster_count,
            countries=len({t.dest.split("/")[0] for t in published if "/" in t.dest}),
            size=_human_bytes(result.total_bytes),
        )
    ]

    lines.append("## Tables\n")
    lines.append("| Table | Rows | Size |")
    lines.append("|---|---:|---:|")
    for table in published:
        stats = result.stats[table.key]
        lines.append(
            f"| [`{table.dest}`]({table.dest}) | {stats.rows:,} | "
            f"{_human_bytes(stats.size_bytes)} |"
        )
    lines.append("")

    for table in published:
        stats = result.stats[table.key]
        lines.append(f"## {table.title}\n")
        lines.append(f"[`{table.dest}`]({table.dest}) — {stats.rows:,} rows\n")
        lines.append(f"{table.description}\n")
        lines.append("| Column | Meaning |")
        lines.append("|---|---|")
        # Ordered by the file, not the catalogue, so the dictionary reads in the
        # order a reader actually meets the columns.
        gloss = dict(table.columns)
        for name in stats.header:
            lines.append(f"| `{name}` | {gloss.get(name, '—')} |")
        lines.append("")
        lines.append(f"`sha256:{stats.sha256}`\n")

    for raster_set in raster_sets:
        stats = result.rasters.get(raster_set.key)
        if not stats:
            continue
        lines.append(f"## {raster_set.title}\n")
        total = sum(s.size_bytes for s in stats)
        lines.append(
            f"`{raster_set.dest}/` — {len(stats)} files, {_human_bytes(total)}\n"
        )
        lines.append(f"{raster_set.description}\n")
        for note in raster_set.notes:
            lines.append(f"* {note}")
        if raster_set.notes:
            lines.append("")

        lines.append("| Year | dtype | Size | File |")
        lines.append("|---|---|---:|---|")
        for item in stats:
            iso3 = raster_set.dest.split("/")[0]
            name = f"LACC_{item.year}_{iso3}.tif" if item.year else "?"
            link = f"{raster_set.dest}/{name}"
            lines.append(
                f"| {item.year or '—'} | `{item.dtype or '—'}` | "
                f"{_human_bytes(item.size_bytes)} | [`{name}`]({link}) |"
            )
        lines.append("")

    out = dest_root / INDEX_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
