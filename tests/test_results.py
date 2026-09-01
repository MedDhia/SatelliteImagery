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
    return (R.table_by_key("zonal-adm1"),)


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
    result = R.build(tmp_path / "absent", dest, tables=one_table, check=True)
    assert not result.missing
    assert len(result.unchanged) == 1
    assert result.stats[one_table[0].key].rows == 1


def test_missing_source_and_no_published_copy_is_reported(tmp_path, one_table):
    result = R.build(tmp_path / "absent", tmp_path / "results", tables=one_table)
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
