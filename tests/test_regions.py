"""Country scoping, desert definitions and the clipped-extract contract."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

import pytest

from satimg import regions as R


def test_country_levels_are_national_plus_two_subnational():
    assert R.COUNTRY_LEVELS == (0, 1, 2)
    assert R.LEVEL_TITLES[0] == "national"
    assert R.LEVEL_TITLES[1] == "governorate"
    assert R.LEVEL_TITLES[2] == "delegation"


def test_scope_keys_are_all_plus_hand_picked_plus_derived():
    # Tunisia's derived `dark` duplicates its hand-picked `narrow` exactly, so
    # it is dropped rather than doubling every downstream series.
    assert R.scope_keys("TUN") == ["all", "narrow", "wide", "dark_wide"]
    assert R.scope_keys("DZA") == ["all", "dark", "dark_wide"]


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
    with pytest.raises(ValueError, match="known: all, narrow, wide, dark_wide"):
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


# --------------------------------------------------------------------------- #
# multi-country support
# --------------------------------------------------------------------------- #
def test_maghreb_is_the_arab_maghreb_union():
    assert set(R.MAGHREB) == {"MAR", "DZA", "TUN", "LBY", "MRT"}


def test_arab_league_has_22_members_starting_with_the_maghreb():
    assert len(R.ARAB_LEAGUE) == 22
    assert len(set(R.ARAB_LEAGUE)) == 22
    # Maghreb first, so the earlier work keeps its place in every index.
    assert R.ARAB_LEAGUE[: len(R.MAGHREB)] == R.MAGHREB


def test_every_arab_league_country_has_level_names():
    for iso3 in R.ARAB_LEAGUE:
        assert iso3 in R.COUNTRY_LEVEL_TITLES, iso3
        for level in R.available_levels(iso3):
            assert R.level_title(iso3, level).strip(), (iso3, level)


def test_djibouti_admin_2_falls_back_rather_than_inventing_a_word():
    # GADM records ENGTYPE_2 as literally "NA" for Djibouti. A plausible-
    # sounding invention would be worse than admitting we do not know.
    assert R.level_title("DJI", 2) == R.GENERIC_LEVEL_TITLES[2]
    assert 2 not in R.COUNTRY_LEVEL_TITLES["DJI"]


def test_countries_without_gadm_admin_2():
    # Checked against the GeoPackage, not assumed.
    assert set(R.LEVELS_AVAILABLE) == {"LBY", "BHR", "COM", "KWT", "QAT"}


def test_small_countries_get_no_derived_scope():
    # Fewer than eight admin-1 units would remain, so the guard rules them out
    # rather than producing a split over a handful of units.
    for iso3 in ("ARE", "QAT", "BHR", "KWT", "LBN", "PSE", "DJI", "COM"):
        assert R.scope_keys(iso3) == ["all"], iso3


def test_refuted_claims_are_corrected_not_quietly_dropped():
    """The rationales once asserted these units were dark for human reasons.

    Measuring them against the Global Aridity Index refuted that: Aleppo is 70%
    arid, Ninawa 58%, Raymah 97%, Nalut 100%. The rationales must now say so -
    a silent rewrite would lose the fact that the earlier reading was wrong.
    """
    for iso3, key, must_mention in (
        ("SYR", "dark_wide", "70% arid"),
        ("IRQ", "dark_wide", "58%"),
        ("YEM", "dark", "97% arid"),
        ("LBY", "dark_wide", "100% arid"),
        ("SOM", "dark", "96% arid"),
    ):
        rationale = R.DESERT_SCOPES[iso3][key].rationale
        assert must_mention in rationale, (iso3, key)


def test_the_module_records_that_the_eyeball_reading_was_wrong():
    doc = R.__doc__ or ""
    import satimg.regions as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    # The surviving, measured findings - not the refuted prose.
    assert "94%" in source and "73% base rate" in source
    assert "Darfur" in source
    assert doc


# --------------------------------------------------------------------------- #
# the pool against the analysed set
# --------------------------------------------------------------------------- #
def test_countries_is_a_strict_superset_of_the_pool():
    assert set(R.ARAB_LEAGUE) < set(R.COUNTRIES)
    assert len(R.COUNTRIES) == len(set(R.COUNTRIES))
    # The pool keeps its exact membership: everything published about "the 22"
    # stays a statement about 22 countries.
    assert len(R.ARAB_LEAGUE) == 22


def test_the_pool_leads_the_analysed_set_so_indexes_keep_their_order():
    assert R.COUNTRIES[: len(R.ARAB_LEAGUE)] == R.ARAB_LEAGUE


def test_thailand_is_analysed_but_not_pooled():
    assert "THA" in R.COUNTRIES
    assert "THA" not in R.ARAB_LEAGUE


def test_the_pooled_analyses_default_to_the_pool_not_the_analysed_set():
    """The whole point of the split, asserted where it can actually regress.

    `aridity.vs_light` cuts `dark_2022` at the cross-country *median* of mean
    DN. Defaulting it to COUNTRIES would move that median and silently rewrite
    `dark_2022`, `cell` and the 6/13/23 nesting for all 317 published units.

    Checked on the resolved default argument rather than the source text, so
    renaming a constant cannot make this pass vacuously. The behavioural
    counterpart - that a fresh join still returns exactly the pool's units even
    with Thailand on disk - lives in tests/test_aridity.py.
    """
    from satimg import aridity as A
    from satimg import trends as T

    for func in (A.vs_light, T.build_rows):
        default = inspect.signature(func).parameters["countries"].default
        assert default is None, func.__qualname__

    # Both resolve `countries=None` to the pool. Exercised with a directory
    # holding nothing, so this asserts the country list and touches no data.
    with tempfile.TemporaryDirectory() as empty:
        assert A.vs_light(empty) == []
        assert T.build_rows(empty) == []


def test_thailand_level_names_come_from_gadm_engtype():
    # GADM 4.1: ENGTYPE_1 is uniformly "Province" (77 units); ENGTYPE_2 is
    # "District" for 845 of 928, so the majority rule gives "district".
    assert R.level_title("THA", 1) == "province"
    assert R.level_title("THA", 2) == "district"


def test_thailand_has_no_exclusion_scope_and_that_is_deliberate():
    """The low-light rule reads its break as desert or conflict.

    Neither transfers to a humid country, so Thailand ships with `all` only -
    the state eight Arab League members are already in. Inventing a scope and
    letting the existing vocabulary label it would repeat the desert-prose
    error this repository has already had to retract.
    """
    assert list(R.scope_keys("THA")) == [R.SCOPE_ALL]
    assert R.desert_scopes("THA") == {}
