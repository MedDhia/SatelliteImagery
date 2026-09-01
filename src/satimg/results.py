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

from .datasets.lrcc_dvnl import CRS_EPSG, NODATA, dtype_for_year

DEFAULT_SOURCE = Path("data/regions")
DEFAULT_DEST = Path("results")
INDEX_NAME = "README.md"


@dataclass(frozen=True)
class ResultTable:
    """One analysis table, and what its columns mean."""

    key: str
    source: str  # relative to the source root
    dest: str  # relative to the results root
    title: str
    description: str
    columns: Tuple[Tuple[str, str], ...]

    def source_path(self, root: str | Path) -> Path:
        return Path(root) / self.source

    def dest_path(self, root: str | Path) -> Path:
        return Path(root) / self.dest


#: Shared column glosses. Kept in one place because the same words mean the
#: same thing in every table, and a data dictionary that contradicts itself is
#: worse than none.
_SCOPE = (
    "unit set: `all`, `narrow` (excl. Tataouine/Kébili/Tozeur) or `wide` "
    "(excl. those plus Médenine/Gabès/Gafsa)"
)
_ZEROS = (
    "pixel zero treatment: `zeros_included` (all land pixels) or `lit_only` "
    "(DN > 0). Blank for subnational rows, where the unit is the observation"
)
_YEAR = "calendar year, 1992–2022"

