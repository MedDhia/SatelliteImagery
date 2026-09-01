"""Superpose administrative boundaries on the nighttime-light rasters.

Two products per admin level, from the same prepared boundary layer:

* ``render_png`` - a viewable map: the NTL grid as a dark-surface basemap with
  boundary lines drawn over it, a sequential colorbar, and the disclosures a
  reader needs to interpret it (stretch, downsampling, projection, extent).
* ``write_boundary_geotiff`` - a georeferenced 2-band GeoTIFF: band 1 is the
  untouched NTL DN, band 2 a rasterized boundary mask. Non-destructive, so the
  original values stay analysable.

Colour follows the sequential rule: magnitude gets **one hue**, stepped
light-to-dark, with the anchor flipped for a dark surface (DN 0 sits at the
surface colour, DN 63 at the lightest step). Boundary lines are deliberately
recessive neutral ink - they are reference geometry, not an encoded variable.

The rasters span 75N to 65S rather than pole to pole, so boundaries are clipped
to the raster's own extent; Antarctica and the high Arctic fall outside the data.

Requires the ``overlay`` extra::

    pip install -e ".[overlay]"
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Sequence, Tuple

from .boundaries import LEVEL_LABELS, BoundaryLayer, load_lines
from .datasets.lrcc_dvnl import (
    CITATION,
    CRS_EPSG,
    DN_MAX,
    DN_MIN,
    GRID_WIDTH,
    NODATA,
)
from .raster import _require_numpy, _require_rasterio

#: Single-hue (amber) sequential ramp, dark surface anchor -> lightest step.
NTL_RAMP: Tuple[str, ...] = (
    "#0b0b0e",
    "#3b1d02",
    "#7c3f04",
    "#b8730a",
    "#e8a01a",
    "#f7c948",
    "#fdeaa8",
)

#: Rendered colour for nodata (DN 127), kept distinct from a true dark DN 0.
NODATA_COLOR = "#17171d"

#: Recessive neutral ink for reference geometry.
BOUNDARY_COLOR = "#c3c9d2"

FIGURE_BACKGROUND = "#000000"
TEXT_PRIMARY = "#e8e8ea"
TEXT_MUTED = "#8b8f98"

DEFAULT_WIDTH_PX = 4000


@dataclass(frozen=True)
class OverlayStyle:
    """Presentation parameters for a PNG render."""

    width_px: int = DEFAULT_WIDTH_PX
    #: Gamma for the display stretch. <1 lifts dim lights into view. Disclosed
    #: in the colorbar label, because it changes what the reader perceives.
    gamma: float = 0.45
    #: Downsampling rule. "max" keeps small bright settlements visible; "average"
    #: is radiometrically fairer but erases cities at global zoom.
    resampling: str = "max"
    line_width_adm0: float = 0.45
    line_width_adm1: float = 0.22
    line_alpha_adm0: float = 0.75
    line_alpha_adm1: float = 0.55
    cmap: Optional[str] = None  # None -> the single-hue NTL_RAMP
    dpi: int = 200
    show_colorbar: bool = True
    title: Optional[str] = None

    def line_width(self, level: int) -> float:
        return self.line_width_adm0 if level == 0 else self.line_width_adm1

    def line_alpha(self, level: int) -> float:
        return self.line_alpha_adm0 if level == 0 else self.line_alpha_adm1


def _colormap(style: OverlayStyle):
    from matplotlib.colors import LinearSegmentedColormap

    if style.cmap:
        import matplotlib

        return matplotlib.colormaps[style.cmap]
    return LinearSegmentedColormap.from_list("ntl_amber", list(NTL_RAMP))


RESAMPLINGS = ("max", "average", "nearest")

#: Rows read per pass while downsampling (multiplied up to a block boundary).
_STRIP_BLOCKS = 64


def read_downsampled(
    path: str | Path,
    width_px: int,
    resampling: str = "max",
    *,
    strip_blocks: int = _STRIP_BLOCKS,
):
    """Read a raster downsampled to about ``width_px`` wide, streaming in strips.

    GDAL's decimated reads cannot do ``max``, and the alternatives are wrong for
    this data: ``average`` dissolves cities into a nearly-black field at global
    zoom, and ``mode``/``nearest`` throw away isolated lit pixels entirely. So
    the block reduction is done here, over an integer decimation factor.

    Nodata is excluded from the reduction rather than participating in it - a
    plain block max would let a single nodata pixel (DN 127) swallow a whole
    block and visibly inflate the nodata region along coasts and grid edges.

    Returns ``(masked_array, extent)`` ready for ``imshow``.
    """
    rasterio = _require_rasterio()
    np = _require_numpy()

    if resampling not in RESAMPLINGS:
        raise ValueError(
            f"unsupported resampling {resampling!r}; choose one of {RESAMPLINGS}"
        )

    with rasterio.open(path) as src:
        target = max(1, min(int(width_px), src.width))
        factor = max(1, -(-src.width // target))  # ceil division
        out_w = -(-src.width // factor)
        out_h = -(-src.height // factor)
        fill = NODATA if src.nodata is None else int(src.nodata)

        total = np.zeros((out_h, out_w), dtype=np.float64)
        counts = np.zeros((out_h, out_w), dtype=np.int64)
        # float32 throughout: the 2014-2022 rasters carry fractional DN, and
        # every integer year's values are exactly representable anyway.
        peak = np.full((out_h, out_w), -1.0, dtype=np.float32)

        pad_cols = out_w * factor - src.width
        strip_rows = max(factor, factor * strip_blocks)

        for row_start in range(0, src.height, strip_rows):
            rows = min(strip_rows, src.height - row_start)
            block = src.read(
                1, window=rasterio.windows.Window(0, row_start, src.width, rows)
            ).astype(np.float32)

            pad_rows = -(-rows // factor) * factor - rows
            if pad_rows or pad_cols:
                block = np.pad(
                    block,
                    ((0, pad_rows), (0, pad_cols)),
                    mode="constant",
                    constant_values=fill,
                )

            valid = block != fill
            # -1 is below every valid DN, so invalid cells never win a max.
            reduced = np.where(valid, block, -1)
            grid_h = block.shape[0] // factor
            shaped = reduced.reshape(grid_h, factor, out_w, factor)
            valid_shaped = valid.reshape(grid_h, factor, out_w, factor)

            out_slice = slice(row_start // factor, row_start // factor + grid_h)
            if resampling == "max":
                np.maximum(
                    peak[out_slice],
                    shaped.max(axis=(1, 3)),
                    out=peak[out_slice],
                )
            elif resampling == "nearest":
                peak[out_slice] = np.where(
                    valid_shaped[:, 0, :, 0], shaped[:, 0, :, 0], -1
                )
            else:  # average over valid cells only
                total[out_slice] += (
                    np.where(valid_shaped, shaped, 0)
                    .sum(axis=(1, 3))
                    .astype(np.float64)
                )
                counts[out_slice] += valid_shaped.sum(axis=(1, 3)).astype(np.int64)

        bounds = src.bounds

    if resampling == "average":
        with np.errstate(invalid="ignore"):
            data = np.where(counts > 0, total / np.maximum(counts, 1), np.nan)
        result = np.ma.masked_invalid(data)
    else:
        result = np.ma.masked_less(peak, 0)

    extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)
    return result, extent


def line_segments(layer: BoundaryLayer, lines: Optional[Sequence] = None):
    """Flatten a boundary layer into coordinate arrays for a LineCollection.

    GADM ADM_0 alone explodes into ~124k rings. Drawing those as individual
    ``plot`` calls dominates render time, and the geometry does not change
    between years, so build the segments once and reuse them across the series.
    """
    np = _require_numpy()

    geometries = load_lines(layer) if lines is None else lines
    segments = []
    for geometry in geometries:
        if geometry is None or geometry.is_empty:
            continue
        parts = geometry.geoms if geometry.geom_type.startswith("Multi") else [geometry]
        for part in parts:
            coords = np.asarray(part.coords)
            if len(coords) > 1:
                segments.append(coords)
    return segments


def render_png(
    raster_path: Optional[str | Path],
    out_path: str | Path,
    *,
    layer: Optional[BoundaryLayer] = None,
    year: Optional[int] = None,
    style: Optional[OverlayStyle] = None,
    segments: Optional[Sequence] = None,
    data=None,
    extent: Optional[Tuple[float, float, float, float]] = None,
) -> Path:
    """Render one NTL raster as a PNG, with boundary lines if a layer is given.

    Pass a precomputed ``data``/``extent`` pair to reuse one downsample across
    several renders of the same year - the raster read is the expensive part.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import PowerNorm

    style = style or OverlayStyle()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if data is None or extent is None:
        if raster_path is None:
            raise ValueError("either raster_path or data+extent must be given")
        data, extent = read_downsampled(raster_path, style.width_px, style.resampling)
    height_px, width_px = data.shape

    cmap = _colormap(style).with_extremes(bad=NODATA_COLOR)

    fig_width = width_px / style.dpi
    fig_height = height_px / style.dpi
    # Bands above and below the map, so nothing is written over the data.
    header = 0.42
    footer = 1.30 if style.show_colorbar else 0.80
    total_height = fig_height + header + footer
    fig = plt.figure(
        figsize=(fig_width, total_height),
        dpi=style.dpi,
        facecolor=FIGURE_BACKGROUND,
    )
    map_fraction = fig_height / total_height
    ax = fig.add_axes((0.0, footer / total_height, 1.0, map_fraction))
    ax.set_facecolor(FIGURE_BACKGROUND)

    image = ax.imshow(
        data,
        extent=extent,
        origin="upper",
        cmap=cmap,
        norm=PowerNorm(gamma=style.gamma, vmin=DN_MIN, vmax=DN_MAX),
        interpolation="nearest",
    )

    if layer is not None:
        if segments is None:
            segments = line_segments(layer)
        ax.add_collection(
            LineCollection(
                segments,
                colors=BOUNDARY_COLOR,
                linewidths=style.line_width(layer.level),
                alpha=style.line_alpha(layer.level),
                capstyle="round",
                antialiaseds=True,
            )
        )

    # Clip to the raster's own extent: the grid stops at 75N/65S, and the
    # boundary layer runs past it.
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_axis_off()

    _draw_chrome(fig, image, layer, year, style, total_height, header, data)

    fig.savefig(out_path, dpi=style.dpi, facecolor=FIGURE_BACKGROUND, pad_inches=0)
    plt.close(fig)
    return out_path


