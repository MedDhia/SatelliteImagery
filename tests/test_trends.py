"""Trend tests: the fit itself, the traps in the data, and the four anchors.

Everything here is synthetic except the anchor test, which reads the committed
CSVs under ``results/``. No rasters, no GADM, no network.

Each case guards a failure that would produce a plausible-looking wrong number
rather than a crash: a flat line reported as a perfect trend, a sign change
averaged into a headline rate, a zero silently turned into a large negative
log, or a rising series handed a positive "half-life".
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from satimg import trends as T

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"

YEARS = list(range(1992, 2023))


def exponential(rate_percent: float, start: float = 1.0, years=YEARS):
    """A series decaying at exactly ``rate_percent`` per year."""
    k = rate_percent / 100.0
    return [start * math.exp(k * (year - years[0])) for year in years]


# --------------------------------------------------------------------------- #
# the fit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("planted", [-4.0, -1.25, -0.1, 0.0, 2.5])
def test_a_planted_exponential_comes_back_at_its_own_rate(planted):
    rate = T.log_linear_rate(YEARS, exponential(planted))
    assert rate.percent_per_year == pytest.approx(planted, abs=1e-9)
    assert rate.n_years == len(YEARS)
    assert rate.first_year == 1992
    assert rate.last_year == 2022


def test_a_flat_series_is_rate_zero_with_r_squared_undefined_not_one():
    """R-squared of a flat line is 0/0. Reporting 1.0 would call it a trend."""
    rate = T.log_linear_rate(YEARS, [3.0] * len(YEARS))
    assert rate.percent_per_year == pytest.approx(0.0)
    assert math.isnan(rate.r_squared)
    assert not rate.is_monotone
    assert rate.direction == "flat"


def test_a_sign_change_scores_low_enough_that_it_is_not_called_monotone():
    """Up then down. A single slope must not be presented as the story."""
    values = [1.0 + 0.4 * math.sin((year - 1992) / 30 * math.pi) for year in YEARS]
    rate = T.log_linear_rate(YEARS, values)
    assert rate.r_squared < T.MONOTONE_R2
    assert not rate.is_monotone


def test_a_clean_exponential_is_monotone():
    assert T.log_linear_rate(YEARS, exponential(-2.0)).is_monotone


def test_zero_and_nan_are_dropped_rather_than_logged_or_clamped():
    """``lit_share`` reaches 0 and Theil L is nan; neither is a rate of -inf."""
    values = exponential(-2.0)
    values[0] = 0.0
    values[5] = float("nan")
    values[9] = -1.0
    rate = T.log_linear_rate(YEARS, values)
    assert rate.n_years == len(YEARS) - 3
    assert rate.first_year == 1993
    assert rate.percent_per_year == pytest.approx(-2.0, abs=1e-9)


def test_too_few_usable_points_is_undefined_not_a_two_point_slope():
    rate = T.log_linear_rate(YEARS, [0.0] * (len(YEARS) - 3) + [1.0, 2.0, 4.0])
    assert rate.n_years == 0
    assert math.isnan(rate.percent_per_year)
    assert rate.direction == "undefined"


# --------------------------------------------------------------------------- #
# half-life
# --------------------------------------------------------------------------- #
def test_half_life_matches_the_planted_rate():
    rate = T.log_linear_rate(YEARS, exponential(-math.log(2) * 100 / 10))
    assert rate.half_life_years == pytest.approx(10.0, abs=1e-9)


def test_a_rising_series_has_no_half_life_rather_than_a_negative_one():
    """A negative number here would be read as a half-life. nan cannot be."""
    rate = T.log_linear_rate(YEARS, exponential(+1.5))
    assert math.isnan(rate.half_life_years)
    assert rate.direction == "rising"


def test_an_undefined_fit_has_no_half_life():
    assert math.isnan(T.UNDEFINED.half_life_years)


# --------------------------------------------------------------------------- #
# windows
# --------------------------------------------------------------------------- #
def test_the_windows_split_at_the_sensor_handover_and_do_not_overlap():
    series = dict(zip(YEARS, exponential(-2.0)))
    spans = {
        name: T.window_rate(series, first, last) for name, first, last in T.WINDOWS
    }
    assert spans["dmsp"].last_year == T.BREAK_YEAR - 1
    assert spans["viirs"].first_year == T.BREAK_YEAR
    assert spans["dmsp"].n_years + spans["viirs"].n_years == spans["full"].n_years


def test_a_window_with_a_different_slope_is_reported_as_that_slope():
    """The whole point of the split: a break must not be averaged away."""
    series = {}
    series.update(dict(zip(YEARS[:22], exponential(-1.0, years=YEARS[:22]))))
    series.update(dict(zip(YEARS[22:], exponential(-6.0, years=YEARS[22:]))))
    assert T.window_rate(series, None, 2013).percent_per_year == pytest.approx(-1.0)
    assert T.window_rate(series, 2014, None).percent_per_year == pytest.approx(-6.0)


# --------------------------------------------------------------------------- #
# typology
# --------------------------------------------------------------------------- #
def rate(percent: float, r_squared: float = 0.9) -> T.Rate:
    return T.Rate(percent, r_squared, len(YEARS), YEARS[0], YEARS[-1])


def test_a_falling_total_with_a_rising_lit_only_margin_is_not_convergence():
    label, why = T.classify_trajectory(rate(-1.0), rate(+1.1), rate(+7.1))
    assert label == T.EXTENSIVE_SPREADER
    assert "new ground" in why


def test_a_fully_lit_country_falling_on_both_margins_is_convergence():
    label, _ = T.classify_trajectory(rate(-4.09), rate(-3.49), rate(+0.10))
    assert label == T.INTENSIVE_CONVERGER


def test_shrinking_lit_area_is_its_own_regime():
    label, why = T.classify_trajectory(rate(+1.44), rate(-0.05), rate(-2.43))
    assert label == T.DISRUPTED
    assert "shrinking" in why


def test_a_country_that_barely_moves_is_not_given_a_direction():
    label, _ = T.classify_trajectory(rate(-0.05), rate(+0.4), rate(+0.5))
    assert label == T.FLAT_LABEL


def test_an_unusable_total_is_undefined_rather_than_classified():
    label, _ = T.classify_trajectory(T.UNDEFINED, rate(-1.0), rate(+1.0))
    assert label == "undefined"


def test_the_thresholds_are_constants_so_the_table_can_be_argued_with():
    assert 0 < T.RISING < T.FLAT
    assert 0 < T.MONOTONE_R2 < 1


# --------------------------------------------------------------------------- #
# reading the committed CSVs
# --------------------------------------------------------------------------- #
def test_series_from_rows_takes_pixel_level_all_units_only():
    rows = [
        {
            "level": "pixel",
            "scope": "all",
            "zeros": "zeros_included",
            "year": "2000",
            "theil_t": "0.5",
            "lit_share": "0.1",
        },
        {
            "level": "pixel",
            "scope": "all",
            "zeros": "lit_only",
            "year": "2000",
            "theil_t": "0.2",
            "lit_share": "1.0",
        },
        {
            "level": "adm1",
            "scope": "all",
            "zeros": "zeros_included",
            "year": "2000",
            "theil_t": "9.9",
            "lit_share": "0.9",
        },
        {
            "level": "pixel",
            "scope": "narrow",
            "zeros": "zeros_included",
            "year": "2000",
            "theil_t": "8.8",
            "lit_share": "0.8",
        },
    ]
    series = T.series_from_rows(rows)
    assert series["total"] == {2000: 0.5}
    assert series["intensive"] == {2000: 0.2}
    assert series["extensive"] == {2000: 0.1}


def test_between_share_reads_the_named_grouping_only():
    rows = [
        {
            "measure": "theil_t",
            "grouping": "governorate",
            "scope": "all",
            "zeros": "zeros_included",
            "year": "2000",
            "between_share": "0.4",
        },
        {
            "measure": "theil_t",
            "grouping": "delegation",
            "scope": "all",
            "zeros": "zeros_included",
            "year": "2000",
            "between_share": "0.7",
        },
        {
            "measure": "theil_l",
            "grouping": "governorate",
            "scope": "all",
            "zeros": "zeros_included",
            "year": "2001",
            "between_share": "0.9",
        },
    ]
    assert T.between_share_series(rows, "governorate") == {2000: 0.4}


# --------------------------------------------------------------------------- #
# against the committed results
# --------------------------------------------------------------------------- #
pytestmark_results = pytest.mark.skipif(
    not (RESULTS / "TUN" / "TUN_inequality_series.csv").exists(),
    reason="results/ not present",
)


@pytest.fixture(scope="module")
def published():
    rows = T.build_rows(RESULTS)
    if not rows:
        pytest.skip("results/ not present")
    return rows


#: Computed while scoping this analysis, before the module existed. A
#: disagreement means the module and the scoping arithmetic differ, and one of
#: them is wrong.
ANCHORS = {
    "BHR": (-4.09, -3.49, +0.10),
    "SOM": (-0.96, +1.11, +7.10),
    "MAR": (-2.26, -0.50, +5.30),
    "SYR": (+1.44, -0.05, -2.43),
}


@pytest.mark.parametrize("iso3", sorted(ANCHORS))
def test_the_scoping_anchors_reproduce(published, iso3):
    got = tuple(
        float(T.full_window(published, measure)[iso3]["percent_per_year"])
        for measure in ("total", "intensive", "extensive")
    )
    assert got == pytest.approx(ANCHORS[iso3], abs=0.005)


def test_every_arab_league_country_is_present_with_every_window(published):
    from satimg import regions as R

    seen = {row["iso3"] for row in published}
    assert seen == set(R.ARAB_LEAGUE)
    windows = {name for name, _, _ in T.WINDOWS}
    for iso3 in R.ARAB_LEAGUE:
        for measure, _ in T.MEASURES:
            got = {
                row["window"]
                for row in published
                if row["iso3"] == iso3 and row["measure"] == measure
            }
            assert got == windows, f"{iso3}/{measure} is missing a window"


#: Libya's Theil T wanders between 3.42 and 3.73 for thirty years without a
#: trend: the fit is +0.006 %/yr at R-squared 0.0004, while its endpoints happen
#: to land 0.19 lower than they started. Endpoints and slope disagree there
#: because there is no slope to agree with - which is the case the R-squared
#: flag exists to catch, so the exception is named rather than smoothed over.
NO_TREND = "LBY"


def test_the_fitted_sign_matches_the_endpoints_wherever_there_is_a_trend(published):
    import csv

    from satimg import regions as R

    rates = T.full_window(published, "total")
    disagree = []
    for iso3 in R.ARAB_LEAGUE:
        with open(
            RESULTS / iso3 / f"{iso3}_inequality_series.csv", encoding="utf-8"
        ) as handle:
            series = T.series_from_rows(list(csv.DictReader(handle)))["total"]
        endpoints = series[2022] - series[1992]
        fitted = float(rates[iso3]["percent_per_year"])
        if (endpoints < 0) != (fitted < 0):
            disagree.append(iso3)
    assert disagree == [NO_TREND]


def test_the_one_country_where_they_disagree_is_flagged_as_having_no_trend(published):
    """Otherwise the exception above would be an unadvertised wrong number."""
    row = T.full_window(published, "total")[NO_TREND]
    assert float(row["r_squared"]) < T.MONOTONE_R2
    assert str(row["monotone"]) == "False"
    assert row["direction"] == "flat"
    assert row["trajectory"] == T.FLAT_LABEL


def test_syria_is_the_only_country_whose_inequality_rises(published):
    directions = {
        iso3: row["direction"]
        for iso3, row in T.full_window(published, "total").items()
    }
    assert sorted(i for i, d in directions.items() if d == "rising") == ["SYR"]
    assert sorted(i for i, d in directions.items() if d == "flat") == [NO_TREND]
    assert sum(d == "falling" for d in directions.values()) == 20


def test_the_non_monotone_countries_are_named_not_given_headline_rates(published):
    """Four series a single slope does not describe. They are the caveat."""
    rows = T.full_window(published, "total")
    flagged = sorted(i for i, r in rows.items() if str(r["monotone"]) == "False")
    assert flagged == ["COM", "LBY", "SYR", "YEM"]


def test_the_post_2014_acceleration_is_near_universal(published):
    """18 of 22 at exactly the sensor boundary - the instrument, not history."""
    eras = T.era_comparison(published)
    assert len(eras) == 22
    faster = [iso3 for iso3, dmsp, viirs in eras if viirs < dmsp]
    assert len(faster) == 18


def test_the_committed_table_matches_a_fresh_fit(published):
    """`results/trends_by_country.csv` must not drift from the module."""
    import csv

    path = RESULTS / T.TRENDS_TABLE
    if not path.exists():
        pytest.skip("trends table not published yet")
    with open(path, encoding="utf-8") as handle:
        committed = list(csv.DictReader(handle))
    assert len(committed) == len(published)
    for row, fresh in zip(committed, published):
        assert row["iso3"] == fresh["iso3"]
        assert row["measure"] == fresh["measure"]
        assert row["window"] == fresh["window"]
        assert row["trajectory"] == fresh["trajectory"]
        assert float(row["percent_per_year"]) == pytest.approx(
            float(fresh["percent_per_year"]), nan_ok=True
        )
