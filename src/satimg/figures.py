"""Assemble the committed figure gallery under ``figures/``.

Everything the renderers write lands under ``data/``, which is gitignored: at
full resolution the 608 figures are 439 MB, which no repository should carry.
This module copies them into ``figures/`` at a size a browser and a ``git
clone`` can afford - the same 608 figures, 47 MB - and generates the index that
the top-level README links to, so the gallery is reachable from the first page.

Two size tiers, because the figures are read differently:

* **Summary figures** (the charts and the small-multiple panels, 19 files) keep
  their native pixels. These are the ones a reader actually studies, and the
  panels pack 31 years into one image - downscaling them destroys the point.
* **Per-year series** (589 files) are capped at :data:`WEB_MAX_PX` on the longest
  side. Browsing 31 near-identical frames does not need print resolution.

Both tiers are re-encoded to a 256-colour palette. Matplotlib writes 24-bit
RGBA, but a colormap ramp plus flat chrome uses far fewer distinct values than
that, so the palette costs nothing visible and saves ~3.5x. Full-resolution
originals stay reproducible: rerun the renderer, or lift ``--max-px``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import regions as R

DEFAULT_SOURCE = Path("data")
DEFAULT_DEST = Path("figures")

#: Longest side, in pixels, of a per-year figure in the gallery.
WEB_MAX_PX = 1200
#: Adaptive palette size for the re-encode.
PALETTE_COLORS = 256

#: Index headings. Summary first - the charts are what a reader should meet
#: before 600 map frames - then one section per country, then the world.
GROUP_SUMMARY = "Summary figures"
GROUP_GLOBAL = "Global overlays"


#: Countries with a full country workflow, in the order the gallery lists them.
COUNTRIES = R.ARAB_LEAGUE
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


def country_group(iso3: str) -> str:
    return f"{COUNTRY_NAMES.get(iso3, iso3)} ({iso3})"


GROUP_ORDER = (
    GROUP_SUMMARY,
    *(country_group(iso3) for iso3 in COUNTRIES),
    GROUP_GLOBAL,
)

#: Raster palettes, and the output directory each renderer run wrote to. The
#: default run has no suffix on disk; the gallery names it explicitly so a
#: reader does not have to know which one "png" meant.
RASTER_PALETTES = (
    ("inferno", "png"),
    ("magma", "png-magma"),
    ("cividis", "png-cividis"),
)
#: Choropleth palettes, and the suffix each run appended to its scale directory.
CHOROPLETH_PALETTES = (("ylorrd", ""), ("cividis", "-cividis"))

SCALE_LABELS = {
    "absolute": "absolute (shared scale across years)",
    "relative": "relative to the national mean of the same year",
}


def _suffix(palette: str, default: str) -> str:
    """Directory suffix a renderer run used: the default run wrote none."""
    return "" if palette == default else f"-{palette}"


@dataclass(frozen=True)
class FigureSet:
    """One directory of the gallery, and where its figures come from."""

    key: str
    group: str
    title: str
    source: str  # glob, relative to the source root
    dest: str  # directory, relative to the gallery root
    full_res: bool = False
    caption: str = ""

    def sources(self, source_root: str | Path) -> List[Path]:
        return sorted(Path(source_root).glob(self.source))


def _country_sets(iso3: str) -> List[FigureSet]:
    """Every gallery directory for one country."""
    group = country_group(iso3)
    name = COUNTRY_NAMES.get(iso3, iso3)
    levels = R.available_levels(iso3)
    sets = [
        FigureSet(
            key=f"{iso3}-charts",
            group=GROUP_SUMMARY,
            title=f"{name}: inequality series and Theil decomposition",
            source=f"regions/{iso3}/inequality/*.png",
            dest=f"{iso3}/charts",
            full_res=True,
            caption=(
                "Gini, Theil T and Theil L over 1992–2022, and the additive "
                "between/within split of Theil."
            ),
        )
    ]

    for palette, _ in RASTER_PALETTES:
        sets.append(
            FigureSet(
                key=f"{iso3}-panel-raster-{palette}",
                group=group,
                title=f"Raster panels ({palette})",
                source=(f"regions/{iso3}/panel{_suffix(palette, 'inferno')}/*.png"),
                dest=f"{iso3}/panels/raster/{palette}",
                full_res=True,
                caption="All 31 years of one admin level in a single small-multiple.",
            )
        )
    for palette, _ in CHOROPLETH_PALETTES:
        sets.append(
            FigureSet(
                key=f"{iso3}-panel-choropleth-{palette}",
                group=group,
                title=f"Choropleth panels ({palette})",
                source=(
                    f"regions/{iso3}/choropleth/panel{_suffix(palette, 'ylorrd')}/*.png"
                ),
                dest=f"{iso3}/panels/choropleth/{palette}",
                full_res=True,
                caption="Units filled by their own light level, all 31 years at once.",
            )
        )

    for palette, src_dir in RASTER_PALETTES:
        for level in levels:
            sets.append(
                FigureSet(
                    key=f"{iso3}-raster-{palette}-adm{level}",
                    group=group,
                    title=(f"adm{level} · {R.level_title(iso3, level)} · {palette}"),
                    source=f"regions/{iso3}/{src_dir}/adm{level}/*.png",
                    dest=f"{iso3}/raster/{palette}/adm{level}",
                    caption="Clipped LRCC-DVNL imagery with GADM boundaries over it.",
                )
            )

    for palette, suffix in CHOROPLETH_PALETTES:
        for level in (lv for lv in levels if lv >= 1):
            for scale in ("absolute", "relative"):
                sets.append(
                    FigureSet(
                        key=f"{iso3}-choropleth-{palette}-adm{level}-{scale}",
                        group=group,
                        title=(
                            f"adm{level} · {R.level_title(iso3, level)} · "
                            f"{scale} · {palette}"
                        ),
                        source=(
                            f"regions/{iso3}/choropleth/adm{level}/"
                            f"{scale}{suffix}/*.png"
                        ),
                        dest=f"{iso3}/choropleth/{palette}/adm{level}/{scale}",
                        caption=SCALE_LABELS[scale],
                    )
                )
    return sets


def _build_sets() -> Tuple[FigureSet, ...]:
    """Enumerate the gallery: every country, then the world.

    Built in loops so a new country is one entry in :data:`COUNTRIES` and a new
    palette is one entry in the palette tuples. Levels come from
    :func:`satimg.regions.available_levels`, so Libya simply produces no
    admin-2 directories rather than a set of dead globs.
    """
    sets: List[FigureSet] = []
    for iso3 in COUNTRIES:
        sets.extend(_country_sets(iso3))

    for level in (0, 1):
        sets.append(
            FigureSet(
                key=f"global-adm{level}",
                group=GROUP_GLOBAL,
                title=f"World · GADM adm{level} boundaries",
                source=f"overlays/lrcc-dvnl/adm{level}/png/*.png",
                dest=f"global/adm{level}",
                caption=(
                    "The full 34 488 × 15 315 grid, downsampled for display; "
                    "the georeferenced two-band GeoTIFFs stay under `data/`."
                ),
            )
        )
    return tuple(sets)


FIGURE_SETS: Tuple[FigureSet, ...] = _build_sets()

#: Featured on the repository's first page. Kept here so the root README, the
#: gallery index and the tests cannot disagree about which files those are, or
#: about what each one is meant to show.
HERO = (
    (
        "TUN/charts/TUN_inequality_series.png",
        "Tunisia, three inequality measures, four levels of aggregation, 1992–2022.",
    ),
    (
        "TUN/charts/TUN_theil_decomposition.png",
        (
            "Where the inequality sits: Theil T halves, yet the share of it "
            "that is *between* governorates rises — convergence happened "
            "within regions, not between them."
        ),
    ),
    (
        "TUN/panels/choropleth/ylorrd/TUN_adm1_relative_1992-2022.png",
        (
            "Governorates coloured by their own light density relative to the "
            "national mean of the same year — 31 years at once."
        ),
    ),
    (
        "global/adm1/LACC_2022_adm1.png",
        "The 2022 global grid with GADM subnational boundaries over it.",
    ),
)


def set_by_key(key: str) -> FigureSet:
    for item in FIGURE_SETS:
        if item.key == key:
            return item
    raise KeyError(f"unknown figure set {key!r}")


# --------------------------------------------------------------------------- #
# conversion
# --------------------------------------------------------------------------- #
def web_size(size: Tuple[int, int], max_px: Optional[int]) -> Tuple[int, int]:
    """Target pixel size after capping the longest side. Never upscales."""
    width, height = size
    longest = max(width, height)
    if not max_px or longest <= max_px:
        return width, height
    scale = max_px / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


def convert_png(
    src: str | Path,
    dest: str | Path,
    *,
    max_px: Optional[int] = WEB_MAX_PX,
    colors: int = PALETTE_COLORS,
) -> Path:
    """Re-encode one figure into the gallery at gallery size."""
    from PIL import Image

    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as handle:
        # The renders paint an opaque surface, so the alpha channel carries no
        # information; dropping it first keeps quantize() from spending palette
        # entries on it.
        image = handle.convert("RGB")
        target = web_size(image.size, max_px)
        if target != image.size:
            image = image.resize(target, Image.Resampling.LANCZOS)
        # dither=NONE: stippling a continuous colormap ramp to fake missing
        # colours is exactly the artefact these palettes exist to avoid.
        image.quantize(
            colors=colors,
            method=Image.Quantize.MAXCOVERAGE,
            dither=Image.Dither.NONE,
        ).save(dest, "PNG", optimize=True)
    return dest


@dataclass
class PlannedFigure:
    """One source figure and where it lands in the gallery."""

    figure_set: FigureSet
    source: Path
    dest: Path

    @property
    def max_px(self) -> Optional[int]:
        return None if self.figure_set.full_res else WEB_MAX_PX


def plan(
    source_root: str | Path = DEFAULT_SOURCE,
    dest_root: str | Path = DEFAULT_DEST,
    *,
    sets: Sequence[FigureSet] = FIGURE_SETS,
) -> List[PlannedFigure]:
    """Every conversion the gallery needs, in index order.

    Missing source directories are simply empty: a user who only ran the Tunisia
    pipeline should get a Tunisia gallery, not a crash.
    """
    dest_root = Path(dest_root)
    planned: List[PlannedFigure] = []
    for figure_set in sets:
        for src in figure_set.sources(source_root):
            planned.append(
                PlannedFigure(
                    figure_set=figure_set,
                    source=src,
                    dest=dest_root / figure_set.dest / src.name,
                )
            )
    return planned


@dataclass
class BuildResult:
    written: List[Path] = field(default_factory=list)
    skipped: List[Path] = field(default_factory=list)
    by_set: Dict[str, List[Path]] = field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        return sum(p.stat().st_size for paths in self.by_set.values() for p in paths)


def build(
    source_root: str | Path = DEFAULT_SOURCE,
    dest_root: str | Path = DEFAULT_DEST,
    *,
    overwrite: bool = False,
    max_px: Optional[int] = WEB_MAX_PX,
    sets: Sequence[FigureSet] = FIGURE_SETS,
    on_file: Optional[Callable[[PlannedFigure, bool], None]] = None,
) -> BuildResult:
    """Populate the gallery from the rendered outputs under ``source_root``."""
    result = BuildResult()
    for item in plan(source_root, dest_root, sets=sets):
        cap = None if item.figure_set.full_res else max_px
        fresh = overwrite or not item.dest.exists()
        if fresh:
            convert_png(item.source, item.dest, max_px=cap)
            result.written.append(item.dest)
        else:
            result.skipped.append(item.dest)
        result.by_set.setdefault(item.figure_set.key, []).append(item.dest)
        if on_file is not None:
            on_file(item, fresh)
    return result


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
INDEX_NAME = "README.md"

_PREAMBLE = """\
# Figures

