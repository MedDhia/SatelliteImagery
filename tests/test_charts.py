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