TABLES: Tuple[ResultTable, ...] = (
    ResultTable(
        key="inequality-series",
        source="TUN/inequality/TUN_inequality_series.csv",
        dest="TUN/TUN_inequality_series.csv",
        title="Inequality series",
        description=(
            "The headline result: 12 series × 31 years. Pixel-level rows are "
            "the distribution of DN over land pixels; subnational rows are the "
            "distribution of **light density** (SOL/km²) over units, "
            "unweighted, so a governorate does not score high for being large."
        ),
        columns=(
            ("year", _YEAR),
            ("level", "`pixel`, `adm1` (governorate) or `adm2` (delegation)"),
            ("level_label", "human-readable form of `level`"),
            ("scope", _SCOPE),
            ("zeros", _ZEROS),
            ("n", "observations behind the index: pixels, or units"),
            ("gini", "Gini coefficient; `nan` if the distribution is all-zero"),
            ("theil_t", "Theil T = GE(1); maximum is ln(n)"),
            (
                "theil_l",
                (
                    "Theil L = GE(0); `nan` whenever any value is 0, since "
                    "ln(μ/x) diverges — which is why the zeros-included pixel "
                    "rows are undefined rather than large"
                ),
            ),
            ("sum_of_lights", "total DN over the scope, for reference"),
            ("lit_share", "fraction of land pixels with DN > 0; pixel rows only"),
        ),
    ),
    ResultTable(
        key="theil-decomposition",
        source="TUN/inequality/TUN_theil_decomposition.csv",
        dest="TUN/TUN_theil_decomposition.csv",
        title="Theil decomposition",
        description=(
            "Additive between/within splits of pixel-level Theil, for two "
            "groupings of the same pixels plus the nested three-way split they "
            "permit. `residual` is the identity check: it is ≤ 5.3e-14 on every "
            "defined row, so the split is exact rather than approximate."
        ),
        columns=(
            ("year", _YEAR),
            ("scope", _SCOPE),
            ("zeros", _ZEROS),
            ("measure", "`theil_t` or `theil_l`"),
            (
                "grouping",
                (
                    "`governorate`, `delegation`, or `nested` — the three-way "
                    "pixel → delegation → governorate split"
                ),
            ),
            ("total", "the index over all pixels in scope"),
            ("between", "between-group component"),
            ("within", "within-group component"),
            ("between_share", "`between` ÷ `total`"),
            ("within_share", "`within` ÷ `total`"),
            (
                "between_deleg_within_gov",
                (
                    "the middle term of the nested split: variation between "
                    "delegations of the same governorate. `nan` otherwise"
                ),
            ),
            ("residual", "|total − (between + within)|; a correctness check"),
            ("n_groups", "groups with at least one pixel in scope"),
        ),
    ),
    ResultTable(
        key="theil-by-unit",
        source="TUN/inequality/TUN_theil_by_unit.csv",
        dest="TUN/TUN_theil_by_unit.csv",
        title="Per-unit Theil contributions",
        description=(
            "What each governorate and delegation contributes to the total, "
            "for Theil T. This is the table that answers *which* unit drives a "
            "movement in the headline series."
        ),
        columns=(
            ("year", _YEAR),
            ("scope", _SCOPE),
            ("zeros", _ZEROS),
            ("grouping", "`governorate` or `delegation`"),
            ("unit", "unit name"),
            ("pixels", "land pixels in the unit, within scope"),
            ("mean_dn", "mean DN over those pixels"),
            ("population_share", "the unit's share of pixels"),
            ("value_share", "the unit's share of total light"),
            ("theil_t", "Theil T computed within the unit alone"),
            (
                "within_contribution",
                (
                    "the unit's term in the within component: `value_share` × "
                    "its own `theil_t`. These sum to `within` in the "
                    "decomposition"
                ),
            ),
        ),
    ),
    ResultTable(
        key="zonal-adm1",
        source="TUN/zonal/TUN_adm1_zonal.csv",
        dest="TUN/TUN_adm1_zonal.csv",
        title="Governorate zonal table",
        description=(
            "24 governorates × 31 years — the aggregation every subnational "
            "number is built from. Each land pixel belongs to exactly one unit, "
            "so `sum_of_lights` totals to the national figure for every year."
        ),
        columns=(
            ("year", _YEAR),
            ("gid", "GADM `GID_1` code — stable across GADM releases, unlike names"),
            ("name", "GADM `NAME_1`"),
            ("pixels", "land pixels assigned to the unit"),
            ("area_km2", "unit area from the GADM geometry, in EPSG:8857"),
            ("sum_of_lights", "Σ DN over the unit's pixels"),
            ("mean_dn", "`sum_of_lights` ÷ `pixels`"),
            (
                "density_sol_per_km2",
                (
                    "`sum_of_lights` ÷ `area_km2` — the quantity the "
                    "subnational Gini and Theil are computed over"
                ),
            ),
        ),
    ),
    ResultTable(
        key="zonal-adm2",
        source="TUN/zonal/TUN_adm2_zonal.csv",
        dest="TUN/TUN_adm2_zonal.csv",
        title="Delegation zonal table",
        description=(
            "268 delegations × 31 years, same columns as the governorate table. "
            "**Check `pixels` before trusting a density**: 11 delegations have "
            "fewer than 5 pixels and the smallest is a single 0.83 km² pixel, so "
            "their densities are extremely noisy. They are kept rather than "
            "dropped so the choice is yours and visible."
        ),
        columns=(
            ("year", _YEAR),
            ("gid", "GADM `GID_2` code"),
            ("name", "GADM `NAME_2`"),
            ("pixels", "land pixels assigned to the unit"),
            ("area_km2", "unit area from the GADM geometry, in EPSG:8857"),
            ("sum_of_lights", "Σ DN over the unit's pixels"),
            ("mean_dn", "`sum_of_lights` ÷ `pixels`"),
            ("density_sol_per_km2", "`sum_of_lights` ÷ `area_km2`"),
        ),
    ),
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


RASTER_SETS: Tuple[RasterSet, ...] = (
    RasterSet(
        key="tun-clipped",
        source="TUN/raster/*.tif",
        dest="TUN/raster",
        title="Tunisia clipped rasters",
        description=(
            "The 31 annual LRCC-DVNL grids cut to Tunisia — 368 × 856 px at "
            "1 km, `EPSG:8857`, nodata 127, LZW. Pixels outside the GADM "
            "national boundary are masked, not merely cropped, so Algerian and "
            "Libyan light does not leak into a bounding box. Every number in "
            "the tables above is computed from exactly these files."
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
                "**Three geotransforms, not one.** 1992–2007, 2008–2011 and "
                "2012–2022 differ by up to 3.9e-4 m (0.39 mm), inherited from "
                "the published rasters. Same pixel grid for every practical "
                "purpose, but an exact-equality check on the transform will "
                "reject the stack; compare with a tolerance."
            ),
            (
                "These carry a real `EPSG:8857`, unlike the published files, "
                "whose `LOCAL_CS` declaration needs `satimg raster fix-crs`."
            ),
        ),
    ),
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
        if not src.exists():
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
they were computed from — {tables} tables ({rows} rows) and {rasters} GeoTIFFs,
{size} in all.

*This file is generated by `satimg results build`; edit
[`src/satimg/results.py`](../src/satimg/results.py), not this page.*

These are committed while the 8.2 GB behind them is not, so the findings can be
checked, re-analysed or disputed — and, with the clipped rasters here,
**recomputed from scratch** — without downloading the LRCC-DVNL deposit and the
GADM world layer first. Regenerate them with:

```bash
satimg lrcc-dvnl extract    --country TUN --levels 0,1,2
satimg lrcc-dvnl inequality --country TUN
satimg results build            # copy into results/
satimg results build --check    # or just report drift, writing nothing
```

## Read this before quoting a number

1. **LRCC-DVNL forbids year-on-year decreases by construction.** A falling Gini
   is therefore partly imposed by the calibration, not purely observed, and
   genuine dimming is invisible in this series.
2. **2014 is a sensor handover** (DMSP → VIIRS) and a dtype change. Treat any
   2013 → 2014 step as a candidate artefact.
3. **DN is a relative index, not radiance.** A Gini of DN is not a Gini of
   income or output.
4. **`theil_l` is `nan` wherever any value is zero**, which is most
   zeros-included pixel rows. That is the measure being undefined, not a bug.

Full method and the remaining caveats: [`../docs/tunisia.md`](../docs/tunisia.md).

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
            name = f"LACC_{item.year}_TUN.tif" if item.year else "?"
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
