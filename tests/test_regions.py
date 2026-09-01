"""Country scoping, desert definitions and the clipped-extract contract."""

from __future__ import annotations

import pytest

from satimg import regions as R


def test_country_levels_are_national_plus_two_subnational():
    assert R.COUNTRY_LEVELS == (0, 1, 2)
    assert R.LEVEL_TITLES[0] == "national"
    assert R.LEVEL_TITLES[1] == "governorate"
    assert R.LEVEL_TITLES[2] == "delegation"


def test_scope_keys_include_all_plus_both_desert_variants():
    assert R.scope_keys("TUN") == ["all", "narrow", "wide"]


def test_all_scope_excludes_nothing():
    assert R.excluded_gid1("TUN", "all") == frozenset()


def test_narrow_scope_is_the_saharan_trio():
    """Tataouine, Kebili, Tozeur - keyed on GID_1 so diacritics cannot break it."""
    assert R.excluded_gid1("TUN", "narrow") == frozenset(
        {"TUN.21_1", "TUN.10_1", "TUN.22_1"}
    )


def test_wide_scope_is_a_superset_of_narrow():
    narrow = R.excluded_gid1("TUN", "narrow")
    wide = R.excluded_gid1("TUN", "wide")
    assert narrow < wide
    assert len(wide) == 6


def test_unknown_scope_is_rejected_with_the_known_ones_listed():
    with pytest.raises(ValueError, match="known: all, narrow, wide"):
        R.excluded_gid1("TUN", "sahara")


def test_country_without_desert_definitions_still_has_the_all_scope():
    assert R.scope_keys("FRA") == ["all"]
    assert R.excluded_gid1("FRA", "all") == frozenset()


def test_check_level_for_country_rejects_deeper_levels():
    assert R.check_level_for_country(2) == 2
    with pytest.raises(ValueError, match="supports levels"):
        R.check_level_for_country(3)


def test_id_fields_per_level():
    assert R.id_fields(0) == ("GID_0", "COUNTRY")
    assert R.id_fields(1) == ("GID_1", "NAME_1")
    assert R.id_fields(2) == ("GID_2", "NAME_2")


def test_analysis_tolerance_is_exact_geometry():
    """Simplifying breaks the tiling between units and leaks pixels."""
    assert R.ANALYSIS_TOLERANCE_M == 0.0


def test_parent_gid1_is_none_at_national_level():
    assert R.parent_gid1(None, 0) is None


def test_parent_gid1_reads_the_column():
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Point

    frame = gpd.GeoDataFrame(
        {"GID_1": ["TUN.21_1", "TUN.1_1"]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:8857",
    )
    assert R.parent_gid1(frame, 2) == ["TUN.21_1", "TUN.1_1"]


def test_parent_gid1_errors_without_the_column():
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Point

    frame = gpd.GeoDataFrame({"X": [1]}, geometry=[Point(0, 0)], crs="EPSG:8857")
    with pytest.raises(ValueError, match="GID_1"):
        R.parent_gid1(frame, 2)
