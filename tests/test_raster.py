"""Raster tests against small synthetic rasters that mimic the real files.

The fixtures reproduce the published quirk: Equal Earth georeferencing carried
in a LOCAL_CS WKT, so ``to_epsg()`` yields None until repaired.
"""

from __future__ import annotations

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")

from satimg import provenance, raster  # noqa: E402
from satimg.checksums import md5_file  # noqa: E402
from satimg.datasets.lrcc_dvnl import CRS_EPSG, NODATA  # noqa: E402

# The exact CRS string GDAL reports for the published rasters.
LOCAL_CS_WKT = (
    'LOCAL_CS["WGS 84 / Equal Earth Greenwich",'
    'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
    'AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","8857"]]'
)


def _write(path, array, crs_wkt, nodata=NODATA):
    transform = rasterio.transform.from_origin(-17_243_957.96, 7_982_831.54, 1000, 1000)
    profile = {
        "driver": "GTiff",
        "width": array.shape[1],
        "height": array.shape[0],
        "count": 1,
        "dtype": "int8",
        "nodata": nodata,
        "transform": transform,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 128,
        "blockysize": 128,
    }
    if crs_wkt is not None:
        profile["crs"] = rasterio.crs.CRS.from_wkt(crs_wkt)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return path


@pytest.fixture
def broken_raster(tmp_path):
    """256x256: DN 0-63 plus a block of nodata, with the LOCAL_CS defect."""
    array = np.zeros((256, 256), dtype=np.int8)
    array[:64, :64] = 63
    array[64:128, :64] = 10
    array[128:, :] = NODATA
    return _write(tmp_path / "broken.tif", array, LOCAL_CS_WKT)


@pytest.fixture
def good_raster(tmp_path):
    array = np.zeros((16, 16), dtype=np.int8)
    array[0, 0] = 5
    return _write(
        tmp_path / "good.tif", array, rasterio.crs.CRS.from_epsg(CRS_EPSG).to_wkt()
    )


def test_describe_flags_the_local_cs_defect(broken_raster):
    info = raster.describe(broken_raster)
    assert info.crs_status == raster.CRS_LOCAL_CS
    assert info.crs_epsg is None
    assert "fix-crs" in info.crs_note
    assert info.dtype == "int8"
    assert info.nodata == NODATA
    assert info.width == 256 and info.height == 256
    assert info.resolution == (1000.0, 1000.0)
    assert raster.needs_crs_repair(broken_raster) is True


def test_describe_accepts_a_correct_crs(good_raster):
    info = raster.describe(good_raster)
    assert info.crs_status == raster.CRS_OK
    assert info.crs_epsg == CRS_EPSG
    assert raster.needs_crs_repair(good_raster) is False


def test_missing_crs_is_reported(tmp_path):
    path = _write(tmp_path / "nocrs.tif", np.zeros((8, 8), dtype=np.int8), None)
    info = raster.describe(path)
    assert info.crs_status == raster.CRS_MISSING


def test_unexpected_crs_is_reported(tmp_path):
    path = _write(
        tmp_path / "wgs84.tif",
        np.zeros((8, 8), dtype=np.int8),
        rasterio.crs.CRS.from_epsg(4326).to_wkt(),
    )
    info = raster.describe(path)
    assert info.crs_status == raster.CRS_UNEXPECTED
    assert info.crs_epsg == 4326


def test_repair_crs_in_place_preserves_pixels_and_transform(broken_raster):
    with rasterio.open(broken_raster) as src:
        before = src.read(1)
        transform_before = src.transform

    raster.repair_crs(broken_raster)

    info = raster.describe(broken_raster)
    assert info.crs_status == raster.CRS_OK
    assert info.crs_epsg == CRS_EPSG
    with rasterio.open(broken_raster) as src:
        assert np.array_equal(src.read(1), before)
        assert src.transform == transform_before


def test_repair_crs_to_a_copy_leaves_the_original_broken(broken_raster, tmp_path):
    out = tmp_path / "fixed" / "out.tif"
    returned = raster.repair_crs(broken_raster, out=out)

    assert returned == out
    assert raster.describe(out).crs_status == raster.CRS_OK
    assert raster.describe(broken_raster).crs_status == raster.CRS_LOCAL_CS


def test_repair_crs_records_the_pre_repair_digest(broken_raster):
    """Repair changes the bytes, so verify needs the original digest kept."""
    before = md5_file(broken_raster)

    raster.repair_crs(broken_raster)

    assert md5_file(broken_raster) != before, "headers should have been rewritten"
    assert provenance.original_md5(broken_raster) == before
    record = provenance.read_record(broken_raster)
    assert record["operations"][-1]["operation"] == "fix-crs"
    assert record["operations"][-1]["details"]["epsg"] == CRS_EPSG


def test_repair_crs_can_skip_the_provenance_record(broken_raster):
    raster.repair_crs(broken_raster, record=False)
    assert provenance.read_record(broken_raster) is None


def test_repeated_repair_still_points_at_the_downloaded_digest(broken_raster):
    before = md5_file(broken_raster)
    raster.repair_crs(broken_raster)
    raster.repair_crs(broken_raster)
    assert provenance.original_md5(broken_raster) == before
    assert len(provenance.read_record(broken_raster)["operations"]) == 2


def test_summarize_counts_nodata_lit_and_sum_of_lights(broken_raster):
    stats = raster.summarize(broken_raster)

    assert stats.total_pixels == 256 * 256
    assert stats.nodata_pixels == 128 * 256
    assert stats.valid_pixels == 128 * 256
    assert stats.lit_pixels == 64 * 64 * 2
    assert stats.zero_pixels == 128 * 256 - 64 * 64 * 2
    assert stats.min_dn == 0
    assert stats.max_dn == 63
    assert stats.sum_of_lights == 64 * 64 * 63 + 64 * 64 * 10
    assert stats.out_of_range_pixels == 0
    assert stats.histogram[63] == 64 * 64
    assert stats.histogram[10] == 64 * 64
    assert stats.lit_fraction == pytest.approx((64 * 64 * 2) / (128 * 256))
    assert stats.mean_dn_lit == pytest.approx(stats.sum_of_lights / stats.lit_pixels)


def test_summarize_is_window_size_independent(broken_raster):
    a = raster.summarize(broken_raster, window_height=7)
    b = raster.summarize(broken_raster, window_height=1024)
    assert a.as_dict() == b.as_dict()


def test_summarize_handles_an_all_nodata_raster(tmp_path):
    array = np.full((32, 32), NODATA, dtype=np.int8)
    path = _write(tmp_path / "empty.tif", array, LOCAL_CS_WKT)
    stats = raster.summarize(path)
    assert stats.valid_pixels == 0
    assert stats.lit_pixels == 0
    assert stats.min_dn is None
    assert stats.mean_dn_valid is None
    assert stats.lit_fraction is None
