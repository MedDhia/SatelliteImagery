"""Zonal aggregation tests on hand-built rasters and geometries."""

from __future__ import annotations

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
gpd = pytest.importorskip("geopandas")
from shapely.geometry import box  # noqa: E402

from satimg import zonal as Z  # noqa: E402
from satimg.datasets.lrcc_dvnl import CRS_EPSG, NODATA  # noqa: E402

PIXEL = 1000.0
OX, OY = 0.0, 10_000.0


def _raster(path, array, nodata=NODATA):
    transform = rasterio.transform.from_origin(OX, OY, PIXEL, PIXEL)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype.name,
        nodata=nodata,
        transform=transform,
        crs=rasterio.crs.CRS.from_epsg(CRS_EPSG),
    ) as dst:
        dst.write(array, 1)
    return path


@pytest.fixture
def two_zones(tmp_path):
    """10x10 grid; left half zone A, right half zone B."""
    array = np.zeros((10, 10), dtype="int16")
    array[:, :5] = 2  # zone A: 50 px x 2 = 100
    array[:, 5:] = 4  # zone B: 50 px x 4 = 200
    path = _raster(tmp_path / "r.tif", array)
    frame = gpd.GeoDataFrame(
        {"GID_1": ["A", "B"], "NAME_1": ["Alpha", "Beta"]},
        geometry=[
            box(OX, OY - 10 * PIXEL, OX + 5 * PIXEL, OY),
            box(OX + 5 * PIXEL, OY - 10 * PIXEL, OX + 10 * PIXEL, OY),
        ],
        crs=f"EPSG:{CRS_EPSG}",
    )
    return path, frame


def test_zone_grid_partitions_every_pixel(two_zones):
    path, frame = two_zones
    grid = Z.build_zone_grid(path, frame, id_field="GID_1", name_field="NAME_1")
    counts = grid.pixels_per_zone()
    assert list(counts) == [50, 50]
    assert grid.count == 2
    assert grid.gids == ["A", "B"]
    assert grid.names == ["Alpha", "Beta"]


def test_zonal_sums_are_exact(two_zones):
    path, frame = two_zones
    grid = Z.build_zone_grid(path, frame, id_field="GID_1")
    values, _ = Z.read_window(path, grid.window)
    sums, counts = Z.zonal_sums(values, grid.ids, grid.count)
    assert list(sums) == [100.0, 200.0]
    assert list(counts) == [50, 50]


def test_nodata_is_excluded_from_sums_and_counts(tmp_path):
    array = np.full((4, 4), 3, dtype="int16")
    array[0, :] = NODATA
    path = _raster(tmp_path / "nd.tif", array)
    frame = gpd.GeoDataFrame(
        {"GID_1": ["A"]},
        geometry=[box(OX, OY - 4 * PIXEL, OX + 4 * PIXEL, OY)],
        crs=f"EPSG:{CRS_EPSG}",
    )
    grid = Z.build_zone_grid(path, frame, id_field="GID_1")
    values, _ = Z.read_window(path, grid.window)
    sums, counts = Z.zonal_sums(values, grid.ids, 1)
    assert counts[0] == 12  # the nodata row is dropped
    assert sums[0] == pytest.approx(36.0)


def test_zonal_table_reports_density_and_area(two_zones):
    path, frame = two_zones
    grid = Z.build_zone_grid(path, frame, id_field="GID_1", name_field="NAME_1")
    rows = Z.zonal_table([(1992, path)], grid)
    assert len(rows) == 2
    a = next(r for r in rows if r["gid"] == "A")
    assert a["pixels"] == 50
    assert a["sum_of_lights"] == pytest.approx(100.0)
    assert a["mean_dn"] == pytest.approx(2.0)
    assert a["area_km2"] == pytest.approx(50.0)
    assert a["density_sol_per_km2"] == pytest.approx(2.0)


def test_zonal_table_totals_equal_the_raster_total(two_zones):
    path, frame = two_zones
    grid = Z.build_zone_grid(path, frame, id_field="GID_1")
    rows = Z.zonal_table([(1992, path)], grid)
    with rasterio.open(path) as src:
        expected = float(src.read(1).sum())
    assert sum(r["sum_of_lights"] for r in rows) == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# grid tolerance
# --------------------------------------------------------------------------- #
def _sig(width, height, ox, oy):
    from affine import Affine

    return (width, height, Affine(1000.0, 0.0, ox, 0.0, -1000.0, oy))


def test_grids_compatible_ignores_sub_millimetre_origin_drift():
    """Real LRCC-DVNL years differ by ~4e-4 m; that must not force a rebuild."""
    a = _sig(34488, 15315, -17243957.96438, 7982831.544023)
    b = _sig(34488, 15315, -17243957.963989, 7982831.544198)
    assert Z.grids_compatible(a, b)


def test_grids_compatible_rejects_a_real_shift():
    a = _sig(10, 10, 0.0, 0.0)
    b = _sig(10, 10, 500.0, 0.0)  # half a pixel
    assert not Z.grids_compatible(a, b)


def test_grids_compatible_rejects_different_dimensions():
    assert not Z.grids_compatible(_sig(10, 10, 0, 0), _sig(11, 10, 0, 0))


def test_grids_compatible_rejects_different_pixel_size():
    from affine import Affine

    a = _sig(10, 10, 0, 0)
    b = (10, 10, Affine(500.0, 0.0, 0.0, 0.0, -500.0, 0.0))
    assert not Z.grids_compatible(a, b)


def test_grids_compatible_handles_none():
    assert not Z.grids_compatible(None, _sig(10, 10, 0, 0))


def test_zonal_table_rejects_a_mismatched_grid(two_zones, tmp_path):
    path, frame = two_zones
    grid = Z.build_zone_grid(path, frame, id_field="GID_1")
    other = _raster(tmp_path / "other.tif", np.zeros((6, 6), dtype="int16"))
    with pytest.raises(ValueError, match="different grid"):
        Z.zonal_table([(1992, other)], grid)


def test_window_for_clips_to_the_raster(two_zones):
    path, frame = two_zones
    window = Z.window_for(path, frame.total_bounds, pad=5)
    assert window.col_off >= 0 and window.row_off >= 0
    with rasterio.open(path) as src:
        assert window.col_off + window.width <= src.width
        assert window.row_off + window.height <= src.height
