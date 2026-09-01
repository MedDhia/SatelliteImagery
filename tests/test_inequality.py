"""Gini tests against hand-computable cases - no raster or GIS involved."""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from satimg.inequality import gini, lorenz, share_of_top  # noqa: E402


def test_perfect_equality_is_zero():
    assert gini([5, 5, 5, 5]) == 0.0
    assert gini([1]) == 0.0


def test_maximum_inequality_is_one_minus_one_over_n():
    # With one holder among n, the Gini of a finite sample tops out below 1.
    for n in (2, 4, 10):
        values = [0.0] * (n - 1) + [100.0]
        assert gini(values) == pytest.approx(1 - 1 / n)


def test_known_value_for_a_simple_ramp():
    # [1,2,3,4]: mean 2.5, mean absolute difference 1.25 -> G = 1.25/(2*2.5) = 0.25
    assert gini([1, 2, 3, 4]) == pytest.approx(0.25)


def test_scale_invariance():
    assert gini([1, 2, 3, 4]) == pytest.approx(gini([10, 20, 30, 40]))


def test_order_invariance():
    assert gini([4, 1, 3, 2]) == pytest.approx(gini([1, 2, 3, 4]))


def test_all_zero_is_nan_not_zero():
    """An unlit region has undefined inequality; 0.0 would read as 'equal'."""
    assert math.isnan(gini([0, 0, 0]))


def test_empty_is_nan():
    assert math.isnan(gini([]))


def test_negative_values_rejected():
    with pytest.raises(ValueError, match="negative"):
        gini([-1, 2, 3])


def test_nan_input_rejected():
    with pytest.raises(ValueError, match="NaN"):
        gini([1.0, float("nan")])


def test_weights_replicate_duplicated_observations():
    """A weight of 2 must equal listing the observation twice."""
    assert gini([1, 2, 3, 4], weights=[1, 1, 1, 2]) == pytest.approx(
        gini([1, 2, 3, 4, 4])
    )


def test_unit_weights_match_the_unweighted_form():
    values = [3.0, 1.0, 7.0, 0.0]
    assert gini(values, weights=[1] * 4) == pytest.approx(gini(values))


def test_weighted_equality_is_zero():
    assert gini([5, 5, 5], weights=[3, 1, 9]) == pytest.approx(0.0)


def test_weight_length_must_match():
    with pytest.raises(ValueError, match="does not match"):
        gini([1, 2, 3], weights=[1, 1])


def test_negative_weights_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        gini([1, 2], weights=[1, -1])


def test_zero_total_weight_is_nan():
    assert math.isnan(gini([1, 2], weights=[0, 0]))


def test_lorenz_endpoints_and_monotonicity():
    pop, share = lorenz([1, 2, 3, 4])
    assert pop[0] == 0.0 and pop[-1] == pytest.approx(1.0)
    assert share[0] == 0.0 and share[-1] == pytest.approx(1.0)
    assert all(b >= a for a, b in zip(share, share[1:]))


def test_lorenz_of_equality_is_the_diagonal():
    pop, share = lorenz([2, 2, 2, 2])
    assert share == pytest.approx(pop)


def test_lorenz_of_empty_is_the_diagonal():
    assert lorenz([]) == ([0.0, 1.0], [0.0, 1.0])


def test_share_of_top():
    assert share_of_top([1] * 9 + [91], 0.1) == pytest.approx(0.91)
    assert share_of_top([5, 5, 5, 5], 0.5) == pytest.approx(0.5)
    assert math.isnan(share_of_top([0, 0], 0.5))


def test_share_of_top_rejects_bad_fraction():
    with pytest.raises(ValueError):
        share_of_top([1, 2], 0)


def test_gini_matches_the_brute_force_definition():
    """Cross-check the rank formula against mean-absolute-difference / 2*mean."""
    rng = np.random.default_rng(0)
    for _ in range(5):
        x = rng.random(40) * 10
        mad = np.abs(x[:, None] - x[None, :]).mean()
        assert gini(x) == pytest.approx(mad / (2 * x.mean()))
