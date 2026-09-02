"""Chart tests: the country vocabulary, and refusing to draw a misleading blank.

Both failures these cover shipped once. Tunisia's words ("delegation",
"governorate") were hardcoded and printed onto every country's chart, and the
nested decomposition drew two empty axes captioned "theil_t undefined with
unlit pixels" for countries whose real problem was that GADM has no admin-2
layer for them at all.
"""

from __future__ import annotations

import pytest

pytest.importorskip("matplotlib")

from satimg import charts as C
from satimg import regions as R


def subnational_titles(iso3):
    return [title for level, _, title in C.facets(iso3) if level != "pixel"]


def test_facet_titles_use_the_countrys_own_words():
    assert subnational_titles("TUN") == [
        "Governorate, light density",
        "Delegation, light density",
    ]
    # Syria's admin-2 units are districts, not Tunisia's delegations.
    assert subnational_titles("SYR") == [
        "Governorate, light density",
        "District, light density",
    ]
    # Algeria's are communes, which is the error that started all of this.
    assert subnational_titles("DZA") == [
        "Province, light density",
        "Commune, light density",
    ]


def test_no_admin_2_country_gets_no_admin_2_facet():
    assert subnational_titles("LBY") == ["District, light density"]
    assert len(C.facets("LBY")) == 3
    assert len(C.facets("TUN")) == 4


def test_every_arab_league_country_has_facets():
    for iso3 in R.ARAB_LEAGUE:
        panels = C.facets(iso3)
        expected = 2 + len([lv for lv in R.available_levels(iso3) if lv >= 1])
        assert len(panels) == expected, iso3
        assert all(title.strip() for _, _, title in panels), iso3


def test_nested_labels_follow_the_country():
    assert C.nested_labels("TUN") == (
        "between governorates",
        "between delegations, within governorate",
        "within delegations",
    )
    assert C.nested_labels("SAU")[0] == "between provinces"


@pytest.mark.parametrize("iso3", ["LBY", "BHR", "COM", "KWT", "QAT"])
def test_decomposition_refuses_rather_than_drawing_an_empty_chart(iso3, tmp_path):
    # A blank chart captioned with the wrong reason is worse than no chart.
    with pytest.raises(C.NoNestedHierarchy, match="no admin-2 layer"):
        C.plot_decomposition([], tmp_path / "x.png", iso3=iso3)
    assert not (tmp_path / "x.png").exists()


def test_decomposition_is_attempted_where_admin_2_exists(tmp_path):
    # Empty rows still produce a file for a country that has the hierarchy;
    # only the missing-layer case is refused.
    out = C.plot_decomposition([], tmp_path / "y.png", iso3="TUN")
    assert out.exists()


# --------------------------------------------------------------------------- #
# pace dumbbell
# --------------------------------------------------------------------------- #
def pace_rows(**by_country):
    """Minimal trends rows: {iso3: (total, intensive)} for the full window."""
    rows = []
    for iso3, (total, intensive) in by_country.items():
        for measure, value in (("total", total), ("intensive", intensive)):
            rows.append(
                {
                    "iso3": iso3,
                    "measure": measure,
                    "window": "full",
                    "percent_per_year": value,
                    "monotone": "True",
                    "r_squared": 0.9,
                    "trajectory": "mixed",
                }
            )
    return rows


def test_pace_dumbbell_draws_from_trends_rows(tmp_path):
    out = C.plot_pace_dumbbell(
        pace_rows(BHR=(-4.09, -3.49), SOM=(-0.96, 1.11)), tmp_path / "pace.png"
    )
    assert out.exists() and out.stat().st_size > 0


def test_pace_dumbbell_refuses_an_empty_window_rather_than_drawing_nothing():
    with pytest.raises(ValueError, match="no country"):
        C.plot_pace_dumbbell(pace_rows(BHR=(-4.09, -3.49)), "x.png", window="viirs")


def test_pace_dumbbell_skips_a_country_missing_one_end(tmp_path):
    rows = pace_rows(BHR=(-4.09, -3.49), SOM=(-0.96, float("nan")))
    out = C.plot_pace_dumbbell(rows, tmp_path / "pace.png")
    assert out.exists()


def test_the_two_ends_take_different_hues_from_the_fixed_order():
    # Two series, so hue carries identity; both come from the same validated
    # order as SCOPE_COLORS rather than being invented here.
    assert C.PACE_COLORS["total"] != C.PACE_COLORS["intensive"]
    assert set(C.PACE_COLORS.values()) <= set(C.SCOPE_COLORS.values())


# --------------------------------------------------------------------------- #
# aridity bands
# --------------------------------------------------------------------------- #
def band_rows(*specs):
    """(desert_share, mean_dn_2022) pairs as trimmed vs_light rows."""
    return [
        {
            "iso3": "XXX",
            "gid": f"X.{i}_1",
            "name": f"unit {i}",
            "desert_share": share,
            "mean_dn_2022": value,
            "majority_arid": share > 0.5,
        }
        for i, (share, value) in enumerate(specs)
    ]


def test_aridity_bands_draws_from_vs_light_rows(tmp_path):
    rows = band_rows(
        (1.0, 0.5),
        (1.0, 3.7),
        (1.0, 40.0),
        (0.3, 0.02),
        (0.3, 3.8),
        (0.6, 12.0),
        (0.0, 0.001),
        (0.0, 14.1),
        (0.0, 30.0),
    )
    out = C.plot_aridity_bands(rows, tmp_path / "arid.png")
    assert out.exists() and out.stat().st_size > 0


def test_aridity_bands_refuses_an_empty_set_rather_than_drawing_an_empty_axis():
    with pytest.raises(ValueError, match="no units"):
        C.plot_aridity_bands([], "x.png")


def test_a_unit_with_no_light_at_all_still_draws(tmp_path):
    """One real unit has mean DN exactly 0, which a log axis cannot take."""
    rows = band_rows((1.0, 0.0), (1.0, 5.0), (0.4, 2.0), (0.0, 20.0))
    assert C.plot_aridity_bands(rows, tmp_path / "zero.png").exists()


def test_the_bands_partition_every_unit():
    """No unit may fall through the three predicates, and none may match two."""
    shares = [0.0, 0.0001, 0.5, 0.9999, 1.0]
    for share in shares:
        matched = [name for name, pred in C.ARIDITY_BANDS if pred(share)]
        assert len(matched) == 1, (share, matched)


def test_the_anomaly_ramp_is_ordinal_not_categorical():
    # Three steps of one hue: a unit's step says which cut it enters at, which
    # is ordered information. Distinct steps, and grey is not one of them.
    assert len(set(C.ANOMALY_TIERS)) == 3
    assert C.CONTEXT not in C.ANOMALY_TIERS


def test_the_swarm_offsets_are_symmetric_and_bounded():
    offsets = C._swarm([1.0] * 9, half_width=0.3)
    assert max(abs(o) for o in offsets) == pytest.approx(0.3)
    assert sum(offsets) == pytest.approx(0.0, abs=0.3)


def test_the_swarm_leaves_a_lone_point_on_its_row():
    assert C._swarm([2.0], half_width=0.3) == [0.0]
    assert C._swarm([], half_width=0.3) == []
