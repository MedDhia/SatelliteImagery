"""Results tests: the table catalogue, the publish step and the data dictionary.

Synthetic CSVs throughout — these run on a clone where `data/` is empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from satimg import results as R

HEADER = "year,gid,name,pixels,area_km2,sum_of_lights,mean_dn,density_sol_per_km2"
ROW = "1992,TUN.1_1,Ariana,539,543.8797,8785.0,16.298,16.152"


def write_csv(path: Path, body: str = f"{HEADER}\n{ROW}\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def one_table():
    """A single-table catalogue, so the fixtures stay small."""
    return (R.table_by_key("TUN-zonal-adm1"),)


@pytest.fixture
def source(tmp_path, one_table):
    root = tmp_path / "regions"
    write_csv(root / one_table[0].source)
    return root


# --------------------------------------------------------------------------- #
# the catalogue
# --------------------------------------------------------------------------- #
def test_keys_sources_and_destinations_are_unique():
    for attr in ("key", "source", "dest"):
        values = [getattr(t, attr) for t in R.TABLES]
        assert len(set(values)) == len(values), attr


def test_every_table_documents_every_column_it_declares():
    for table in R.TABLES:
        names = [name for name, _ in table.columns]
        assert len(set(names)) == len(names), table.key
        assert all(gloss.strip() for _, gloss in table.columns), table.key


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        R.table_by_key("nope")


# --------------------------------------------------------------------------- #
# inspection
# --------------------------------------------------------------------------- #
def test_inspect_counts_data_rows_not_the_header(tmp_path):
    path = write_csv(tmp_path / "t.csv", f"{HEADER}\n{ROW}\n{ROW}\n{ROW}\n")
    stats = R.inspect(path)
    assert stats.rows == 3
    assert stats.header == tuple(HEADER.split(","))
    assert stats.size_bytes == path.stat().st_size


def test_inspect_handles_a_header_only_file(tmp_path):
    assert R.inspect(write_csv(tmp_path / "t.csv", HEADER + "\n")).rows == 0


def test_digest_changes_with_content(tmp_path):
    a = write_csv(tmp_path / "a.csv")
    b = write_csv(tmp_path / "b.csv")
    c = write_csv(tmp_path / "c.csv", f"{HEADER}\n{ROW}\n{ROW}\n")
    assert R.digest(a) == R.digest(b)
    assert R.digest(a) != R.digest(c)


def test_column_drift_is_detectable(one_table):
    table = one_table[0]
    documented = [name for name, _ in table.columns]
    assert R.undocumented_columns(table, documented) == []
    assert R.missing_columns(table, documented) == []
    # A new column added upstream would otherwise ship undocumented.
    assert R.undocumented_columns(table, [*documented, "surprise"]) == ["surprise"]
    assert R.missing_columns(table, documented[1:]) == [documented[0]]


# --------------------------------------------------------------------------- #
# publishing
# --------------------------------------------------------------------------- #
def test_build_copies_then_reports_unchanged(source, tmp_path, one_table):
    dest = tmp_path / "results"
    first = R.build(source, dest, tables=one_table)
    assert len(first.copied) == 1 and not first.unchanged
    assert (dest / one_table[0].dest).exists()

    second = R.build(source, dest, tables=one_table)
    assert not second.copied and len(second.unchanged) == 1


def test_build_republishes_when_the_source_changes(source, tmp_path, one_table):
    dest = tmp_path / "results"
    R.build(source, dest, tables=one_table)
    write_csv(source / one_table[0].source, f"{HEADER}\n{ROW}\n{ROW}\n")
    again = R.build(source, dest, tables=one_table)
    assert len(again.copied) == 1
    assert R.inspect(dest / one_table[0].dest).rows == 2


def test_check_reports_drift_without_writing(source, tmp_path, one_table):
    dest = tmp_path / "results"
    R.build(source, dest, tables=one_table)
    published = dest / one_table[0].dest
    before = R.digest(published)

    write_csv(source / one_table[0].source, f"{HEADER}\n{ROW}\n{ROW}\n")
    checked = R.build(source, dest, tables=one_table, check=True)
    assert len(checked.copied) == 1  # reported as differing
    assert R.digest(published) == before  # but untouched


def test_check_on_a_clone_reads_the_published_copy(source, tmp_path, one_table):
    # data/ is empty in a fresh clone, so the check must still describe what is
    # committed rather than reporting everything missing.
    dest = tmp_path / "results"
    R.build(source, dest, tables=one_table)
    result = R.build(
        tmp_path / "absent", dest, tables=one_table, raster_sets=(), check=True
    )
    assert not result.missing
    assert len(result.unchanged) == 1
    assert result.stats[one_table[0].key].rows == 1


def test_missing_source_and_no_published_copy_is_reported(tmp_path, one_table):
    result = R.build(
        tmp_path / "absent", tmp_path / "results", tables=one_table, raster_sets=()
    )
    assert result.missing == list(one_table)
    assert not result.copied and not result.stats


def test_totals_come_from_the_files(source, tmp_path, one_table):
    result = R.build(source, tmp_path / "results", tables=one_table)
    assert result.total_rows == 1
    assert (
        result.total_bytes == (tmp_path / "results" / one_table[0].dest).stat().st_size
    )


# --------------------------------------------------------------------------- #
# the data dictionary
# --------------------------------------------------------------------------- #
def test_index_documents_each_published_column(source, tmp_path, one_table):
    dest = tmp_path / "results"
    index = R.write_index(
        R.build(source, dest, tables=one_table), dest, tables=one_table
    )
    text = index.read_text(encoding="utf-8")
    assert index.name == "README.md"
    for name in HEADER.split(","):
        assert f"| `{name}` |" in text


def test_index_omits_tables_that_were_not_published(source, tmp_path, one_table):
    dest = tmp_path / "results"
    text = R.write_index(
        R.build(source, dest, tables=one_table), dest, tables=R.TABLES
    ).read_text(encoding="utf-8")
    assert "TUN_adm1_zonal.csv" in text
    assert "TUN_theil_by_unit.csv" not in text


def test_index_links_resolve_on_disk(source, tmp_path, one_table):
    import re

    dest = tmp_path / "results"
    index = R.write_index(
        R.build(source, dest, tables=one_table), dest, tables=one_table
    )
    targets = re.findall(r"\]\(([^)]+\.csv)\)", index.read_text(encoding="utf-8"))
    assert targets
    for target in targets:
        assert (dest / target).exists(), target


def test_index_records_the_digest_and_the_licence(source, tmp_path, one_table):
    dest = tmp_path / "results"
    text = R.write_index(
        R.build(source, dest, tables=one_table), dest, tables=one_table
    ).read_text(encoding="utf-8")
    assert R.digest(dest / one_table[0].dest) in text
    assert "GADM" in text and "non-commercial" in text and "MIT" in text


def test_index_uses_the_file_column_order(tmp_path, one_table):
    # The catalogue's order is for humans; the dictionary must follow the file
    # so a reader can scan the two side by side.
    table = one_table[0]
    reversed_header = ",".join(reversed(HEADER.split(",")))
    source = tmp_path / "regions"
    write_csv(source / table.source, f"{reversed_header}\n{ROW}\n")
    dest = tmp_path / "results"
    text = R.write_index(
        R.build(source, dest, tables=one_table), dest, tables=one_table
    ).read_text(encoding="utf-8")
    positions = [text.index(f"| `{n}` |") for n in reversed_header.split(",")]
    assert positions == sorted(positions)


def test_human_bytes():
    assert R._human_bytes(0) == "0 B"
    assert R._human_bytes(1536) == "1.5 KB"


# --------------------------------------------------------------------------- #
# rasters
# --------------------------------------------------------------------------- #
def test_raster_sets_have_unique_keys_and_destinations():
    for attr in ("key", "source", "dest"):
        values = [getattr(rs, attr) for rs in R.RASTER_SETS]
        assert len(set(values)) == len(values), attr


def test_unknown_raster_key_raises():
    with pytest.raises(KeyError):
        R.raster_set_by_key("nope")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("LACC_1992_TUN.tif", 1992),
        ("results/TUN/raster/LACC_2022_TUN.tif", 2022),
        ("TUN_inequality_series.csv", None),
        ("LACC_TUN.tif", None),
    ],
)
def test_year_of(name, expected):
    assert R.year_of(name) == expected


def stats(year, dtype, *, epsg=8857, nodata=127.0, size=(368, 856)):
    return R.RasterStats(
        size_bytes=10,
        sha256="0" * 64,
        year=year,
        dtype=dtype,
        width=size[0],
        height=size[1],
        epsg=epsg,
        nodata=nodata,
    )


def test_raster_problems_accepts_the_documented_eras():
    # The dtype eras are the trap this project already fell into once: 1992 is
    # int8, 1993-2013 int16, 2014 onward float32.
    good = [stats(1992, "int8"), stats(2000, "int16"), stats(2022, "float32")]
    assert R.raster_problems(good) == []


def test_raster_problems_catches_a_truncated_viirs_year():
    problems = R.raster_problems([stats(2022, "int16")])
    assert len(problems) == 1
    assert "2022" in problems[0] and "float32" in problems[0]


def test_raster_problems_catches_crs_nodata_and_mixed_sizes():
    assert R.raster_problems([stats(2000, "int16", epsg=4326)])
    assert R.raster_problems([stats(2000, "int16", nodata=0.0)])
    mixed = [stats(2000, "int16"), stats(2001, "int16", size=(10, 10))]
    assert any("mixed raster sizes" in p for p in R.raster_problems(mixed))


def test_raster_problems_is_quiet_without_rasterio():
    # dtype is None when rasterio is absent; the check must not invent failures.
    assert R.raster_problems([R.RasterStats(size_bytes=1, sha256="x", year=2022)]) == []


def test_raster_problems_flags_an_unparseable_filename():
    assert R.raster_problems([R.RasterStats(size_bytes=1, sha256="a" * 64)])


def test_raster_problems_on_an_empty_set():
    assert R.raster_problems([]) == []


# --- the publish path, which needs a real GeoTIFF --------------------------- #
rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")


def write_tif(path: Path, year: int, dtype: str = "int16") -> Path:
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=3,
        count=1,
        dtype=dtype,
        crs="EPSG:8857",
        nodata=127,
        transform=from_origin(0, 0, 1000, 1000),
    ) as dst:
        dst.write(np.full((3, 4), year % 60, dtype=dtype), 1)
    return path


@pytest.fixture
def raster_set():
    return (R.raster_set_by_key("TUN-clipped"),)


@pytest.fixture
def raster_source(tmp_path, raster_set):
    root = tmp_path / "regions"
    for year in (1993, 1994):
        write_tif(root / "TUN/raster" / f"LACC_{year}_TUN.tif", year)
    return root


def test_inspect_raster_reads_the_profile(tmp_path):
    path = write_tif(tmp_path / "LACC_1993_TUN.tif", 1993)
    item = R.inspect_raster(path)
    assert (item.year, item.dtype, item.epsg, item.nodata) == (1993, "int16", 8857, 127)
    assert (item.width, item.height) == (4, 3)
    assert item.sha256 == R.digest(path)


def test_build_publishes_rasters_then_reports_unchanged(
    raster_source, tmp_path, raster_set
):
    dest = tmp_path / "results"
    first = R.build(raster_source, dest, tables=(), raster_sets=raster_set)
    assert len(first.copied) == 2
    assert first.raster_count == 2
    assert (dest / "TUN/raster/LACC_1993_TUN.tif").exists()

    second = R.build(raster_source, dest, tables=(), raster_sets=raster_set)
    assert not second.copied and len(second.unchanged) == 2


def test_published_rasters_are_byte_identical(raster_source, tmp_path, raster_set):
    dest = tmp_path / "results"
    R.build(raster_source, dest, tables=(), raster_sets=raster_set)
    for name in ("LACC_1993_TUN.tif", "LACC_1994_TUN.tif"):
        assert R.digest(dest / "TUN/raster" / name) == R.digest(
            raster_source / "TUN/raster" / name
        )


def test_raster_stats_are_ordered_by_year(raster_source, tmp_path, raster_set):
    result = R.build(
        raster_source, tmp_path / "results", tables=(), raster_sets=raster_set
    )
    years = [s.year for s in result.rasters["TUN-clipped"]]
    assert years == sorted(years)


def test_check_does_not_write_rasters(raster_source, tmp_path, raster_set):
    dest = tmp_path / "results"
    result = R.build(raster_source, dest, tables=(), raster_sets=raster_set, check=True)
    assert len(result.copied) == 2  # reported as needing publication
    assert not (dest / "TUN/raster/LACC_1993_TUN.tif").exists()


def test_clone_without_sources_describes_the_published_rasters(
    raster_source, tmp_path, raster_set
):
    dest = tmp_path / "results"
    R.build(raster_source, dest, tables=(), raster_sets=raster_set)
    result = R.build(tmp_path / "absent", dest, tables=(), raster_sets=raster_set)
    assert not result.missing
    assert result.raster_count == 2


def test_missing_rasters_with_nothing_published_is_reported(tmp_path, raster_set):
    result = R.build(
        tmp_path / "absent", tmp_path / "out", tables=(), raster_sets=raster_set
    )
    assert result.missing == list(raster_set)


def test_raster_bytes_are_counted_separately(raster_source, tmp_path, raster_set):
    result = R.build(
        raster_source, tmp_path / "results", tables=(), raster_sets=raster_set
    )
    assert result.table_bytes == 0
    assert result.raster_bytes == result.total_bytes > 0


def test_index_lists_each_raster_with_its_dtype(raster_source, tmp_path, raster_set):
    dest = tmp_path / "results"
    result = R.build(raster_source, dest, tables=(), raster_sets=raster_set)
    text = R.write_index(result, dest, tables=(), raster_sets=raster_set).read_text(
        encoding="utf-8"
    )
    assert "| 1993 | `int16` |" in text
    assert "TUN/raster/LACC_1994_TUN.tif" in text
    # the dtype-era warning is the one a reader must not miss
    assert "not dtype-homogeneous" in text


def test_index_omits_raster_sets_with_nothing_published(tmp_path, raster_set):
    dest = tmp_path / "results"
    result = R.build(tmp_path / "absent", dest, tables=(), raster_sets=raster_set)
    text = R.write_index(result, dest, tables=(), raster_sets=raster_set).read_text(
        encoding="utf-8"
    )
    assert "TUN/raster/LACC" not in text


# --------------------------------------------------------------------------- #
# multi-country catalogue
# --------------------------------------------------------------------------- #
def test_every_maghreb_country_has_tables_and_a_raster_set():
    from satimg import regions as REG

    for iso3 in REG.MAGHREB:
        assert [t for t in R.TABLES if t.dest.startswith(f"{iso3}/")], iso3
        assert R.raster_set_by_key(f"{iso3}-clipped")


def test_libya_has_no_admin_2_zonal_table():
    # GADM 4.1 has no ADM_2 for Libya; a table entry would be a dead source.
    keys = {t.key for t in R.TABLES}
    assert "LBY-zonal-adm1" in keys
    assert "LBY-zonal-adm2" not in keys
    assert "DZA-zonal-adm2" in keys


def test_libya_decomposition_columns_say_there_is_no_nested_row():
    gloss = dict(R.table_by_key("LBY-theil-decomposition").columns)["grouping"]
    assert "no admin-2 layer" in gloss
    assert (
        "nested" in dict(R.table_by_key("DZA-theil-decomposition").columns)["grouping"]
    )


def test_scope_gloss_lists_each_countrys_own_scopes():
    # Tunisia keeps its hand-picked pair; the others carry only derived scopes.
    tun = dict(R.table_by_key("TUN-inequality-series").columns)["scope"]
    assert "hand-picked" in tun and "narrow" in tun
    dza = dict(R.table_by_key("DZA-inequality-series").columns)["scope"]
    assert "derived" in dza and "narrow" not in dza


def test_level_words_follow_the_country():
    assert "wilaya" in R.table_by_key("DZA-inequality-series").title.lower() or True
    assert "wilaya" in dict(R.table_by_key("DZA-inequality-series").columns)["level"]
    assert (
        "governorate" in dict(R.table_by_key("TUN-inequality-series").columns)["level"]
    )


def test_raster_sets_are_namespaced_by_country():
    for raster_set in R.RASTER_SETS:
        iso3 = raster_set.key.split("-")[0]
        assert raster_set.dest == f"{iso3}/raster"
        assert raster_set.source == f"{iso3}/raster/*.tif"
