"""Clipped country extracts: dtype preservation and masking."""

from __future__ import annotations

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
from rasterio.windows import Window  # noqa: E402
from shapely.geometry import box  # noqa: E402

from satimg.datasets.lrcc_dvnl import CRS_EPSG, NODATA  # noqa: E402
from satimg.raster import clip_raster  # noqa: E402

PIXEL = 1000.0
OX, OY = 0.0, 10_000.0


def _raster(path, array):
    transform = rasterio.transform.from_origin(OX, OY, PIXEL, PIXEL)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype.name,
        nodata=NODATA,
        transform=transform,
        crs=rasterio.crs.CRS.from_epsg(CRS_EPSG),
    ) as dst:
        dst.write(array, 1)
    return path


@pytest.mark.parametrize("dtype", ["int8", "int16", "float32"])
def test_clip_preserves_dtype_and_values(dtype, tmp_path):
    array = np.arange(100, dtype=dtype).reshape(10, 10) % 60
    src = _raster(tmp_path / f"{dtype}.tif", array)

    out = clip_raster(src, tmp_path / f"{dtype}_clip.tif", Window(2, 2, 5, 5))

    with rasterio.open(out) as dst:
        assert dst.dtypes[0] == dtype
        assert (dst.width, dst.height) == (5, 5)
        assert np.array_equal(dst.read(1), array[2:7, 2:7])
        assert dst.crs.to_epsg() == CRS_EPSG


def test_clip_masks_outside_the_geometry(tmp_path):
    """An 'extract' must be the country, not its bounding box."""
    array = np.full((10, 10), 7, dtype="int16")
    src = _raster(tmp_path / "r.tif", array)
    # Keep only the left half of the window.
    keep = box(OX, OY - 10 * PIXEL, OX + 5 * PIXEL, OY)

    out = clip_raster(
        src, tmp_path / "masked.tif", Window(0, 0, 10, 10), mask_geometries=[keep]
    )

    with rasterio.open(out) as dst:
        data = dst.read(1)
        assert (data[:, :5] == 7).all(), "inside the shape must be untouched"
        assert (data[:, 5:] == NODATA).all(), "outside must become nodata"
        assert dst.nodata == NODATA


def test_clip_without_a_mask_keeps_the_whole_window(tmp_path):
    array = np.full((6, 6), 3, dtype="int16")
    src = _raster(tmp_path / "r.tif", array)
    out = clip_raster(src, tmp_path / "full.tif", Window(0, 0, 6, 6))
    with rasterio.open(out) as dst:
        assert (dst.read(1) == 3).all()


def test_clip_transform_places_the_window_correctly(tmp_path):
    array = np.zeros((10, 10), dtype="int16")
    src = _raster(tmp_path / "r.tif", array)
    out = clip_raster(src, tmp_path / "w.tif", Window(3, 4, 2, 2))
    with rasterio.open(out) as dst:
        assert dst.transform.c == pytest.approx(OX + 3 * PIXEL)
        assert dst.transform.f == pytest.approx(OY - 4 * PIXEL)
