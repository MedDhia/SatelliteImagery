"""Overlay tests on small synthetic rasters and geometries - no GADM needed."""

from __future__ import annotations

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
pytest.importorskip("matplotlib")
shapely = pytest.importorskip("shapely")

from shapely.geometry import LineString, Polygon  # noqa: E402

from satimg import overlay  # noqa: E402
from satimg.boundaries import BoundaryLayer  # noqa: E402
from satimg.datasets.lrcc_dvnl import CRS_EPSG, NODATA  # noqa: E402

PIXEL = 1000.0
ORIGIN_X, ORIGIN_Y = -10_000.0, 10_000.0


def _write_raster(path, array, nodata=NODATA, crs_epsg=CRS_EPSG):
    transform = rasterio.transform.from_origin(ORIGIN_X, ORIGIN_Y, PIXEL, PIXEL)
    profile = {
        "driver": "GTiff",
        "width": array.shape[1],
        "height": array.shape[0],
        "count": 1,
        "dtype": "int8",
        "nodata": nodata,
        "transform": transform,
        "crs": rasterio.crs.CRS.from_epsg(crs_epsg),
        "compress": "lzw",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return path


@pytest.fixture
def raster(tmp_path):
    """20x20 grid: a bright block, a dim block, and a nodata block."""
    array = np.zeros((20, 20), dtype=np.int8)
    array[0:4, 0:4] = 63
    array[4:8, 0:4] = 7
    array[16:20, :] = NODATA
    return _write_raster(tmp_path / "ntl.tif", array)


@pytest.fixture
def layer(tmp_path):
    """A boundary layer: one square polygon covering the grid's middle."""
    gpd = pytest.importorskip("geopandas")
    square = Polygon(
        [
            (ORIGIN_X + 4000, ORIGIN_Y - 4000),
            (ORIGIN_X + 14000, ORIGIN_Y - 4000),
            (ORIGIN_X + 14000, ORIGIN_Y - 14000),
            (ORIGIN_X + 4000, ORIGIN_Y - 14000),
        ]
    )
    frame = gpd.GeoDataFrame(
        {"GID_0": ["TST"], "COUNTRY": ["Testland"]},
        geometry=[square],
        crs=f"EPSG:{CRS_EPSG}",
    )
    path = tmp_path / "adm0.gpkg"
    frame.to_file(path, driver="GPKG", layer="adm0")
    return BoundaryLayer(
        level=0, path=path, epsg=CRS_EPSG, feature_count=1, tolerance_m=500
    )


# --------------------------------------------------------------------------- #
# downsampling
# --------------------------------------------------------------------------- #
def test_max_downsampling_preserves_isolated_bright_pixels(tmp_path):
    """A lone lit pixel must survive; this is why 'average' is not the default."""
    array = np.zeros((20, 20), dtype=np.int8)
    array[10, 10] = 63
    path = _write_raster(tmp_path / "sparse.tif", array)

    data, _ = overlay.read_downsampled(path, width_px=4, resampling="max")
    assert data.max() == 63

    averaged, _ = overlay.read_downsampled(path, width_px=4, resampling="average")
    # Same pixel, diluted across a 5x5 block - visually gone at global zoom.
    assert averaged.max() == pytest.approx(63 / 25)


def test_downsampling_does_not_let_nodata_swallow_a_block(tmp_path):
    """One nodata pixel in a block must not mark the whole block nodata."""
    array = np.zeros((10, 10), dtype=np.int8)
    array[:] = 5
    array[0, 0] = NODATA
    path = _write_raster(tmp_path / "mixed.tif", array)

    data, _ = overlay.read_downsampled(path, width_px=2, resampling="max")
    assert not data.mask.any(), "nodata leaked into a block that had valid pixels"
    assert data.max() == 5


def test_fully_nodata_block_is_masked(tmp_path):
    array = np.full((10, 10), NODATA, dtype=np.int8)
    array[:, 5:] = 3
    path = _write_raster(tmp_path / "half.tif", array)

    data, _ = overlay.read_downsampled(path, width_px=2, resampling="max")
    assert bool(data.mask[0, 0]) is True
    assert data[0, 1] == 3


def test_downsampled_extent_matches_raster_bounds(raster):
    data, extent = overlay.read_downsampled(raster, width_px=5)
    assert extent[0] == ORIGIN_X
    assert extent[3] == ORIGIN_Y
    assert data.shape[1] == 5


def test_average_ignores_nodata_in_the_denominator(tmp_path):
    array = np.zeros((4, 4), dtype=np.int8)
    array[0, 0] = 8
    array[0, 1] = NODATA
    array[1, 0] = 8
    array[1, 1] = 8
    path = _write_raster(tmp_path / "avg.tif", array)

    data, _ = overlay.read_downsampled(path, width_px=2, resampling="average")
    # 3 valid cells of 8 over 3 (not 4) cells.
    assert data[0, 0] == pytest.approx(8.0)


def test_unknown_resampling_rejected(raster):
    with pytest.raises(ValueError, match="unsupported resampling"):
        overlay.read_downsampled(raster, width_px=5, resampling="bicubic")


def test_downsampling_is_strip_size_independent(raster):
    a, _ = overlay.read_downsampled(raster, width_px=5, strip_blocks=1)
    b, _ = overlay.read_downsampled(raster, width_px=5, strip_blocks=99)
    assert np.array_equal(a.filled(-1), b.filled(-1))


# --------------------------------------------------------------------------- #
# rasterized mask / GeoTIFF
# --------------------------------------------------------------------------- #
def test_rasterize_produces_a_boundary_ring(raster, layer):
    mask = overlay.rasterize_boundaries(raster, layer)
    assert mask.shape == (20, 20)
    assert set(np.unique(mask)) <= {0, 1}
    assert mask.sum() > 0
    # The square's interior must be untouched: only its outline is drawn.
    assert mask[9, 9] == 0


def test_geotiff_is_non_destructive(raster, layer, tmp_path):
    out = overlay.write_boundary_geotiff(raster, tmp_path / "out.tif", layer)

    with rasterio.open(raster) as src, rasterio.open(out) as dst:
        assert dst.count == 2
        assert np.array_equal(src.read(1), dst.read(1))
        assert dst.transform == src.transform
        assert dst.width == src.width and dst.height == src.height
        assert dst.crs.to_epsg() == CRS_EPSG
        assert set(np.unique(dst.read(2))) <= {0, 1}
        assert "boundary mask" in dst.descriptions[1]


def test_geotiff_emits_a_real_crs_even_from_a_broken_source(tmp_path, layer):
    """Source rasters ship a LOCAL_CS; the overlay product must not inherit it."""
    local_cs = (
        'LOCAL_CS["WGS 84 / Equal Earth Greenwich",'
        'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
        'AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","8857"]]'
    )
    array = np.zeros((20, 20), dtype=np.int8)
    transform = rasterio.transform.from_origin(ORIGIN_X, ORIGIN_Y, PIXEL, PIXEL)
    broken = tmp_path / "broken.tif"
    with rasterio.open(
        broken,
        "w",
        driver="GTiff",
        width=20,
        height=20,
        count=1,
        dtype="int8",
        nodata=NODATA,
        transform=transform,
        crs=rasterio.crs.CRS.from_wkt(local_cs),
    ) as dst:
        dst.write(array, 1)

    assert rasterio.open(broken).crs.to_epsg() is None

    out = overlay.write_boundary_geotiff(broken, tmp_path / "fixed.tif", layer)
    with rasterio.open(out) as dst:
        assert dst.crs.to_epsg() == CRS_EPSG


@pytest.mark.parametrize("dtype", ["int8", "int16", "float32"])
def test_geotiff_preserves_each_dtype_in_the_series(dtype, layer, tmp_path):
    """1992 is int8, 1993-2013 int16, 2014-2022 float32 with fractional DN.

    Forcing one common dtype silently truncated the VIIRS-era years, so band 1
    must come back bit-identical whatever the source used.
    """
    array = np.zeros((20, 20), dtype=dtype)
    array[0, 0] = 63
    if dtype == "float32":
        array[1, 1] = np.float32(1.0526316)
        array[2, 2] = np.float32(62.964287)
    else:
        array[1, 1] = 7

    transform = rasterio.transform.from_origin(ORIGIN_X, ORIGIN_Y, PIXEL, PIXEL)
    source = tmp_path / f"{dtype}.tif"
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        width=20,
        height=20,
        count=1,
        dtype=dtype,
        nodata=NODATA,
        transform=transform,
        crs=rasterio.crs.CRS.from_epsg(CRS_EPSG),
    ) as dst:
        dst.write(array, 1)

    out = overlay.write_boundary_geotiff(source, tmp_path / f"{dtype}_out.tif", layer)

    with rasterio.open(out) as dst:
        assert dst.dtypes[0] == dtype
        assert np.array_equal(dst.read(1), array), "band 1 was not preserved exactly"
        assert set(np.unique(dst.read(2)).tolist()) <= {0, 1}


