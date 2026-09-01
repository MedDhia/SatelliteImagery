from __future__ import annotations

import pytest

from satimg.util import format_table, human_bytes, parse_year_spec


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (None, "?"),
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KiB"),
        (16_594_900, "15.8 MiB"),
        (1024**3, "1.0 GiB"),
    ],
)
def test_human_bytes(size, expected):
    assert human_bytes(size) == expected


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("1992", [1992]),
        ("1992-1995", [1992, 1993, 1994, 1995]),
        ("1992-1994,2000", [1992, 1993, 1994, 2000]),
        (" 2000 , 1999 ", [1999, 2000]),
        ("2000,2000", [2000]),
    ],
)
def test_parse_year_spec(spec, expected):
    assert parse_year_spec(spec) == expected


@pytest.mark.parametrize("spec", ["", "abc", "1995-1992", "1992-", "-", "199x"])
def test_parse_year_spec_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        parse_year_spec(spec)


def test_parse_year_spec_validates_against_available_years():
    valid = range(1992, 2023)
    assert parse_year_spec("2022", valid=valid) == [2022]
    with pytest.raises(ValueError, match="not in dataset"):
        parse_year_spec("2023", valid=valid)


def test_format_table_aligns_columns():
    text = format_table([["a", "1"], ["bbb", "22"]], ["NAME", "N"])
    lines = text.splitlines()
    assert lines[0].startswith("NAME")
    assert len(lines) == 4
    assert "bbb" in lines[3]
