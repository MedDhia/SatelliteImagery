"""Aridity tests: the class boundaries, true cell area, and the nodata traps.

Synthetic and offline - no 646 MB download, no GADM. Every case here guards a
failure mode that produces a plausible-looking wrong number rather than a crash.
"""

from __future__ import annotations

import math

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
from affine import Affine  # noqa: E402

from satimg import aridity as A  # noqa: E402

PIXEL = A.RESOLUTION_DEG


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw,expected",
    [
        (0, 1),  # AI 0 is a real hyper-arid value, not nodata
        (127, 1),  # the value that the old read_window fallback would have eaten
        (299, 1),
        (300, 2),  # boundaries are half-open [lower, upper)
        (1999, 2),
        (2000, 3),
        (4999, 3),
        (5000, 4),
        (6499, 4),
        (6500, 5),
        (64999, 5),
        (A.UNDEFINED, 0),
    ],
)
def test_classify_boundaries(raw, expected):
    assert int(A.classify(np.array([[raw]]))[0, 0]) == expected


def test_zero_is_hyper_arid_on_land_and_nodata_at_sea():
    # The whole ocean/desert ambiguity in one assertion: identical AI values,
    # opposite meanings, resolved only by the land mask.
    raw = np.array([[0, 0]])
    land = np.array([[True, False]])
    assert list(A.classify(raw, land_mask=land)[0]) == [1, A.NODATA_CODE]


def test_classes_tile_the_range_without_gap_or_overlap():
    edges = [(c.lower_raw, c.upper_raw) for c in A.CLASSES]
    assert edges[0][0] == 0 and edges[-1][1] is None
    for (_, upper), (lower, _) in zip(edges, edges[1:]):
        assert upper == lower


def test_class_codes_never_collide_with_nodata():
    assert A.NODATA_CODE not in {c.code for c in A.CLASSES}


# --------------------------------------------------------------------------- #
# true cell area
# --------------------------------------------------------------------------- #
def test_row_areas_integrate_to_the_whole_ellipsoid():
    transform = Affine(PIXEL, 0, -180.0, 0, -PIXEL, 90.0)
    total = A.row_areas_km2(transform, 21600).sum() * 43200
    assert abs(total - 510_065_600) / 510_065_600 < 1e-6


def test_cell_area_shrinks_poleward():
    def cell(lat):
        return A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, lat), 1)[0]

    assert cell(0) > cell(20) > cell(37) > cell(60)


def test_cell_area_is_symmetric_about_the_equator():
    # Comoros sits at 11.7 S. A cos() clamped to the northern hemisphere, or an
    # abs() in the wrong place, would silently mis-weight the only humid control.
    north = A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, 11.7 + PIXEL), 1)[0]
    south = A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, -11.7), 1)[0]
    assert math.isclose(north, south, rel_tol=1e-12)


def test_row_areas_are_all_positive():
    transform = Affine(PIXEL, 0, -180.0, 0, -PIXEL, 90.0)
    assert (A.row_areas_km2(transform, 21600) > 0).all()


# --------------------------------------------------------------------------- #
# shares
# --------------------------------------------------------------------------- #
def test_shares_sum_to_one_accepts_nan_for_an_empty_unit():
    row = {f"{c.key}_share": float("nan") for c in A.CLASSES}
    assert A.shares_sum_to_one(row)


def test_shares_sum_to_one_rejects_a_short_denominator():
    row = {f"{c.key}_share": 0.0 for c in A.CLASSES}
    row["arid_share"] = 0.9  # sums to 0.9, e.g. a dropped nodata class
    assert not A.shares_sum_to_one(row)


# --------------------------------------------------------------------------- #
# warping onto the analysis grid
# --------------------------------------------------------------------------- #
def _write(path, array, *, crs, transform, nodata=0, dtype=None):
    profile = dict(
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=dtype or array.dtype.name,
        crs=crs,
        transform=transform,
        nodata=nodata,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return path


def test_warp_matches_the_reference_grid_exactly(tmp_path):
    from satimg.raster import warp_to_grid
    from satimg.zonal import grids_compatible

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((6, 5), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(8857),
        transform=Affine(1000.0, 0, 0.0, 0, -1000.0, 10_000.0),
        nodata=127,
    )
    src = _write(
        tmp_path / "src.tif",
        np.full((40, 40), 2, dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got, rasterio.open(ref) as want:
        assert grids_compatible(
            (got.width, got.height, got.transform),
            (want.width, want.height, want.transform),
        )
        assert got.nodata == 0


def test_untouched_destination_cells_are_nodata_not_zero_class(tmp_path):
    """GDAL's default fill is 0. For a class raster 0 must mean 'no data',
    never a class - otherwise every ocean cell becomes real-looking output."""
    from satimg.raster import warp_to_grid

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((8, 8), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 50.0, 0, -PIXEL, 50.0),
        nodata=127,
    )
    # Source sits far away, so it covers none of the destination.
    src = _write(
        tmp_path / "src.tif",
        np.full((4, 4), 3, dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, -170.0, 0, -PIXEL, -40.0),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got:
        assert (got.read(1) == A.NODATA_CODE).all()


def test_warp_invents_no_class_absent_from_the_source(tmp_path):
    from satimg.raster import warp_to_grid

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((10, 10), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(8857),
        transform=Affine(1000.0, 0, 0.0, 0, -1000.0, 10_000.0),
        nodata=127,
    )
    values = np.random.default_rng(0).choice([1, 5], size=(60, 60)).astype("uint8")
    src = _write(
        tmp_path / "src.tif",
        values,
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got:
        present = set(np.unique(got.read(1)).tolist())
    assert present <= {A.NODATA_CODE, 1, 5}


# --------------------------------------------------------------------------- #
# the read_window trap this work closed
# --------------------------------------------------------------------------- #
def test_read_window_refuses_to_guess_a_missing_nodata(tmp_path):
    from satimg.zonal import read_window

    path = _write(
        tmp_path / "no_nodata.tif",
        np.full((4, 4), 127, dtype="uint16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
        nodata=None,
    )
    with pytest.raises(ValueError, match="declares no nodata"):
        read_window(path, rasterio.windows.Window(0, 0, 4, 4))


def test_read_window_keeps_127_when_told_there_is_no_fill(tmp_path):
    from satimg.zonal import read_window

    path = _write(
        tmp_path / "ai.tif",
        np.full((4, 4), 127, dtype="uint16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
        nodata=None,
    )
    data, _ = read_window(path, rasterio.windows.Window(0, 0, 4, 4), nodata=None)
    assert not np.isnan(data).any()
    assert (data == 127).all()


def test_build_zone_grid_refuses_a_geographic_crs(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from satimg.zonal import build_zone_grid

    path = _write(
        tmp_path / "r.tif",
        np.ones((4, 4), dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    frame = gpd.GeoDataFrame(
        {"GID_1": ["A"]}, geometry=[box(0, 0, 0.02, 0.02)], crs="EPSG:4326"
    )
    with pytest.raises(ValueError, match="projected CRS"):
        build_zone_grid(path, frame, id_field="GID_1")