def test_downsampling_keeps_fractional_dn(tmp_path):
    """A float32 year must not be truncated to integers on the way to a PNG."""
    array = np.zeros((4, 4), dtype="float32")
    array[0, 0] = np.float32(1.0526316)
    transform = rasterio.transform.from_origin(ORIGIN_X, ORIGIN_Y, PIXEL, PIXEL)
    path = tmp_path / "frac.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        nodata=NODATA,
        transform=transform,
        crs=rasterio.crs.CRS.from_epsg(CRS_EPSG),
    ) as dst:
        dst.write(array, 1)

    data, _ = overlay.read_downsampled(path, width_px=2, resampling="max")
    assert data[0, 0] == pytest.approx(1.0526316, rel=1e-6)


def test_supplied_mask_is_used_verbatim(raster, layer, tmp_path):
    """The batch path reuses one mask across years; it must be honoured."""
    custom = np.zeros((20, 20), dtype=np.int8)
    custom[3, 3] = 1

    out = overlay.write_boundary_geotiff(
        raster, tmp_path / "custom.tif", layer, mask=custom
    )
    with rasterio.open(out) as dst:
        written = dst.read(2)
    assert written[3, 3] == 1
    assert written.sum() == 1


def test_grid_signature_matches_for_identical_grids(raster, tmp_path):
    twin = _write_raster(tmp_path / "twin.tif", np.ones((20, 20), dtype=np.int8))
    assert overlay.grid_signature(raster) == overlay.grid_signature(twin)


