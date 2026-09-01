"""Country scoping, desert definitions and the clipped-extract contract."""

from __future__ import annotations

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


def test_conflict_affected_scopes_say_so():
    # Syria's and Iraq's cuts select war damage, not aridity. If a future edit
    # rewrites these as desert sets, this fails.
    assert "conflict" in R.DESERT_SCOPES["SYR"]["dark_wide"].rationale
    assert "war damage" in R.DESERT_SCOPES["IRQ"]["dark_wide"].rationale
    assert "poverty" in R.DESERT_SCOPES["SOM"]["dark"].rationale


@pytest.mark.parametrize(
    "iso3,level,expected",
    [
        ("TUN", 1, "governorate"),
        ("TUN", 2, "delegation"),
        ("DZA", 1, "province"),  # GADM's own ENGTYPE_1, not a guess
        ("DZA", 2, "commune"),  # NOT "daira" - GADM labels these communes
        ("MRT", 2, "department"),
        ("LBY", 1, "district"),
        ("FRA", 1, "admin-1 unit"),  # unmapped country falls back
        ("LBY", 2, "admin-2 unit"),  # level Libya does not have
    ],
)
def test_level_title_is_country_aware(iso3, level, expected):
    # "governorate" on an Algerian wilaya would be a wrong word on 93 maps.
    assert R.level_title(iso3, level) == expected


def test_libya_has_no_admin_2_in_gadm():
    assert R.available_levels("LBY") == (0, 1)
    assert not R.has_level("LBY", 2)
    assert R.has_level("DZA", 2)


def test_resolve_levels_drops_what_gadm_lacks():
    assert R.resolve_levels("LBY", (0, 1, 2)) == ((0, 1), (2,))
    assert R.resolve_levels("DZA", (0, 1, 2)) == ((0, 1, 2), ())


def test_resolve_levels_raises_when_nothing_survives():
    with pytest.raises(ValueError, match="GADM provides"):
        R.resolve_levels("LBY", (2,))


def test_every_maghreb_country_has_a_usable_scope_set():
    for iso3 in R.MAGHREB:
        keys = R.scope_keys(iso3)
        assert keys[0] == "all"
        assert len(keys) >= 2, iso3


def test_derived_scopes_are_marked_as_derived():
    # A reader must be able to tell "we judged this Saharan" from "the light
    # data put it below the break".
    assert R.DESERT_SCOPES["DZA"]["dark"].derived is True
    assert R.DESERT_SCOPES["TUN"]["narrow"].derived is False


def test_the_low_light_rule_reproduces_tunisias_hand_picked_trio():
    """The validity check for the derived rule, asserted rather than left in prose."""
    assert (
        R.DERIVED_SCOPES["TUN"]["dark"].gid1 == R.TUNISIA_DESERT_SCOPES["narrow"].gid1
    )


def test_the_derived_wide_scope_is_not_tunisias_hand_picked_wide():
    # It takes Siliana where the geographic definition takes Gafsa; the module
    # says so, and a future edit that quietly "fixes" this should fail here.
    derived = R.DERIVED_SCOPES["TUN"]["dark_wide"].gid1
    assert derived != R.TUNISIA_DESERT_SCOPES["wide"].gid1
    assert "TUN.19_1" in derived  # Siliana
    assert "TUN.6_1" not in derived  # Gafsa


def test_derived_scopes_nest_and_name_real_units():
    for iso3, scopes in R.DERIVED_SCOPES.items():
        if "dark" in scopes and "dark_wide" in scopes:
            assert scopes["dark"].gid1 < scopes["dark_wide"].gid1, iso3
        for scope in scopes.values():
            assert scope.gid1, iso3
            assert all(gid.startswith(iso3 + ".") for gid in scope.gid1), iso3
            assert scope.rationale.strip(), iso3