def _draw_chrome(fig, image, layer, year, style, total_height, header, data) -> None:
    """Title, colorbar and the disclosures needed to read the map honestly."""
    boundary_note = (
        f"{LEVEL_LABELS[layer.level]} boundaries" if layer is not None else "no overlay"
    )
    headline = style.title or (
        f"Nighttime lights {year}" if year is not None else "Nighttime lights"
    )
    # Title lives in its own band above the map, never over the data.
    fig.text(
        0.012,
        1.0 - header / total_height * 0.55,
        f"{headline}  ·  {boundary_note}",
        color=TEXT_PRIMARY,
        fontsize=14,
        fontweight="bold",
        va="center",
        ha="left",
    )

    scale_km = None
    if data is not None and data.shape[1]:
        # One rendered pixel covers this many km of ground at 1 km native.
        scale_km = round(GRID_WIDTH / data.shape[1])

    if style.show_colorbar:
        bar_bottom = 0.30 * header / total_height + 0.035
        bar_ax = fig.add_axes((0.012, bar_bottom, 0.26, 0.018))
        bar = fig.colorbar(image, cax=bar_ax, orientation="horizontal")
        bar.set_label(
            f"DN, relative (γ {style.gamma:g} display stretch)",
            color=TEXT_MUTED,
            fontsize=8,
        )
        bar.outline.set_edgecolor(TEXT_MUTED)
        bar.outline.set_linewidth(0.4)
        bar_ax.tick_params(colors=TEXT_MUTED, labelsize=7, width=0.4, length=2)

    notes = [
        "LRCC-DVNL 1992–2022 · Tang et al. 2025 · doi:10.7910/DVN/15IKI5",
        (
            "WGS 84 / Equal Earth Greenwich (EPSG:8857) · 1 km native "
            "· extent 75°N–65°S (poles not covered)"
        ),
    ]
    if scale_km:
        notes.append(
            f"displayed at ~{scale_km} km/px, {style.resampling} downsampling "
            "· DN 0–63, nodata rendered dark"
        )
    if layer is not None:
        notes.append(
            f"{layer.attribution} · {layer.feature_count} units, "
            f"simplified {layer.tolerance_m:g} m"
        )

    fig.text(
        0.33,
        0.055 + 0.30 * header / total_height,
        "\n".join(notes),
        color=TEXT_MUTED,
        fontsize=7,
        va="center",
        ha="left",
        linespacing=1.6,
    )


