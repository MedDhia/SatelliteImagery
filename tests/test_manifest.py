"""The committed manifest is the dataset import; guard its shape and content."""

from __future__ import annotations

import json
import re

import pytest

from satimg.datasets import lrcc_dvnl


@pytest.fixture(scope="module")
def manifest():
    return lrcc_dvnl.load_manifest()


def test_manifest_file_is_committed():
    assert lrcc_dvnl.MANIFEST_PATH.exists()


def test_annual_series_covers_1992_to_2022(manifest):
    years = manifest.years(lrcc_dvnl.DATASET_ID)
    assert years == list(range(lrcc_dvnl.FIRST_YEAR, lrcc_dvnl.LAST_YEAR + 1))
    assert len(years) == 31


def test_products_present(manifest):
    assert set(manifest.products) == {"lrcc-dvnl", "c-dvnl", "crf"}


def test_every_file_has_a_usable_md5_and_size(manifest):
    for data_file in manifest.files:
        assert re.fullmatch(r"[0-9a-f]{32}", data_file.md5), data_file.name
        assert data_file.size_bytes > 0
        assert data_file.dataverse_file_id > 0


def test_file_ids_are_unique(manifest):
    ids = [f.dataverse_file_id for f in manifest.files]
    assert len(ids) == len(set(ids))


def test_annual_filenames_follow_the_lacc_pattern(manifest):
    # The published filenames say LACC_, not LRCC-DVNL_; keep that pinned so a
    # rename upstream shows up as a test failure rather than 404s at download.
    for data_file in manifest.select(product=lrcc_dvnl.DATASET_ID):
        assert data_file.name == f"LACC_{data_file.year}.tif"


def test_urls_point_at_dataverse_access_api(manifest):
    for data_file in manifest.files:
        assert data_file.url.startswith(
            "https://dataverse.harvard.edu/api/access/datafile/"
        )
        assert data_file.url.endswith(str(data_file.dataverse_file_id))


def test_dataset_level_provenance_is_recorded(manifest):
    dataset = manifest.dataset
    assert dataset["doi"] == lrcc_dvnl.DOI
    assert dataset["paper_doi"] == lrcc_dvnl.PAPER_DOI
    assert dataset["license"]["spdx_id"]
    assert dataset["grid"]["crs_epsg"] == lrcc_dvnl.CRS_EPSG
    assert dataset["grid"]["nodata"] == lrcc_dvnl.NODATA


def test_dtype_eras_cover_every_year_without_gaps():
    """The dtype switch is a real property of the deposit; pin it."""
    years = [lrcc_dvnl.dtype_for_year(y) for y in range(1992, 2023)]
    assert len(years) == 31
    assert lrcc_dvnl.dtype_for_year(1992) == "int8"
    assert lrcc_dvnl.dtype_for_year(1993) == "int16"
    assert lrcc_dvnl.dtype_for_year(2013) == "int16"
    # The switch to fractional DN lands on the DMSP -> VIIRS boundary.
    assert lrcc_dvnl.dtype_for_year(2014) == "float32"
    assert lrcc_dvnl.dtype_for_year(2022) == "float32"


def test_dtype_for_year_rejects_years_outside_the_series():
    with pytest.raises(ValueError):
        lrcc_dvnl.dtype_for_year(2023)


def test_manifest_records_the_dtype_eras(manifest):
    eras = manifest.dataset["grid"]["dtype_eras"]
    assert [e["dtype"] for e in eras] == ["int8", "int16", "float32"]


def test_select_filters_by_product_and_year(manifest):
    chosen = manifest.select(product=lrcc_dvnl.DATASET_ID, years=[1992, 2022])
    assert [f.year for f in chosen] == [1992, 2022]

    with pytest.raises(KeyError):
        manifest.select(product="not-a-product")


def test_annual_series_helper_matches_select():
    assert lrcc_dvnl.annual_series([2000])[0].year == 2000


def test_local_path_is_namespaced_by_product(tmp_path, manifest):
    data_file = manifest.select(product=lrcc_dvnl.DATASET_ID, years=[1992])[0]
    assert data_file.local_path(tmp_path) == tmp_path / "lrcc-dvnl" / "LACC_1992.tif"


def test_total_bytes_matches_sum_of_files(manifest):
    raw = json.loads(lrcc_dvnl.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest.total_bytes == sum(f["size_bytes"] for f in raw["files"])


def test_malformed_manifest_raises_manifest_error(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(lrcc_dvnl.ManifestError):
        lrcc_dvnl.load_manifest(str(broken))


def test_manifest_with_undeclared_product_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "products": {},
                "files": [
                    {
                        "product": "ghost",
                        "name": "x.tif",
                        "dataverse_file_id": 1,
                        "size_bytes": 1,
                        "md5": "0" * 32,
                        "content_type": "image/tiff",
                        "directory_label": "d",
                        "year": 1992,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(lrcc_dvnl.ManifestError):
        lrcc_dvnl.load_manifest(str(bad))


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(lrcc_dvnl.ManifestError):
        lrcc_dvnl.load_manifest(str(tmp_path / "nope.json"))
