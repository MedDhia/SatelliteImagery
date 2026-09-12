"""Results tests: the table catalogue, the publish step and the data dictionary.

Synthetic CSVs throughout — these run on a clone where `data/` is empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from satimg import regions as R2
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
    for attr in ("key", "dest"):
        values = [getattr(t, attr) for t in R.TABLES]
        assert len(set(values)) == len(values), attr
    # Sources are unique too, except for the cross-country tables, which have
    # none: they are computed from the published CSVs, not copied from data/.
    sources = [t.source for t in R.TABLES if not t.in_place]
    assert len(set(sources)) == len(sources)


def test_an_in_place_table_has_no_source_to_copy_from():
    in_place = [t for t in R.TABLES if t.in_place]
    # One pair per comparison pool: the default pool keeps the unprefixed
    # names it was published under, every other pool is prefixed.
    from satimg import aridity as A
    from satimg import regions as Reg
    from satimg import trends as T

    expected = {T.trends_table(p) for p in Reg.POOLS}
    expected |= {A.vs_light_table(p) for p in Reg.POOLS}
    assert {t.dest for t in in_place} == expected
    for table in in_place:
        assert table.source_path("data/regions") is None


def test_every_committed_top_level_table_is_catalogued(tmp_path):
    """A committed CSV outside the catalogue is a number nobody can check.

    Only this direction is asserted. The reverse - catalogued but not yet on
    disk - is the legitimate `not_generated` state: the catalogue is derived
    from `regions.POOLS`, so a newly added pool is listed before its command
    has ever run.
    """
    from pathlib import Path

    published = Path(__file__).resolve().parents[1] / "results"
    if not published.exists():
        pytest.skip("results/ not present")
    on_disk = {p.name for p in published.glob("*.csv")}
    catalogued = {t.dest for t in R.TABLES if "/" not in t.dest}
    assert on_disk <= catalogued, on_disk - catalogued


def test_a_catalogued_table_not_yet_written_is_pending_not_missing(tmp_path):
    result = R.build(tmp_path / "src", tmp_path / "dest")
    assert not result.missing
    assert set(result.not_generated) == {t.dest for t in R.TABLES if t.in_place}


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
    """Nothing published for the country at all: pending, not a fault.

    It becomes `missing` - an error - only once the country has some other
    output published, because then the gap is a partial publish.
    """
    result = R.build(
        tmp_path / "absent", tmp_path / "results", tables=one_table, raster_sets=()
    )
    assert not result.missing
    assert result.not_analysed == [one_table[0].dest.split("/")[0]]
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
    assert not result.missing
    assert result.not_analysed == [raster_set[0].dest.split("/")[0]]


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
    # Sourced from GADM's ENGTYPE fields: Algeria's admin-2 units are communes,
    # not the "daira" that was hand-written and rendered onto its maps.
    dza = dict(R.table_by_key("DZA-inequality-series").columns)["level"]
    assert "province" in dza and "commune" in dza
    tun = dict(R.table_by_key("TUN-inequality-series").columns)["level"]
    assert "governorate" in tun and "delegation" in tun


def test_raster_sets_are_namespaced_by_country():
    for raster_set in R.RASTER_SETS:
        iso3 = raster_set.key.split("-")[0]
        assert raster_set.dest == f"{iso3}/raster"
        assert raster_set.source == f"{iso3}/raster/*.tif"


# --------------------------------------------------------------------------- #
# not analysed yet vs published with a hole in it
# --------------------------------------------------------------------------- #
def test_a_country_with_no_outputs_at_all_is_not_an_error(tmp_path):
    """The catalogue lists a country before it is run.

    During a staged rollout that is the normal state. Failing on it would make
    `results build` unusable until the very last country finished.
    """
    result = R.build(tmp_path / "src", tmp_path / "dest")
    assert not result.missing
    assert set(result.not_analysed) == set(R2.COUNTRIES)
    # The cross-country tables belong to no country and are tracked apart.
    assert set(result.not_generated) == {t.dest for t in R.TABLES if t.in_place}


def test_a_country_published_with_a_gap_in_it_is_an_error(tmp_path):
    """The dangerous state: some outputs landed and one did not."""
    dest = tmp_path / "dest"
    iso3 = R2.COUNTRIES[0]
    table = next(t for t in R.TABLES if t.dest.startswith(f"{iso3}/"))
    written = dest / table.dest
    written.parent.mkdir(parents=True, exist_ok=True)
    written.write_text("year\n1992\n", encoding="utf-8")

    result = R.build(tmp_path / "src", dest)
    assert iso3 not in result.not_analysed
    gaps = {getattr(item, "dest", "") for item in result.missing}
    assert any(d.startswith(f"{iso3}/") for d in gaps)
    assert table.dest not in gaps  # the one that did land is not a gap


def test_cross_country_tables_are_never_counted_as_a_country(tmp_path):
    result = R.build(tmp_path / "src", tmp_path / "dest")
    for iso3 in result.not_analysed:
        assert "." not in iso3 and "/" not in iso3
        assert iso3 in R2.COUNTRIES


# --- the dark_2022 median tie ----------------------------------------------
#
# The gloss for `dark_2022` used to name Iraq's Ninawa in every pool, because
# all four tables were generated from one shared column template. Three of the
# four contain no Iraqi unit, and Africa has no tie at all - so the sentence
# was wrong about the example and, there, about the point it was making.
# Naming a unit is a claim about published data, so it gets checked.


def _pool_medians():
    """(pool, median, tied unit description or None) from the committed CSVs.

    A unit with no land pixel in the light raster has no ``mean_dn_2022``, and
    such a value must never reach ``statistics.median``. NaN is not ordered
    against anything, so one of them in the list makes ``sorted`` return an
    arbitrary permutation and the "median" a value with no meaning: Oceania read
    63.0, the DN ceiling, for a pool where 121 of 205 units sit below 1.0. Skip
    them exactly as :func:`aridity.dark_cut` does - and then check that this is
    in fact what it does, so the two readings can never quietly diverge.
    """
    import csv
    import math
    import statistics
    from pathlib import Path

    from satimg import aridity as A
    from satimg import regions as R

    out = []
    for pool in R.POOLS:
        path = Path("results") / A.vs_light_table(pool)
        if not path.exists():  # pool not published yet
            continue
        rows = list(csv.DictReader(path.open()))
        if not rows:
            continue
        measured = [r for r in rows if _as_float(r["mean_dn_2022"]) is not None]
        values = [float(r["mean_dn_2022"]) for r in measured]
        assert not any(math.isnan(v) for v in values)
        median = statistics.median(values)
        tied = [r for r in measured if float(r["mean_dn_2022"]) == median]
        out.append((pool, median, tied))
    return out


def _as_float(text):
    """The number in a published cell, or None where there is no measurement.

    Blank means unmeasured. The literal ``nan`` also has to be caught here:
    ``float`` accepts it silently, and it is the shape that poisoned the cut.
    """
    if text is None or not text.strip():
        return None
    value = float(text)
    return None if value != value else value


def test_the_median_this_file_computes_is_the_one_the_code_cuts_at():
    """The check reimplements the median; make sure it reimplements *that* one.

    Reimplementing is deliberate - a check that calls the code under test only
    proves it agrees with itself. But a reimplementation that has drifted is
    worse than none, so the two are compared here rather than trusted apart.
    """
    import csv
    from pathlib import Path

    from satimg import aridity as A

    for pool, median, _ in _pool_medians():
        rows = list((Path("results") / A.vs_light_table(pool)).open())
        values = [
            v
            for v in (_as_float(r["mean_dn_2022"]) for r in csv.DictReader(iter(rows)))
            if v is not None
        ]
        assert A.dark_cut(values) == median, (
            f"pool {pool!r}: this file reads the median as {median}, "
            f"aridity.dark_cut cuts at {A.dark_cut(values)}"
        )


#: Columns of the cross-country tables that something downstream aggregates -
#: a median, a rank, a sort. These are the ones NaN cannot appear in.
AGGREGATED_COLUMNS = (
    "mean_dn_1992",
    "mean_dn_2022",
    "desert_share",
    "dryland_share",
    "humid_share",
)


def test_no_aggregated_column_carries_the_literal_nan():
    """An unmeasured cell is blank. ``nan`` in a summed column is a trap.

    ``float("nan")`` parses without complaint and then destroys the ordering of
    any sort it reaches, so a median over it comes back *wrong* rather than
    absent - Oceania's read 63.0, the DN ceiling, for a pool whose units are
    mostly below 1.0. Seven Oceanian units published it: four with no land pixel
    in the light raster, three with no aridity cell.

    Scoped deliberately to the cross-country tables and to the columns
    something aggregates. A per-country series may hold a genuinely undefined
    value - Theil L where a unit has zero light, a half-life where the trend
    rises, the nested split where there is no nesting - and nothing takes a
    median of those. Whether they too should be blank is a separate question
    about encoding, not about a wrong number.

    Name columns are excluded, and not for convenience: Thailand's province of
    **Nan** is a real place, and a case-insensitive match for "nan" flags it.
    """
    import csv
    from pathlib import Path

    offenders = []
    for path in sorted(Path("results").glob("*.csv")):
        for row in csv.DictReader(path.open()):
            for column in AGGREGATED_COLUMNS:
                value = row.get(column)
                if value is None or not value.strip():
                    continue
                number = float(value)
                if number != number:  # NaN, the only value unequal to itself
                    offenders.append(f"{path.name}:{column}")
    assert not offenders, (
        f"{len(offenders)} aggregated cell(s) carry NaN, which a median will "
        f"silently mis-sort rather than reject: {sorted(set(offenders))}"
    )


def test_named_median_ties_are_real():
    """Every pool named in MEDIAN_TIES must actually have a unit on its median."""
    from satimg import results as RS

    for pool, median, tied in _pool_medians():
        named = RS.MEDIAN_TIES.get(pool)
        if named is None:
            assert not tied, (
                f"pool {pool!r} has {len(tied)} unit(s) exactly on its median "
                f"{median} but MEDIAN_TIES names none; the strict '<' is "
                "load-bearing there and the gloss should say so"
            )
            continue
        assert tied, (
            f"MEDIAN_TIES names {named!r} for pool {pool!r}, but no unit sits "
            f"on its median {median}"
        )
        # the named unit must be one of the tied ones, not merely some unit
        assert any(r["name"] in named or r["iso3"] in named for r in tied), (
            f"MEDIAN_TIES says {named!r} for {pool!r}, but the tie is "
            f"{[(r['iso3'], r['name']) for r in tied]}"
        )


def test_dark_2022_gloss_never_names_another_pools_unit():
    """The defect itself: an Iraqi unit cited in pools without Iraqi units."""
    from satimg import regions as R
    from satimg import results as RS

    for table in RS.CROSS_TABLES:
        if "aridity-vs-light" not in table.key:
            continue
        pool = table.key.rsplit("-aridity-vs-light", 1)[0]
        gloss = dict(table.columns)["dark_2022"]
        named = RS.MEDIAN_TIES.get(pool)
        if named is None:
            assert "sits exactly on" not in gloss, (
                f"pool {pool!r} has no median tie, but its dark_2022 gloss "
                f"claims one: {gloss!r}"
            )
        else:
            assert named in gloss
        # Whatever it names, the country must belong to this pool.
        if "Iraq" in gloss:
            assert "IRQ" in R.pool_countries(pool), (
                f"pool {pool!r} does not contain Iraq, but its dark_2022 "
                "gloss names an Iraqi unit"
            )


def test_no_published_csv_is_empty():
    """A zero-byte table cannot be told apart from a failed write.

    Tokelau is the case that made this real: its 17 pixels are unlit in all 31
    years, so it has no lit unit to contribute anything and its per-unit table
    has no rows. Written header-only it states its schema and says there is
    nothing to report; written empty it broke `satimg results build`, which
    left the published catalogue stale at 147 countries for several commits
    because the caller only checked the copy count.
    """
    published = Path(__file__).resolve().parents[1] / "results"
    empty = [p for p in published.rglob("*.csv") if p.stat().st_size == 0]
    assert not empty, [str(p) for p in empty]


def test_every_published_csv_has_a_header_row():
    """Stronger than non-empty: the first line must name the columns."""
    import csv as _csv

    published = Path(__file__).resolve().parents[1] / "results"
    for path in sorted(published.rglob("*.csv")):
        with open(path, encoding="utf-8", newline="") as handle:
            header = next(_csv.reader(handle), None)
        assert header, path
        assert all(field.strip() for field in header), (path, header)


def test_unit_sort_key_orders_digits_numerically():
    """TUN.2_1 before TUN.10_1, which a plain string sort gets backwards."""
    from satimg.analysis import unit_sort_key

    gids = ["TUN.10_1", "TUN.2_1", "TUN.1_1", "CHN.1.1_1", "HKG.1_1"]
    assert sorted(gids, key=lambda g: unit_sort_key("X", g)) == [
        "CHN.1.1_1",
        "HKG.1_1",
        "TUN.1_1",
        "TUN.2_1",
        "TUN.10_1",
    ]
    # the iso3 leads, so a country's units never interleave with another's
    pairs = [("TUN", "TUN.9_1"), ("DZA", "DZA.1_1"), ("TUN", "TUN.1_1")]
    assert [p[1] for p in sorted(pairs, key=lambda p: unit_sort_key(*p))] == [
        "DZA.1_1",
        "TUN.1_1",
        "TUN.9_1",
    ]


def test_every_published_aridity_join_is_sorted():
    """Row order is a property of the data, not of upstream cache state.

    The published tables used to follow the GADM layer's feature order, so
    re-running one country from a differently-filtered cache could move rows
    that had not changed - 37 of them, once, when the United States was
    re-run uncropped. A sorted table cannot do that: a re-run that changes no
    number produces no diff, and a change cannot hide inside a reordering.
    """
    import csv as _csv

    from satimg import aridity as A
    from satimg import regions as R
    from satimg.analysis import unit_sort_key

    published = Path(__file__).resolve().parents[1] / "results"
    if not published.is_dir():
        pytest.skip("no published results tree here")
    seen = 0
    for pool in R.POOLS:
        path = published / A.vs_light_table(pool)
        if not path.exists():
            continue
        rows = list(_csv.DictReader(path.open(encoding="utf-8", newline="")))
        keys = [unit_sort_key(r["iso3"], r["gid"]) for r in rows]
        assert keys == sorted(keys), f"{path.name} is not in unit_sort_key order"
        assert len(set(keys)) == len(keys), f"{path.name} has a duplicate unit"
        seen += 1
    assert seen, "no aridity joins found to check"


def test_every_published_trends_table_groups_countries():
    """Countries in iso3 order; each one's rows stay in the order emitted."""
    import csv as _csv

    from satimg import regions as R
    from satimg import trends as T

    published = Path(__file__).resolve().parents[1] / "results"
    if not published.is_dir():
        pytest.skip("no published results tree here")
    seen = 0
    for pool in R.POOLS:
        path = published / T.trends_table(pool)
        if not path.exists():
            continue
        isos = [r["iso3"] for r in _csv.DictReader(path.open(encoding="utf-8"))]
        assert isos == sorted(isos), f"{path.name} is not grouped by iso3"
        seen += 1
    assert seen, "no trends tables found to check"


