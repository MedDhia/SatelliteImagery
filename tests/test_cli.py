from __future__ import annotations

import json

import pytest

from satimg.cli import main
from satimg.datasets import lrcc_dvnl


def test_list_shows_products(capsys):
    assert main(["lrcc-dvnl", "list"]) == 0
    out = capsys.readouterr().out
    assert "lrcc-dvnl" in out
    assert "1992-2022" in out
    assert "CC0 1.0" in out


def test_list_per_file_detail(capsys):
    assert main(["lrcc-dvnl", "list", "--product", "lrcc-dvnl", "--years", "1992"]) == 0
    out = capsys.readouterr().out
    assert "LACC_1992.tif" in out


def test_list_json_is_parseable(capsys):
    assert main(["lrcc-dvnl", "list", "--years", "1992-1994", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [entry["year"] for entry in payload] == [1992, 1993, 1994]
    assert all(entry["url"].startswith("https://") for entry in payload)


def test_download_dry_run_touches_no_network(capsys, tmp_path):
    code = main(
        [
            "lrcc-dvnl",
            "download",
            "--years",
            "1992-1993",
            "--dest",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("api/access/datafile") == 2
    assert not list(tmp_path.iterdir())


def test_verify_reports_missing_files(capsys, tmp_path):
    code = main(["lrcc-dvnl", "verify", "--years", "1992", "--dest", str(tmp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "MISSING" in captured.err


def test_verify_detects_corruption(capsys, tmp_path):
    data_file = lrcc_dvnl.annual_series([1992])[0]
    target = data_file.local_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x00" * data_file.size_bytes)

    code = main(["lrcc-dvnl", "verify", "--years", "1992", "--dest", str(tmp_path)])

    assert code == 1
    assert "CORRUPT" in capsys.readouterr().err


def test_verify_accepts_a_locally_repaired_file(capsys, tmp_path):
    """A fix-crs'd raster must not be reported as corrupt."""
    from satimg import provenance

    data_file = lrcc_dvnl.annual_series([1992])[0]
    target = data_file.local_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Different bytes and a different size than published, but with the
    # pre-repair digest recorded.
    target.write_bytes(b"\x00" * (data_file.size_bytes + 100))
    provenance.write_repair_record(
        target,
        original_md5=data_file.md5,
        original_size=data_file.size_bytes,
        operation="fix-crs",
    )

    code = main(["lrcc-dvnl", "verify", "--years", "1992", "--dest", str(tmp_path)])

    assert code == 0
    assert "REPAIRED" in capsys.readouterr().out


def test_verify_rejects_a_repair_record_for_different_bytes(capsys, tmp_path):
    """A sidecar recording some other file's digest must not excuse corruption."""
    from satimg import provenance

    data_file = lrcc_dvnl.annual_series([1992])[0]
    target = data_file.local_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x00" * 10)
    provenance.write_repair_record(
        target, original_md5="f" * 32, original_size=10, operation="fix-crs"
    )

    code = main(["lrcc-dvnl", "verify", "--years", "1992", "--dest", str(tmp_path)])

    assert code == 1
    assert "CORRUPT" in capsys.readouterr().err


def test_invalid_year_is_a_clean_error(capsys):
    assert main(["lrcc-dvnl", "download", "--years", "1990", "--dry-run"]) == 1
    assert "not in dataset" in capsys.readouterr().err


def test_cite_text_and_bibtex(capsys):
    assert main(["lrcc-dvnl", "cite"]) == 0
    text = capsys.readouterr().out
    assert "Scientific Data" in text
    assert "10.7910/DVN/15IKI5" in text

    assert main(["lrcc-dvnl", "cite", "--format", "bibtex"]) == 0
    bibtex = capsys.readouterr().out
    assert "@article{tang2025lrccdvnl" in bibtex
    assert "@misc{tang2025lrccdvnldata" in bibtex


def test_no_command_prints_help(capsys):
    assert main([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_version_flag():
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