def rasterize_boundaries(
    raster_path: str | Path,
    layer: BoundaryLayer,
    *,
    lines: Optional[Sequence] = None,
    all_touched: bool = True,
):
    """Burn a boundary layer onto a raster's exact grid, returning a mask array."""
    rasterio = _require_rasterio()
    np = _require_numpy()
    from rasterio.features import rasterize

    geometries = load_lines(layer) if lines is None else lines
    shapes = [g for g in geometries if g is not None and not g.is_empty]

    with rasterio.open(raster_path) as src:
        out_shape = (src.height, src.width)
        transform = src.transform

    return rasterize(
        ((g, 1) for g in shapes),
        out_shape=out_shape,
        transform=transform,
        fill=0,
        all_touched=all_touched,
        dtype="uint8",
    ).astype(np.int8)


def grid_signature(raster_path: str | Path):
    """(width, height, transform) - what a rasterized mask is valid for."""
    rasterio = _require_rasterio()
    with rasterio.open(raster_path) as src:
        return (src.width, src.height, src.transform)


def write_boundary_geotiff(
    raster_path: str | Path,
    out_path: str | Path,
    layer: BoundaryLayer,
    *,
    lines: Optional[Sequence] = None,
    mask=None,
    window_height: int = 2048,
) -> Path:
    """Write a 2-band GeoTIFF: band 1 the NTL DN, band 2 a boundary mask.

    Non-destructive by construction - the NTL band is copied through unchanged,
    so every original DN survives and stays analysable.

    Every year of this dataset shares one grid, so a caller processing the whole
    series can rasterize once and pass the same ``mask`` in for each year. It is
    the caller's job to confirm the grid matches (see :func:`grid_signature`).
    """
    rasterio = _require_rasterio()
    from rasterio.crs import CRS
    from rasterio.windows import Window

    raster_path = Path(raster_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if mask is None:
        mask = rasterize_boundaries(raster_path, layer, lines=lines)

    with rasterio.open(raster_path) as src:
        # The series is NOT dtype-homogeneous: 1992 is int8, 1993-2013 int16 and
        # 2014-2022 float32 carrying fractional DN. Forcing a common dtype would
        # silently truncate the VIIRS-era years, so band 1 keeps whatever the
        # source used. The 0/1 mask is representable in all of them.
        source_dtype = src.dtypes[0]
        profile = src.profile.copy()
        profile.update(
            count=2,
            dtype=source_dtype,
            compress="lzw",
            tiled=True,
            blockxsize=256,
            blockysize=256,
            nodata=NODATA,
            # Predictor 2 (horizontal differencing) is for integers; floats want
            # 3, and using the wrong one costs compression or upsets readers.
            predictor=3 if source_dtype.startswith("float") else 2,
        )
        # The published rasters carry a broken LOCAL_CS; emit a real CRS so the
        # product is usable without a separate repair step.
        profile["crs"] = CRS.from_epsg(CRS_EPSG)

        with rasterio.open(out_path, "w", **profile) as dst:
            for row_start in range(0, src.height, window_height):
                rows = min(window_height, src.height - row_start)
                window = Window(0, row_start, src.width, rows)
                dst.write(src.read(1, window=window), 1, window=window)
                dst.write(
                    mask[row_start : row_start + rows, :].astype(source_dtype),
                    2,
                    window=window,
                )

            dst.set_band_description(
                1,
                f"LRCC-DVNL nighttime light DN (0-63, nodata 127, {source_dtype})",
            )
            dst.set_band_description(
                2, f"GADM adm{layer.level} {layer.label} boundary mask (1=boundary)"
            )
            dst.update_tags(
                dataset="LRCC-DVNL",
                citation=CITATION,
                boundaries=layer.attribution,
                boundary_level=f"adm{layer.level}",
                note=(
                    "Band 1 is the unmodified published DN grid. Band 2 is a "
                    "rasterized boundary mask; no NTL value was overwritten."
                ),
            )
    return out_path


def styles_for_level(level: int, base: Optional[OverlayStyle] = None) -> OverlayStyle:
    """Style tuned for an admin level (admin-1 needs finer, dimmer lines)."""
    base = base or OverlayStyle()
    if level == 0:
        return base
    return replace(base, line_width_adm0=base.line_width_adm1)
