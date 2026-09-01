"""Command line interface for importing and inspecting satellite imagery datasets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .checksums import ChecksumMismatch, md5_file
from .datasets import lrcc_dvnl
from .download import download_file
from .provenance import original_md5

# Safe to import at module level: satimg.raster defers its rasterio/numpy
# imports until a raster command actually runs.
from .raster import RasterDependencyError
from .util import format_table, human_bytes, parse_year_spec

DEFAULT_DEST = Path("data/raw/lrcc-dvnl")
DEFAULT_OVERLAY_DEST = Path("data/overlays/lrcc-dvnl")
BOUNDARIES_ROOT = Path("data/boundaries")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _selected_files(args) -> List[lrcc_dvnl.DataFile]:
    manifest = lrcc_dvnl.load_manifest()
    product = getattr(args, "product", None)
    years: Optional[List[int]] = None
    if getattr(args, "years", None):
        valid = manifest.years(product) if product else None
        years = parse_year_spec(args.years, valid=valid or None)
    files = manifest.select(product=product, years=years)
    if not files:
        raise SystemExit("no files matched the given --product/--years selection")
    return files


class _Progress:
    """Single-line progress reporter for a terminal, silent when piped."""

    def __init__(self, label: str, enabled: bool) -> None:
        self.label = label
        self.enabled = enabled and sys.stderr.isatty()
        self._last = 0.0

    def __call__(self, done: int, total: Optional[int]) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        complete = total is not None and done >= total
        if now - self._last < 0.2 and not complete:
            return
        self._last = now
        if total:
            pct = 100.0 * done / total
            bar_width = 24
            filled = int(bar_width * done / total)
            bar = "#" * filled + "." * (bar_width - filled)
            text = (
                f"  {self.label}: [{bar}] {pct:5.1f}% "
                f"{human_bytes(done)}/{human_bytes(total)}"
            )
        else:
            text = f"  {self.label}: {human_bytes(done)}"
        sys.stderr.write("\r\033[K" + text)
        sys.stderr.flush()

    def done(self) -> None:
        if self.enabled:
            sys.stderr.write("\n")
            sys.stderr.flush()


# --------------------------------------------------------------------------- #
# lrcc-dvnl subcommands
# --------------------------------------------------------------------------- #
def cmd_list(args) -> int:
    manifest = lrcc_dvnl.load_manifest()

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "product": f.product,
                        "year": f.year,
                        "name": f.name,
                        "size_bytes": f.size_bytes,
                        "md5": f.md5,
                        "url": f.url,
                    }
                    for f in _selected_files(args)
                ],
                indent=2,
            )
        )
        return 0

    if not args.product and not args.years:
        print(f"{manifest.dataset.get('title')}")
        print(f"  DOI      {manifest.dataset.get('landing_page')}")
        print(
            f"  Version  {manifest.dataset.get('dataverse_version')} "
            f"released {manifest.dataset.get('release_time')}"
        )
        license_info = manifest.dataset.get("license") or {}
        print(f"  License  {license_info.get('name')} ({license_info.get('uri')})")
        print(
            f"  Total    {human_bytes(manifest.total_bytes)} across "
            f"{len(manifest.files)} files\n"
        )
        rows = []
        for pid, product in manifest.products.items():
            files = manifest.select(product=pid)
            years = manifest.years(pid)
            span = f"{years[0]}-{years[-1]}" if years else "n/a"
            rows.append(
                [
                    pid,
                    span,
                    str(len(files)),
                    human_bytes(sum(f.size_bytes for f in files)),
                    product.file_format,
                ]
            )
        print(format_table(rows, ["PRODUCT", "YEARS", "FILES", "SIZE", "FORMAT"]))
        print("\nRun 'satimg lrcc-dvnl list --product lrcc-dvnl' for per-file detail.")
        return 0

    rows = [
        [
            f.product,
            str(f.year) if f.year is not None else "-",
            f.name,
            human_bytes(f.size_bytes),
            f.md5,
        ]
        for f in _selected_files(args)
    ]
    print(format_table(rows, ["PRODUCT", "YEAR", "FILE", "SIZE", "MD5"]))
    return 0


def cmd_download(args) -> int:
    files = _selected_files(args)
    dest_root = Path(args.dest)
    total_bytes = sum(f.size_bytes for f in files)

    print(
        f"{len(files)} file(s), {human_bytes(total_bytes)} -> {dest_root}",
        file=sys.stderr,
    )
    if args.dry_run:
        for f in files:
            print(
                f"{f.url}  ->  {f.local_path(dest_root)}  ({human_bytes(f.size_bytes)})"
            )
        return 0

    failures: List[str] = []
    for index, data_file in enumerate(files, start=1):
        label = f"[{index}/{len(files)}] {data_file.name}"
        target = data_file.local_path(dest_root)
        progress = _Progress(label, enabled=not args.quiet)
        try:
            result = download_file(
                data_file.url,
                target,
                expected_md5=data_file.md5,
                expected_size=data_file.size_bytes,
                resume=not args.no_resume,
                retries=args.retries,
                progress=progress,
            )
            progress.done()
            print(f"{label}: {result.status} ({human_bytes(data_file.size_bytes)})")
        except ChecksumMismatch as exc:
            progress.done()
            failures.append(f"{data_file.name}: {exc}")
            print(f"{label}: CHECKSUM FAILED", file=sys.stderr)
        except (OSError, RuntimeError) as exc:
            progress.done()
            failures.append(f"{data_file.name}: {exc}")
            print(f"{label}: FAILED ({exc})", file=sys.stderr)
            if not args.keep_going:
                break

    if failures:
        print(f"\n{len(failures)} file(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\nAll files downloaded and verified.")
    return 0


def cmd_verify(args) -> int:
    files = _selected_files(args)
    dest_root = Path(args.dest)
    missing: List[str] = []
    corrupt: List[str] = []
    verified = 0
    repaired = 0

    for data_file in files:
        target = data_file.local_path(dest_root)
        if not target.exists():
            missing.append(data_file.name)
            continue

        size = target.stat().st_size
        if size == data_file.size_bytes and md5_file(target) == data_file.md5:
            verified += 1
            if not args.quiet:
                print(f"OK        {data_file.name}")
            continue

        # A local repair (e.g. fix-crs) changes the bytes on purpose. Fall back
        # to the digest recorded before that repair.
        if original_md5(target) == data_file.md5:
            repaired += 1
            if not args.quiet:
                print(f"REPAIRED  {data_file.name} (modified locally, provenance OK)")
            continue

        if size != data_file.size_bytes:
            corrupt.append(
                f"{data_file.name}: size {size} != expected {data_file.size_bytes}"
            )
        else:
            corrupt.append(
                f"{data_file.name}: md5 {md5_file(target)} != expected {data_file.md5}"
            )

    summary = f"\nverified {verified}/{len(files)}"
    if repaired:
        summary += f", locally repaired {repaired}"
    if missing:
        summary += f", missing {len(missing)}"
    if corrupt:
        summary += f", corrupt {len(corrupt)}"
    print(summary)

    for name in missing:
        print(f"MISSING   {name}", file=sys.stderr)
    for problem in corrupt:
        print(f"CORRUPT   {problem}", file=sys.stderr)
    return 1 if (missing or corrupt) else 0


def cmd_cite(args) -> int:
    if args.format == "bibtex":
        print(lrcc_dvnl.BIBTEX, end="")
    else:
        print("Paper:")
        print(f"  {lrcc_dvnl.CITATION}")
        print("\nDataset:")
        print(f"  {lrcc_dvnl.DATA_CITATION}")
    return 0


def cmd_overlay(args) -> int:
    """Produce boundary-overlaid sets: one per admin level, per output format."""
    from . import boundaries as B
    from .overlay import (
        OverlayStyle,
        grid_signature,
        line_segments,
        rasterize_boundaries,
        read_downsampled,
        render_png,
        write_boundary_geotiff,
    )

    levels = [B.check_level(int(v)) for v in str(args.admin).split(",") if v.strip()]
    formats = [f.strip() for f in str(args.format).split(",") if f.strip()]
    unknown = set(formats) - {"png", "tif"}
    if unknown:
        raise SystemExit(f"unknown --format value(s): {', '.join(sorted(unknown))}")

    files = _selected_files(args)
    source_root = Path(args.source)
    dest_root = Path(args.dest)

    available = []
    for data_file in files:
        candidate = source_root / data_file.name
        if not candidate.exists():
            candidate = data_file.local_path(source_root)
        if candidate.exists():
            available.append((data_file, candidate))
        else:
            print(
                f"skip {data_file.name}: not downloaded under {source_root}",
                file=sys.stderr,
            )
    if not available:
        raise SystemExit(
            f"no source rasters found under {source_root}; "
            "run 'satimg lrcc-dvnl download' first"
        )

    style = OverlayStyle(
        width_px=args.width,
        gamma=args.gamma,
        resampling=args.resampling,
        cmap=args.cmap,
        dpi=args.dpi,
    )

    # Prepare each level once; reproject + simplify is the slow part.
    prepared = {}
    for level in levels:
        layer = B.prepare_level(args.boundaries_root, level=level)
        prepared[level] = {
            "layer": layer,
            "segments": line_segments(layer) if "png" in formats else None,
            "mask": None,
            "grid": None,
        }
        print(
            f"boundaries adm{level}: {layer.feature_count} units "
            f"({layer.label}) from GADM {B.GADM_VERSION}",
            file=sys.stderr,
        )

    written = 0
    for data_file, raster in available:
        stem = Path(data_file.name).stem
        needs_png = "png" in formats
        decimated = None

        for level in levels:
            state = prepared[level]
            layer = state["layer"]

            if needs_png:
                png_out = dest_root / f"adm{level}" / "png" / f"{stem}_adm{level}.png"
                if png_out.exists() and not args.overwrite:
                    print(f"exists {png_out}")
                else:
                    if decimated is None:
                        decimated = read_downsampled(
                            raster, style.width_px, style.resampling
                        )
                    render_png(
                        None,
                        png_out,
                        layer=layer,
                        year=data_file.year,
                        style=style,
                        segments=state["segments"],
                        data=decimated[0],
                        extent=decimated[1],
                    )
                    written += 1
                    print(f"wrote  {png_out}")

            if "tif" in formats:
                tif_out = dest_root / f"adm{level}" / "tif" / f"{stem}_adm{level}.tif"
                if tif_out.exists() and not args.overwrite:
                    print(f"exists {tif_out}")
                    continue
                signature = grid_signature(raster)
                # Every year shares one grid, so the mask is rasterized once and
                # reused; recompute only if a raster turns up on a different grid.
                if state["mask"] is None or state["grid"] != signature:
                    state["mask"] = rasterize_boundaries(raster, layer)
                    state["grid"] = signature
                write_boundary_geotiff(raster, tif_out, layer, mask=state["mask"])
                written += 1
                print(f"wrote  {tif_out}")

    print(f"\n{written} file(s) written under {dest_root}")
    if any(prepared):
        print(
            "Boundaries are GADM 4.1: non-commercial use, redistribution not "
            "permitted. Overlay products inherit that restriction.",
            file=sys.stderr,
        )
    return 0


# --------------------------------------------------------------------------- #
# boundaries subcommands
# --------------------------------------------------------------------------- #
def cmd_boundaries_fetch(args) -> int:
    from . import boundaries as B

    print(B.GADM_LICENSE_NOTICE, file=sys.stderr)
    progress = _Progress("gadm", enabled=not args.quiet)
    target = B.fetch_gadm(args.root, keep_archive=args.keep_archive, progress=progress)
    progress.done()
    print(f"GADM ready: {target} ({human_bytes(target.stat().st_size)})")
    print(f"License notice: {B.license_path(args.root)}")
    return 0


def cmd_boundaries_prepare(args) -> int:
    from . import boundaries as B

    for value in str(args.level).split(","):
        level = B.check_level(int(value))
        layer = B.prepare_level(args.root, level=level, force=args.force)
        print(
            f"adm{level} ({layer.label}): {layer.feature_count} units, "
            f"EPSG:{layer.epsg}, simplified {layer.tolerance_m:g} m -> {layer.path}"
        )
    return 0


def cmd_boundaries_info(args) -> int:
    from . import boundaries as B

    source = B.gpkg_path(args.root)
    print(f"GADM {B.GADM_VERSION}")
    print(f"  source     {source} {'(present)' if source.exists() else '(MISSING)'}")
    print("  license    non-commercial; redistribution not permitted")
    rows = []
    for level, label in B.LEVEL_LABELS.items():
        cache = B.cache_path(args.root, level=level)
        rows.append(
            [
                f"adm{level}",
                label,
                B.LEVEL_LAYERS[level],
                "cached" if cache.exists() else "-",
            ]
        )
    print()
    print(format_table(rows, ["LEVEL", "LABEL", "LAYER", "PREPARED"]))
    return 0


# --------------------------------------------------------------------------- #
# raster subcommands
# --------------------------------------------------------------------------- #
def cmd_raster_info(args) -> int:
    from .raster import CRS_OK, describe

    exit_code = 0
    for path in args.paths:
        info = describe(path)
        if args.json:
            print(json.dumps(info.as_dict(), indent=2))
        else:
            print(f"{info.path}")
            print(
                f"  size        {info.width} x {info.height} ({info.band_count} band)"
            )
            print(f"  dtype       {info.dtype}  nodata {info.nodata}")
            print(f"  resolution  {info.resolution[0]:g} x {info.resolution[1]:g}")
            print(f"  bounds      {', '.join(f'{b:.1f}' for b in info.bounds)}")
            print(f"  compression {info.compression}  tiled {info.tiled}")
            print(f"  on disk     {human_bytes(info.size_bytes)}")
            print(f"  crs         {info.crs_status.upper()}: {info.crs_note}")
        if info.crs_status != CRS_OK:
            exit_code = 1 if args.strict else exit_code
    return exit_code


def cmd_raster_fix_crs(args) -> int:
    from .raster import CRS_OK, describe, repair_crs

    for path in args.paths:
        info = describe(path)
        if info.crs_status == CRS_OK and not args.force:
            print(f"SKIP  {path} (already EPSG:{info.crs_epsg})")
            continue
        if args.dry_run:
            print(f"WOULD FIX  {path} ({info.crs_status}: {info.crs_note})")
            continue
        target = repair_crs(path, out=args.out, epsg=args.epsg)
        fixed = describe(target)
        status = "OK" if fixed.crs_status == CRS_OK else "STILL BROKEN"
        print(f"{status}  {target} -> EPSG:{fixed.crs_epsg}")
        if fixed.crs_status != CRS_OK:
            return 1
    return 0


def cmd_raster_stats(args) -> int:
    from .raster import summarize

    for path in args.paths:
        stats = summarize(path, window_height=args.window_height)
        if args.json:
            print(json.dumps(stats.as_dict(), indent=2))
            continue
        print(f"{stats.path}")
        print(f"  total pixels     {stats.total_pixels:,}")
        print(f"  nodata pixels    {stats.nodata_pixels:,}")
        print(f"  valid pixels     {stats.valid_pixels:,}")
        lit_fraction = stats.lit_fraction
        lit_text = f"{lit_fraction:.4%}" if lit_fraction is not None else "n/a"
        print(f"  lit pixels DN>0  {stats.lit_pixels:,} ({lit_text} of valid)")
        print(f"  dtype            {stats.dtype}")
        if stats.min_dn is None:
            print("  DN range         n/a (no valid pixels)")
        elif stats.histogram_is_binned:
            print(f"  DN range         {stats.min_dn:.4g} - {stats.max_dn:.4g}")
        else:
            print(f"  DN range         {stats.min_dn} - {stats.max_dn}")
        print(f"  sum of lights    {stats.sum_of_lights:,.0f}")
        if stats.mean_dn_lit is not None:
            print(f"  mean DN (lit)    {stats.mean_dn_lit:.3f}")
        if stats.out_of_range_pixels:
            print(f"  OUT OF RANGE     {stats.out_of_range_pixels:,} pixels")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="satimg",
        description="Import and inspect global satellite imagery datasets.",
    )
    parser.add_argument("--version", action="version", version=f"satimg {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    dataset = commands.add_parser(
        "lrcc-dvnl",
        help="LRCC-DVNL global nighttime lights, 1992-2022",
        description=(
            "LRCC-DVNL global annual nighttime lights (1992-2022), "
            f"doi:{lrcc_dvnl.DOI}."
        ),
    )
    sub = dataset.add_subparsers(dest="subcommand", metavar="<subcommand>")

    def add_selection(target, default_product: Optional[str] = None) -> None:
        target.add_argument(
            "--product",
            default=default_product,
            help="product id to operate on (see 'satimg lrcc-dvnl list')",
        )
        target.add_argument(
            "--years",
            help="year selection, e.g. '1992-2000,2010' (default: all years)",
        )

    listing = sub.add_parser("list", help="show products and files in the manifest")
    add_selection(listing)
    listing.add_argument("--json", action="store_true", help="emit JSON")
    listing.set_defaults(func=cmd_list)

    download = sub.add_parser(
        "download", help="download files and verify them against the manifest"
    )
    add_selection(download, default_product=lrcc_dvnl.DATASET_ID)
    download.add_argument(
        "--dest", default=DEFAULT_DEST, help=f"download root (default: {DEFAULT_DEST})"
    )
    download.add_argument(
        "--no-resume", action="store_true", help="ignore any partial .part files"
    )
    download.add_argument(
        "--retries", type=int, default=4, help="network retries per file (default: 4)"
    )
    download.add_argument(
        "--keep-going",
        action="store_true",
        help="continue after a failed file instead of stopping",
    )
    download.add_argument("--dry-run", action="store_true", help="only print the plan")
    download.add_argument("--quiet", action="store_true", help="no progress bars")
    download.set_defaults(func=cmd_download)

    verify = sub.add_parser("verify", help="checksum local files against the manifest")
    add_selection(verify, default_product=lrcc_dvnl.DATASET_ID)
    verify.add_argument("--dest", default=DEFAULT_DEST, help="download root to check")
    verify.add_argument("--quiet", action="store_true", help="only report problems")
    verify.set_defaults(func=cmd_verify)

    cite = sub.add_parser("cite", help="print the citations for paper and dataset")
    cite.add_argument(
        "--format", choices=["text", "bibtex"], default="text", help="citation format"
    )
    cite.set_defaults(func=cmd_cite)

    overlay = sub.add_parser(
        "overlay",
        help="superpose administrative boundaries, producing one set per level",
        description=(
            "Produce boundary-overlaid sets from downloaded rasters: PNG map "
            "renders and/or 2-band GeoTIFFs whose second band is a boundary "
            "mask. Boundaries come from GADM (non-commercial use only)."
        ),
    )
    add_selection(overlay, default_product=lrcc_dvnl.DATASET_ID)
    overlay.add_argument(
        "--admin",
        default="0,1",
        help="admin level(s) to overlay: 0=country, 1=subnational (default: 0,1)",
    )
    overlay.add_argument(
        "--format",
        default="png,tif",
        help="output kinds: png, tif, or both (default: png,tif)",
    )
    overlay.add_argument(
        "--source",
        default=DEFAULT_DEST,
        help=f"where the downloaded rasters live (default: {DEFAULT_DEST})",
    )
    overlay.add_argument(
        "--dest", default=DEFAULT_OVERLAY_DEST, help="output root for the overlay sets"
    )
    overlay.add_argument(
        "--boundaries-root",
        default=BOUNDARIES_ROOT,
        help=f"where GADM data and caches live (default: {BOUNDARIES_ROOT})",
    )
    overlay.add_argument(
        "--width", type=int, default=4000, help="PNG width in pixels (default: 4000)"
    )
    overlay.add_argument(
        "--gamma",
        type=float,
        default=0.45,
        help="display stretch for the PNG colour ramp (default: 0.45)",
    )
    overlay.add_argument(
        "--resampling",
        choices=["max", "average", "nearest"],
        default="max",
        help="PNG downsampling rule (default: max, keeps small settlements)",
    )
    overlay.add_argument(
        "--cmap", help="matplotlib colormap name instead of the single-hue ramp"
    )
    overlay.add_argument("--dpi", type=int, default=200, help="PNG dpi (default: 200)")
    overlay.add_argument(
        "--overwrite", action="store_true", help="re-render outputs that already exist"
    )
    overlay.set_defaults(func=cmd_overlay)

    bounds = commands.add_parser(
        "boundaries",
        help="fetch and prepare administrative boundaries (GADM)",
        description=(
            "GADM administrative boundaries. GADM is free for academic and "
            "other non-commercial use; redistribution and commercial use "
            "require permission, so nothing is committed to this repository."
        ),
    )
    bounds_sub = bounds.add_subparsers(dest="subcommand", metavar="<subcommand>")

    fetch = bounds_sub.add_parser(
        "fetch", help="download and extract the GADM world GeoPackage (2.5 GiB)"
    )
    fetch.add_argument("--root", default=BOUNDARIES_ROOT, help="boundary data root")
    fetch.add_argument(
        "--keep-archive", action="store_true", help="keep the .zip after extracting"
    )
    fetch.add_argument("--quiet", action="store_true", help="no progress bar")
    fetch.set_defaults(func=cmd_boundaries_fetch)

    prepare = bounds_sub.add_parser(
        "prepare", help="reproject and simplify one or more admin levels"
    )
    prepare.add_argument(
        "--level", default="0,1", help="admin level(s), comma separated (default: 0,1)"
    )
    prepare.add_argument("--root", default=BOUNDARIES_ROOT, help="boundary data root")
    prepare.add_argument(
        "--force", action="store_true", help="rebuild even if a cache exists"
    )
    prepare.set_defaults(func=cmd_boundaries_prepare)

    binfo = bounds_sub.add_parser("info", help="show GADM status and prepared caches")
    binfo.add_argument("--root", default=BOUNDARIES_ROOT, help="boundary data root")
    binfo.set_defaults(func=cmd_boundaries_info)

    raster = commands.add_parser(
        "raster", help="inspect and repair downloaded rasters (needs the raster extra)"
    )
    raster_sub = raster.add_subparsers(dest="subcommand", metavar="<subcommand>")

    info = raster_sub.add_parser("info", help="print raster properties and CRS status")
    info.add_argument("paths", nargs="+", type=Path)
    info.add_argument("--json", action="store_true", help="emit JSON")
    info.add_argument(
        "--strict", action="store_true", help="exit non-zero if the CRS needs repair"
    )
    info.set_defaults(func=cmd_raster_info)

    fix = raster_sub.add_parser(
        "fix-crs",
        help="replace the broken LOCAL_CS declaration with a real EPSG CRS",
    )
    fix.add_argument("paths", nargs="+", type=Path)
    fix.add_argument(
        "--out",
        type=Path,
        help="write a fixed copy here instead of editing in place (single input)",
    )
    fix.add_argument(
        "--epsg", type=int, default=lrcc_dvnl.CRS_EPSG, help="EPSG code to assign"
    )
    fix.add_argument("--force", action="store_true", help="rewrite even if already OK")
    fix.add_argument(
        "--dry-run", action="store_true", help="only report what would change"
    )
    fix.set_defaults(func=cmd_raster_fix_crs)

    stats = raster_sub.add_parser("stats", help="summarize DN distribution of a raster")
    stats.add_argument("paths", nargs="+", type=Path)
    stats.add_argument("--json", action="store_true", help="emit JSON")
    stats.add_argument(
        "--window-height",
        type=int,
        default=512,
        help="rows read per pass (default: 512)",
    )
    stats.set_defaults(func=cmd_raster_stats)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        # Show the help of the deepest selected subparser.
        if args.command:
            parser.parse_args([args.command, "--help"])
        parser.print_help()
        return 1

    if getattr(args, "out", None) is not None and len(getattr(args, "paths", [])) > 1:
        parser.error("--out accepts a single input path")

    try:
        return args.func(args)
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:  # pragma: no cover - e.g. `satimg ... | head`
        # Point stdout at devnull so the interpreter does not report the
        # broken pipe again while flushing at exit.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except RasterDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
