"""Series assembly: the shape of the output and that scopes really exclude."""

from __future__ import annotations

import csv
import math

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
gpd = pytest.importorskip("geopandas")
from shapely.geometry import box  # noqa: E402

from satimg import analysis as A  # noqa: E402
from satimg import regions as R  # noqa: E402
from satimg import zonal as Z  # noqa: E402
from satimg.datasets.lrcc_dvnl import CRS_EPSG, NODATA  # noqa: E402

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


def test_write_csv_roundtrip(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = A.write_csv(rows, tmp_path / "nested" / "out.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        back = list(csv.DictReader(handle))
    assert [r["a"] for r in back] == ["1", "2"]


def test_write_csv_handles_no_rows(tmp_path):
    path = A.write_csv([], tmp_path / "empty.csv")
    assert path.read_text(encoding="utf-8") == ""


def test_excluded_zone_indices_are_one_based_to_match_the_zone_raster():
    """build_zone_grid burns unit i as id i+1; the exclusion must agree."""
    frame = gpd.GeoDataFrame(
        {"GID_1": ["TUN.1_1", "TUN.21_1", "TUN.10_1"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
        crs=f"EPSG:{CRS_EPSG}",
    )
    got = A._excluded_zone_indices(frame, 1, "TUN", "narrow")
    assert got == {2, 3}


def test_excluded_zone_indices_empty_for_all_scope():
    frame = gpd.GeoDataFrame(
        {"GID_1": ["TUN.21_1"]}, geometry=[box(0, 0, 1, 1)], crs=f"EPSG:{CRS_EPSG}"
    )
    assert A._excluded_zone_indices(frame, 1, "TUN", "all") == set()


def test_excluded_zone_indices_empty_at_national_level():
    frame = gpd.GeoDataFrame(
        {"GID_0": ["TUN"]}, geometry=[box(0, 0, 1, 1)], crs=f"EPSG:{CRS_EPSG}"
    )
    assert A._excluded_zone_indices(frame, 0, "TUN", "narrow") == set()


def test_gini_series_requires_rasters():
    with pytest.raises(ValueError, match="no rasters"):
        A.gini_series("TUN", [])


def test_gini_of_a_uniform_region_is_zero_and_lit_share_is_one(tmp_path, monkeypatch):
    """End-to-end shape check on a synthetic 'country' of two equal units."""
    array = np.full((4, 4), 5, dtype="int16")
    path = _raster(tmp_path / "u.tif", array)

    left = box(OX, OY - 4 * PIXEL, OX + 2 * PIXEL, OY)
    right = box(OX + 2 * PIXEL, OY - 4 * PIXEL, OX + 4 * PIXEL, OY)
    layers = {
        0: gpd.GeoDataFrame(
            {"GID_0": ["XXX"], "COUNTRY": ["Test"]},
            geometry=[box(OX, OY - 4 * PIXEL, OX + 4 * PIXEL, OY)],
            crs=f"EPSG:{CRS_EPSG}",
        ),
        1: gpd.GeoDataFrame(
            {"GID_1": ["X.1_1", "X.2_1"], "NAME_1": ["A", "B"]},
            geometry=[left, right],
            crs=f"EPSG:{CRS_EPSG}",
        ),
        2: gpd.GeoDataFrame(
            {
                "GID_1": ["X.1_1", "X.2_1"],
                "GID_2": ["X.1.1_1", "X.2.1_1"],
                "NAME_2": ["a", "b"],
            },
            geometry=[left, right],
            crs=f"EPSG:{CRS_EPSG}",
        ),
    }

    def fake_build_grids(iso3, ref, root=None, levels=R.COUNTRY_LEVELS):
        out = {}
        for level in levels:
            frame = layers[level]
            idf, namef = R.id_fields(level)
            out[level] = {
                "layer": None,
                "units": frame,
                "grid": Z.build_zone_grid(ref, frame, id_field=idf, name_field=namef),
            }
        return out

    monkeypatch.setattr(A, "build_grids", fake_build_grids)
    rows, tables = A.gini_series("XXX", [(2000, path)])

    # One scope ("all") for a country with no desert definitions:
    # pixel x 2 zero-treatments + adm1 + adm2 = 4 rows for one year.
    assert len(rows) == 4
    assert set(tables) == {1, 2}
    for row in rows:
        assert row["gini"] == pytest.approx(0.0), row
    pixel = [r for r in rows if r["level"] == "pixel"]
    assert all(r["lit_share"] == pytest.approx(1.0) for r in pixel)
    assert {r["zeros"] for r in pixel} == {A.ZEROS_INCLUDED, A.ZEROS_EXCLUDED}


def test_dark_region_yields_nan_not_zero(tmp_path, monkeypatch):
    array = np.zeros((4, 4), dtype="int16")
    path = _raster(tmp_path / "dark.tif", array)
    frame = gpd.GeoDataFrame(
        {"GID_1": ["X.1_1"], "NAME_1": ["A"]},
        geometry=[box(OX, OY - 4 * PIXEL, OX + 4 * PIXEL, OY)],
        crs=f"EPSG:{CRS_EPSG}",
    )

    def fake_build_grids(iso3, ref, root=None, levels=R.COUNTRY_LEVELS):
        return {
            1: {
                "layer": None,
                "units": frame,
                "grid": Z.build_zone_grid(
                    ref, frame, id_field="GID_1", name_field="NAME_1"
                ),
            }
        }

    monkeypatch.setattr(A, "build_grids", fake_build_grids)
    rows, _ = A.gini_series("XXX", [(2000, path)], levels=(1,))
    assert all(math.isnan(r["gini"]) for r in rows)