def test_docs_quote_the_darkness_cuts_the_tables_actually_have():
    """Five regional docs each carry a cross-pool comparison table.

    Adding the rest of the world moved five pools' medians at once, and every
    one of those tables silently became wrong - the same class of drift
    MEDIAN_TIES is guarded against, but in prose. Rows look like

        | `europe` | 728 | 9.9373 |
        | north-america | 519 | odd | 10.1136 | Guatemala's Chimaltenango |

    so any row whose first cell names a pool is checked against that pool's
    published cut.
    """
    import csv as _csv
    import re
    import statistics

    from satimg import aridity as A
    from satimg import regions as R

    repo = Path(__file__).resolve().parents[1]
    published = repo / "results"
    if not published.is_dir():
        pytest.skip("no published results tree here")

    cuts = {}
    for pool in R.POOLS:
        path = published / A.vs_light_table(pool)
        if not path.exists():
            continue
        rows = list(_csv.DictReader(path.open(encoding="utf-8", newline="")))
        values = [float(r["mean_dn_2022"]) for r in rows if r["mean_dn_2022"].strip()]
        cuts[pool] = (len(values), statistics.median(values))

    checked = 0
    for md in sorted((repo / "docs").glob("*.md")):
        for line in md.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip().strip("*`") for c in line.strip("|").split("|")]
            if not cells or cells[0] not in cuts:
                continue
            n, cut = cuts[cells[0]]
            numbers = [
                c.strip("*") for c in cells[1:] if re.fullmatch(r"[\d. ]+", c or "x")
            ]
            floats = [c for c in numbers if "." in c]
            if not floats:
                continue  # a link or prose row, not a cut table
            assert f"{cut:.4f}" in floats, (
                f"{md.name} says {floats} for {cells[0]}, published cut is {cut:.4f}"
            )
            ints = [int(c.replace(" ", "")) for c in numbers if "." not in c]
            assert n in ints, (
                f"{md.name} says {ints} units for {cells[0]}, published count is {n}"
            )
            checked += 1
    assert checked >= 15, f"only {checked} pool rows found across the docs"
