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


# --------------------------------------------------------------------------- #
# trends
# --------------------------------------------------------------------------- #
def series_csv(path, iso3, rates):
    """A minimal inequality series a country's trends row can be fit from."""
    import math

    header = "year,level,level_label,scope,zeros,n,gini,theil_t,theil_l,"
    header += "sum_of_lights,lit_share\n"
    lines = [header]
    total, intensive, extensive = rates
    for year in range(1992, 2023):
        t = math.exp(total / 100 * (year - 1992))
        i = math.exp(intensive / 100 * (year - 1992))
        share = 0.2 * math.exp(extensive / 100 * (year - 1992))
        lines.append(
            f"{year},pixel,pixel,all,zeros_included,100,0.5,{t},nan,1000,{share}\n"
        )
        lines.append(f"{year},pixel,pixel,all,lit_only,50,0.4,{i},nan,1000,1.0\n")
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{iso3}_inequality_series.csv").write_text("".join(lines))


def test_trends_writes_the_table_and_names_the_trajectories(tmp_path, capsys):
    series_csv(tmp_path / "SOM", "SOM", (-0.96, +1.11, +7.10))
    series_csv(tmp_path / "BHR", "BHR", (-4.09, -3.49, +0.10))

    code = main(
        ["trends", "--country", "SOM,BHR", "--results", str(tmp_path), "--no-figure"]
    )
    assert code == 0

    out = capsys.readouterr().out
    assert "trends_by_country.csv" in out
    assert "extensive spreader" in out and "SOM" in out
    assert "intensive converger" in out and "BHR" in out
    assert (tmp_path / "trends_by_country.csv").exists()


def test_trends_says_the_post_2014_acceleration_is_the_instrument(tmp_path, capsys):
    series_csv(tmp_path / "SOM", "SOM", (-0.96, +1.11, +7.10))
    main(["trends", "--country", "SOM", "--results", str(tmp_path), "--no-figure"])
    out = capsys.readouterr().out
    assert "instrument signature" in out
    assert "must not be compared" in out


def test_trends_refuses_an_empty_results_directory(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["trends", "--country", "all", "--results", str(tmp_path)])
    assert "inequality" in str(excinfo.value)


def test_trends_draws_the_figure_into_the_gallery(tmp_path):
    pytest.importorskip("matplotlib")
    from satimg import trends

    series_csv(tmp_path / "SOM", "SOM", (-0.96, +1.11, +7.10))
    series_csv(tmp_path / "BHR", "BHR", (-4.09, -3.49, +0.10))
    gallery = tmp_path / "figures"
    code = main(
        [
            "trends",
            "--country",
            "SOM,BHR",
            "--results",
            str(tmp_path),
            "--figures",
            str(gallery),
        ]
    )
    assert code == 0
    assert (gallery / trends.PACE_FIGURE).exists()


# --------------------------------------------------------------------------- #
# aridity
# --------------------------------------------------------------------------- #
def aridity_country(root, iso3, units, mean_dn):
    import csv as _csv

    folder = root / iso3
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{iso3}_adm1_aridity.csv", "w", newline="") as handle:
        writer = _csv.DictWriter(
            handle,
            fieldnames=[
                "gid",
                "name",
                "area_km2",
                "pixels_classified",
                "desert_share",
                "dryland_share",
                "humid_share",
            ],
        )
        writer.writeheader()
        for gid, name, share in units:
            writer.writerow(
                {
                    "gid": gid,
                    "name": name,
                    "area_km2": 100.0,
                    "pixels_classified": 100,
                    "desert_share": share,
                    "dryland_share": 1.0,
                    "humid_share": 0.0,
                }
            )
    with open(folder / f"{iso3}_adm1_zonal.csv", "w", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["year", "gid", "mean_dn"])
        writer.writeheader()
        for year in (1992, 2022):
            for gid, _, _ in units:
                writer.writerow({"year": year, "gid": gid, "mean_dn": mean_dn[gid]})


def test_aridity_vs_light_writes_the_table_and_reports_the_cells(tmp_path, capsys):
    # A real ISO3: `vs-light` pools every Arab League country deliberately,
    # because the darkness cut is a cross-country median. Narrowing it to one
    # country would move that cut without saying so, which is why there is no
    # --country flag to narrow it with.
    units = [
        ("TUN.91_1", "arid dark", 0.9),
        ("TUN.92_1", "green dark", 0.1),
        ("TUN.93_1", "arid lit", 0.8),
        ("TUN.94_1", "green lit", 0.0),
    ]
    aridity_country(
        tmp_path,
        "TUN",
        units,
        {"TUN.91_1": 0.5, "TUN.92_1": 1.0, "TUN.93_1": 20.0, "TUN.94_1": 30.0},
    )
    assert main(["aridity", "vs-light", "--results", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "aridity_vs_light.csv" in out
    assert "desert_dark" in out and "anomalously_dark" in out
    assert "strict <" in out
    # These gids belong to no light scope, so there is no lift to report - and
    # reporting one would have meant dividing by zero.
    assert "excludes no unit here" in out
    assert (tmp_path / "aridity_vs_light.csv").exists()


def test_aridity_vs_light_refuses_an_empty_results_directory(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["aridity", "vs-light", "--results", str(tmp_path)])
    assert "aridity units" in str(excinfo.value)


def test_aridity_chart_draws_into_the_gallery(tmp_path):
    pytest.importorskip("matplotlib")
    from satimg import aridity as A

    units = [
        ("TUN.91_1", "a", 1.0),
        ("TUN.92_1", "b", 0.4),
        ("TUN.93_1", "c", 0.0),
        ("TUN.94_1", "d", 1.0),
    ]
    aridity_country(
        tmp_path,
        "TUN",
        units,
        {"TUN.91_1": 0.5, "TUN.92_1": 1.0, "TUN.93_1": 20.0, "TUN.94_1": 30.0},
    )
    gallery = tmp_path / "figures"
    code = main(
        [
            "aridity",
            "chart",
            "--results",
            str(tmp_path),
            "--figures",
            str(gallery),
        ]
    )
    assert code == 0
    assert (gallery / A.BANDS_FIGURE).exists()