def test_grid_signature_differs_for_a_different_grid(raster, tmp_path):
    other = _write_raster(tmp_path / "other.tif", np.ones((10, 10), dtype=np.int8))
    assert overlay.grid_signature(raster) != overlay.grid_signature(other)


# --------------------------------------------------------------------------- #
# PNG rendering
# --------------------------------------------------------------------------- #
def test_render_png_writes_an_image(raster, layer, tmp_path):
    out = overlay.render_png(
        raster,
        tmp_path / "map.png",
        layer=layer,
        year=1992,
        style=overlay.OverlayStyle(width_px=200, dpi=50),
    )
    assert out.exists()
    assert out.stat().st_size > 0
    with open(out, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


def test_render_png_without_a_layer(raster, tmp_path):
    out = overlay.render_png(
        raster, tmp_path / "plain.png", style=overlay.OverlayStyle(width_px=120, dpi=50)
    )
    assert out.exists()


def test_render_png_requires_a_source(tmp_path):
    with pytest.raises(ValueError, match="raster_path or data"):
        overlay.render_png(None, tmp_path / "x.png")


def test_render_png_accepts_precomputed_data(raster, layer, tmp_path):
    data, extent = overlay.read_downsampled(raster, 120)
    out = overlay.render_png(
        None,
        tmp_path / "reused.png",
        layer=layer,
        data=data,
        extent=extent,
        style=overlay.OverlayStyle(width_px=120, dpi=50),
    )
    assert out.exists()


def test_line_segments_flattens_multipart_geometries(layer):
    segments = overlay.line_segments(layer)
    assert segments
    assert all(seg.shape[1] == 2 for seg in segments)
    assert all(len(seg) > 1 for seg in segments)


def test_line_segments_accepts_explicit_lines(layer):
    lines = [LineString([(0, 0), (1000, 1000)]), None]
    segments = overlay.line_segments(layer, lines=lines)
    assert len(segments) == 1


def test_style_line_width_varies_by_level():
    style = overlay.OverlayStyle()
    assert style.line_width(0) > style.line_width(1)
    assert style.line_alpha(0) > style.line_alpha(1)
