from __future__ import annotations

from satimg import provenance


def test_sidecar_path_appends_suffix(tmp_path):
    assert provenance.sidecar_path(tmp_path / "LACC_1992.tif").name == (
        "LACC_1992.tif.satimg.json"
    )


def test_read_record_returns_none_without_a_sidecar(tmp_path):
    assert provenance.read_record(tmp_path / "x.tif") is None
    assert provenance.original_md5(tmp_path / "x.tif") is None


def test_write_and_read_a_repair_record(tmp_path):
    target = tmp_path / "x.tif"
    target.write_bytes(b"data")

    provenance.write_repair_record(
        target,
        original_md5="ABC" + "0" * 29,
        original_size=4,
        operation="fix-crs",
        details={"epsg": 8857},
    )

    record = provenance.read_record(target)
    assert record["file"] == "x.tif"
    assert record["original_size"] == 4
    assert len(record["operations"]) == 1
    assert record["operations"][0]["operation"] == "fix-crs"
    assert record["operations"][0]["details"]["epsg"] == 8857
    # Digests are compared lowercased.
    assert provenance.original_md5(target) == ("ABC" + "0" * 29).lower()


def test_second_repair_keeps_the_first_original_digest(tmp_path):
    target = tmp_path / "x.tif"
    target.write_bytes(b"data")

    provenance.write_repair_record(
        target, original_md5="a" * 32, original_size=4, operation="fix-crs"
    )
    provenance.write_repair_record(
        target, original_md5="b" * 32, original_size=99, operation="fix-crs"
    )

    record = provenance.read_record(target)
    # The digest must still refer to the downloaded bytes, not the first repair.
    assert record["original_md5"] == "a" * 32
    assert record["original_size"] == 4
    assert len(record["operations"]) == 2


def test_corrupt_sidecar_is_ignored(tmp_path):
    target = tmp_path / "x.tif"
    target.write_bytes(b"data")
    provenance.sidecar_path(target).write_text("{ broken", encoding="utf-8")

    assert provenance.read_record(target) is None
    assert provenance.original_md5(target) is None


def test_non_object_sidecar_is_ignored(tmp_path):
    target = tmp_path / "x.tif"
    target.write_bytes(b"data")
    provenance.sidecar_path(target).write_text("[1, 2]", encoding="utf-8")

    assert provenance.read_record(target) is None