Every figure this repository produces, in one place — {count} of them, {size}.

*This file is generated by `satimg figures build`; edit
[`src/satimg/figures.py`](../src/satimg/figures.py), not this page.*

The renderers write full-resolution output under `data/`, which is gitignored
(439 MB). The gallery is the same figures re-encoded to a 256-colour palette,
with the per-year series capped at {max_px} px on the longest side; the charts
and the small-multiple panels keep their native pixels. To regenerate at any
size:

```bash
pip install -e ".[dev]"
satimg lrcc-dvnl overlay                                # global sets
satimg lrcc-dvnl extract    --country TUN --levels 0,1,2
satimg lrcc-dvnl choropleth --country TUN --levels 1,2
satimg lrcc-dvnl inequality --country TUN
satimg figures build --max-px 0                         # 0 = keep full size
```

## Provenance and terms — read before reusing a figure

* **Imagery** — LRCC-DVNL, 1992–2022 at 1 km
  ([paper](https://doi.org/10.1038/s41597-025-05246-8) ·
  [data](https://doi.org/10.7910/DVN/15IKI5))
* **Boundaries** — GADM 4.1 ([gadm.org](https://gadm.org))
* **Projection** — WGS 84 / Equal Earth Greenwich (EPSG:8857)

⚠️ **These figures are not covered by the repository's MIT licence.** They
depict GADM 4.1 boundaries, and GADM's terms are *academic and other
non-commercial use; redistribution or commercial use not allowed without prior
permission*. Reproducing a figure in academic work with the attribution above is
what GADM permits; commercial use is not. The MIT licence applies to the code
only. See [`NOTICE.md`](NOTICE.md) and
[`../docs/overlays.md`](../docs/overlays.md).

No GADM data is committed here: the vector layers, the boundary-mask GeoTIFF
bands and the GID-keyed zonal tables all stay under gitignored `data/`. What is
committed is rendered raster imagery, at a resolution from which the source
geometry cannot be recovered.

Every figure also carries its own provenance and attribution in its footer, so
a figure lifted out of this folder stays self-describing.

## What to look at first
"""

_CAVEAT = """\
## Two caveats these figures cannot show you

1. **A lit pixel never dims here — it goes out.** Every decrease in this series
   is a lit → unlit transition; no pixel steps from DN 40 to DN 20. So gradual
   dimming is invisible and brightening between two frames is partly imposed,
   but catastrophic loss is real signal: Syria's national sum of lights falls
   54% between 2010 and 2016.
2. **2014 is a sensor handover** (DMSP → VIIRS), and the storage dtype changes
   with it. Treat any 2013 → 2014 step as a candidate artefact. The charts mark
   the break with a dashed line.

Full method, results and the remaining caveats:
[`../docs/tunisia.md`](../docs/tunisia.md) and
[`../docs/lrcc-dvnl.md`](../docs/lrcc-dvnl.md).
"""


#: Figures that are not conversions of a rendered raster: they are drawn
#: straight from the committed tables in ``results/`` by their own command, and
#: so live in the gallery without passing through :func:`build`. Listed here so
#: the index still finds them instead of silently dropping a whole analysis.
CROSS_COUNTRY = (
    (
        "trends/pace_total_vs_intensive.png",
        "Pace of change, all 22 countries",
        (
            "How fast each country's nighttime-light Theil T is moving, and "
            "whether the fall is convergence among lit places or light simply "
            "reaching new ground. Built by `satimg trends`."
        ),
    ),
)


def _human_bytes(total: int) -> str:
    value = float(total)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _year_of(name: str) -> Optional[str]:
    for chunk in Path(name).stem.split("_"):
        if len(chunk) == 4 and chunk.isdigit():
            return chunk
    return None


def _links(paths: Iterable[Path], dest_root: Path) -> str:
    """One dense row of year links, so 31 frames cost one line, not 31."""
    cells = []
    for path in paths:
        rel = path.relative_to(dest_root).as_posix()
        cells.append(f"[{_year_of(path.name) or path.stem}]({rel})")
    return " · ".join(cells)


def write_index(
    result: BuildResult,
    dest_root: str | Path = DEFAULT_DEST,
    *,
    max_px: Optional[int] = WEB_MAX_PX,
    sets: Sequence[FigureSet] = FIGURE_SETS,
) -> Path:
    """Write the gallery index that the repository's first page links to."""
    dest_root = Path(dest_root)
    extra = [item for item in CROSS_COUNTRY if (dest_root / item[0]).exists()]
    total = sum(len(paths) for paths in result.by_set.values()) + len(extra)
    size = result.total_bytes + sum(
        (dest_root / rel).stat().st_size for rel, _, _ in extra
    )
    lines = [
        _PREAMBLE.format(
            count=total,
            size=_human_bytes(size),
            max_px=max_px or WEB_MAX_PX,
        )
    ]

    for rel, caption in HERO:
        if (dest_root / rel).exists():
            lines.append(f"{caption}\n")
            lines.append(f"[![{Path(rel).stem}]({rel})]({rel})\n")

    for group in GROUP_ORDER:
        members = [s for s in sets if s.group == group and result.by_set.get(s.key)]
        if not members:
            continue
        lines.append(f"## {group}\n")
        for figure_set in members:
            paths = result.by_set[figure_set.key]
            lines.append(f"### {figure_set.title}\n")
            if figure_set.caption:
                lines.append(f"{figure_set.caption}\n")
            lines.append(f"`{figure_set.dest}/` — {len(paths)} file(s)\n")
            lines.append(f"{_links(paths, dest_root)}\n")

    if extra:
        lines.append("## Cross-country analysis\n")
        for rel, title, caption in extra:
            lines.append(f"### {title}\n")
            lines.append(f"{caption}\n")
            lines.append(f"[![{Path(rel).stem}]({rel})]({rel})\n")

    lines.append(_CAVEAT)
    out = dest_root / INDEX_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
