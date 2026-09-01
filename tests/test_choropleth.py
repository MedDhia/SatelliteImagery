"""Choropleth tests: the per-unit value maths and the class scheme."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("matplotlib")
gpd = pytest.importorskip("geopandas")
np = pytest.importorskip("numpy")
from shapely.geometry import box  # noqa: E402

from satimg import choropleth as C  # noqa: E402


@pytest.fixture
def units():
    return gpd.GeoDataFrame(
        {"GID_1": ["A", "B", "C"], "NAME_1": ["a", "b", "c"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
        crs="EPSG:8857",
    )


#: Two units: one bright and small, one dim and large.
ROWS = [
    {
        "year": 2000,
        "gid": "A",
        "pixels": 10,
        "sum_of_lights": 100.0,
        "mean_dn": 10.0,
        "area_km2": 10.0,
        "density_sol_per_km2": 10.0,
    },
    {
        "year": 2000,
        "gid": "B",
        "pixels": 90,
        "sum_of_lights": 90.0,
        "mean_dn": 1.0,
        "area_km2": 90.0,
        "density_sol_per_km2": 1.0,
    },
    {
        "year": 2001,
        "gid": "A",
        "pixels": 10,
        "sum_of_lights": 200.0,
        "mean_dn": 20.0,
        "area_km2": 10.0,
        "density_sol_per_km2": 20.0,
    },
    {
        "year": 2001,
        "gid": "B",
        "pixels": 90,
        "sum_of_lights": 180.0,
        "mean_dn": 2.0,
        "area_km2": 90.0,
        "density_sol_per_km2": 2.0,
    },
]


def test_absolute_values_are_the_raw_field():
    values, national = C.unit_values(ROWS, 2000, scale=C.ABSOLUTE)
    assert values == {"A": 10.0, "B": 1.0}
    # 190 light over 100 pixels
    assert national == pytest.approx(1.9)


def test_national_mean_is_light_weighted_not_a_mean_of_means():
    """A one-pixel unit must not weigh the same as a 90-pixel one."""
    _, national = C.unit_values(ROWS, 2000, scale=C.ABSOLUTE)
    assert national == pytest.approx((100.0 + 90.0) / (10 + 90))
    naive = (10.0 + 1.0) / 2  # mean of the per-unit means
    assert not math.isclose(national, naive)


def test_relative_values_divide_by_that_years_national_mean():
    values, national = C.unit_values(ROWS, 2000, scale=C.RELATIVE)
    assert values["A"] == pytest.approx(10.0 / national)
    assert values["B"] == pytest.approx(1.0 / national)


def test_relative_divides_growth_out():
    """Both units double; their relative standing must not move."""
    first, _ = C.unit_values(ROWS, 2000, scale=C.RELATIVE)
    second, _ = C.unit_values(ROWS, 2001, scale=C.RELATIVE)
    assert first["A"] == pytest.approx(second["A"])
    assert first["B"] == pytest.approx(second["B"])


def test_absolute_does_not_divide_growth_out():
    first, _ = C.unit_values(ROWS, 2000, scale=C.ABSOLUTE)
    second, _ = C.unit_values(ROWS, 2001, scale=C.ABSOLUTE)
    assert second["A"] == pytest.approx(2 * first["A"])


def test_unknown_year_returns_empty():
    values, national = C.unit_values(ROWS, 1899)
    assert values == {}
    assert math.isnan(national)


def test_alternative_field_is_honoured():
    values, _ = C.unit_values(ROWS, 2000, field="density_sol_per_km2")
    assert values["A"] == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# class scheme
# --------------------------------------------------------------------------- #
def test_breaks_are_ascending_and_fixed():
    for breaks in (C.DN_BREAKS, C.RATIO_BREAKS):
        assert list(breaks) == sorted(breaks)
        assert len(breaks) >= 5


def test_ratio_breaks_straddle_one():
    """The crossover at the national mean must fall on a class edge."""
    below = [b for b in C.RATIO_BREAKS if b < 1]
    above = [b for b in C.RATIO_BREAKS if b > 1]
    assert below and above
    assert max(below) == pytest.approx(0.8)
    assert min(above) == pytest.approx(1.25)


def test_ramp_runs_white_to_dark_red():
    assert C.WHITE_YLORRD[0] == "#ffffff"
    assert C.WHITE_YLORRD[-1] == "#800026"


def test_ramp_lightness_is_monotonically_decreasing():
    """White to red must never brighten mid-ramp, or classes stop ordering."""
    from matplotlib.colors import to_rgb

    def luminance(hex_color):
        c = np.array(to_rgb(hex_color))
        lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return float(np.dot(lin, [0.2126, 0.7152, 0.0722]))

    lums = [luminance(c) for c in C.WHITE_YLORRD]
    assert all(b <= a + 1e-9 for a, b in zip(lums, lums[1:])), lums


def test_edges_are_not_white_because_the_lowest_class_is():
    """A white unit on a white page needs a visible outline."""
    assert C.EDGE != "#ffffff"
    assert C.WHITE_YLORRD[0] == "#ffffff"


def test_both_scales_share_one_ramp():
    _, cmap_a, breaks_a = C._norm_and_cmap(C.ABSOLUTE)
    _, cmap_r, breaks_r = C._norm_and_cmap(C.RELATIVE)
    assert cmap_a.name == cmap_r.name
    assert breaks_a != breaks_r


def test_unknown_scale_rejected():
    with pytest.raises(ValueError, match="scale must be"):
        C._norm_and_cmap("diverging")


def test_relative_tick_labels_read_as_multiples():
    _, _, breaks = C._norm_and_cmap(C.RELATIVE)
    labels = C._tick_labels(C.RELATIVE, breaks)
    assert "1/8" in labels
    assert "2×" in labels
    assert labels[-1] == ""  # the open-ended top class carries no number


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scale", [C.ABSOLUTE, C.RELATIVE])
def test_render_writes_a_png(units, scale, tmp_path):
    out = C.render_choropleth(
        units,
        {"A": 5.0, "B": 20.0, "C": 0.2},
        tmp_path / f"{scale}.png",
        id_field="GID_1",
        scale=scale,
        year=2000,
        level_label="governorate",
        iso3="XXX",
        dpi=60,
    )
    assert out.exists()
    with open(out, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


def test_render_handles_units_with_no_data(units, tmp_path):
    """A missing unit must be drawn grey, not fall into the lowest class."""
    out = C.render_choropleth(
        units,
        {"A": 5.0},  # B and C absent
        tmp_path / "missing.png",
        id_field="GID_1",
        dpi=60,
    )
    assert out.exists()


def test_panel_writes_a_png(units, tmp_path):
    out = C.render_choropleth_panel(
        units,
        {1992: {"A": 1.0, "B": 5.0, "C": 20.0}, 1993: {"A": 2.0, "B": 6.0, "C": 25.0}},
        tmp_path / "panel.png",
        id_field="GID_1",
        level_label="governorate",
        iso3="XXX",
        columns=2,
        dpi=60,
    )
    assert out.exists()


def test_panel_requires_at_least_one_year(units, tmp_path):
    with pytest.raises(ValueError, match="at least one year"):
        C.render_choropleth_panel(units, {}, tmp_path / "x.png", id_field="GID_1")
