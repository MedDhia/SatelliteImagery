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


# --------------------------------------------------------------------------- #
# Theil indices
# --------------------------------------------------------------------------- #
from satimg.inequality import (  # noqa: E402
    THEIL_L,
    THEIL_T,
    decompose_theil,
    decompose_theil_by_ids,
    nested_theil_shares,
    theil,
    theil_l,
    theil_t,
)


def test_theil_is_zero_under_perfect_equality():
    assert theil_t([5, 5, 5, 5]) == pytest.approx(0.0)
    assert theil_l([5, 5, 5, 5]) == pytest.approx(0.0)


def test_theil_t_two_point_matches_the_definition():
    # x = [1,3], mu = 2: sum p_i (x_i/mu) ln(x_i/mu)
    expected = 0.5 * 0.5 * math.log(0.5) + 0.5 * 1.5 * math.log(1.5)
    assert theil_t([1, 3]) == pytest.approx(expected)


def test_theil_l_two_point_matches_the_definition():
    expected = 0.5 * math.log(2 / 1) + 0.5 * math.log(2 / 3)
    assert theil_l([1, 3]) == pytest.approx(expected)


@pytest.mark.parametrize("n", [2, 5, 20])
def test_theil_t_maximum_is_log_n(n):
    """One holder among n gives exactly ln(n) - the theoretical ceiling."""
    values = [0.0] * (n - 1) + [1.0]
    assert theil_t(values) == pytest.approx(math.log(n))


def test_theil_t_is_zero_safe_but_theil_l_is_not():
    """The dividing line that matters for pixel data: 86% of pixels are unlit."""
    assert theil_t([0, 1, 2]) == pytest.approx(theil_t([0.0, 1.0, 2.0]))
    assert not math.isnan(theil_t([0, 1, 2]))
    assert math.isnan(theil_l([0, 1, 2]))


def test_theil_scale_invariance():
    assert theil_t([1, 2, 3]) == pytest.approx(theil_t([10, 20, 30]))
    assert theil_l([1, 2, 3]) == pytest.approx(theil_l([10, 20, 30]))


def test_theil_all_zero_and_empty_are_nan():
    for fn in (theil_t, theil_l):
        assert math.isnan(fn([0, 0, 0]))
        assert math.isnan(fn([]))


def test_theil_rejects_negatives():
    for fn in (theil_t, theil_l):
        with pytest.raises(ValueError, match="negative"):
            fn([-1, 1])


def test_theil_weights_replicate_duplication():
    assert theil_t([1, 2], weights=[1, 2]) == pytest.approx(theil_t([1, 2, 2]))
    assert theil_l([1, 2], weights=[1, 2]) == pytest.approx(theil_l([1, 2, 2]))


def test_theil_weight_validation():
    with pytest.raises(ValueError, match="does not match"):
        theil_t([1, 2], weights=[1])
    with pytest.raises(ValueError, match="non-negative"):
        theil_t([1, 2], weights=[1, -1])


def test_theil_dispatch_rejects_unknown_measure():
    with pytest.raises(ValueError, match="unknown measure"):
        theil([1, 2], "gini")


# --------------------------------------------------------------------------- #
# decomposition
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("measure", [THEIL_T, THEIL_L])
def test_decomposition_identity_holds(measure):
    """total == between + within. This is the reason to use Theil at all."""
    rng = np.random.default_rng(3)
    for _ in range(5):
        x = rng.random(400) * 10 + 0.01
        groups = rng.integers(0, 6, 400)
        d = decompose_theil(x, groups, measure)
        assert d.residual() < 1e-12
        assert d.between + d.within == pytest.approx(d.total)
        assert d.between_share + d.within_share == pytest.approx(1.0)


def test_single_group_puts_everything_within():
    d = decompose_theil([1, 2, 3, 4], ["A"] * 4, THEIL_T)
    assert d.between == pytest.approx(0.0)
    assert d.within == pytest.approx(d.total)


def test_internally_uniform_groups_put_everything_between():
    d = decompose_theil([2, 2, 8, 8], ["A", "A", "B", "B"], THEIL_T)
    assert d.within == pytest.approx(0.0)
    assert d.between == pytest.approx(d.total)


def test_dark_group_drops_out_of_theil_t_but_breaks_theil_l():
    values = [0, 0, 1, 2, 3]
    groups = ["A", "A", "B", "B", "B"]
    t = decompose_theil(values, groups, THEIL_T)
    assert t.residual() < 1e-12
    dark = next(p for p in t.groups if p.key == "A")
    assert dark.value_share == pytest.approx(0.0)
    assert dark.within_contribution == pytest.approx(0.0)

    assert math.isnan(decompose_theil(values, groups, THEIL_L).between)


def test_decomposition_group_shares_sum_to_one():
    rng = np.random.default_rng(5)
    x = rng.random(200) * 5 + 0.1
    groups = rng.integers(0, 4, 200)
    d = decompose_theil(x, groups, THEIL_T)
    assert sum(p.population_share for p in d.groups) == pytest.approx(1.0)
    assert sum(p.value_share for p in d.groups) == pytest.approx(1.0)


def test_decomposition_rejects_mismatched_groups():
    with pytest.raises(ValueError, match="does not match"):
        decompose_theil([1, 2, 3], ["A", "B"], THEIL_T)


def test_decomposition_of_empty_is_nan():
    d = decompose_theil([], [], THEIL_T)
    assert math.isnan(d.total)
    assert d.groups == []


# --------------------------------------------------------------------------- #
# vectorised path must agree with the reference
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("measure", [THEIL_T, THEIL_L])
@pytest.mark.parametrize("with_zeros", [False, True])
def test_fast_decomposition_matches_reference(measure, with_zeros):
    rng = np.random.default_rng(9)
    x = rng.random(600) * 10 + 0.05
    if with_zeros:
        x[rng.integers(0, 600, 80)] = 0.0
    ids = rng.integers(1, 7, 600)

    ref = decompose_theil(x, ids, measure)
    fast = decompose_theil_by_ids(x, ids, 6, measure)

    def same(a, b):
        return (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b, rel=1e-12)

    assert same(ref.total, fast.total)
    assert same(ref.between, fast.between)
    assert same(ref.within, fast.within)
    assert len(ref.groups) == len(fast.groups)


def test_fast_decomposition_excludes_id_zero():
    """Id 0 means 'outside every unit' - e.g. a pixel beyond the country."""
    x = [1.0, 2.0, 3.0, 1000.0]
    ids = [1, 1, 2, 0]
    d = decompose_theil_by_ids(x, ids, 2, THEIL_T)
    assert sum(p.n for p in d.groups) == 3
    assert d.total == pytest.approx(theil_t([1.0, 2.0, 3.0]))


def test_fast_decomposition_of_all_outside_is_nan():
    d = decompose_theil_by_ids([1.0, 2.0], [0, 0], 2, THEIL_T)
    assert math.isnan(d.total)


# --------------------------------------------------------------------------- #
# nested split
# --------------------------------------------------------------------------- #
def test_nested_shares_sum_to_the_total():
    """Pixels < delegations < governorates: three parts, exactly additive."""
    values = [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]
    delegations = ["d1", "d1", "d2", "d2", "d3", "d3", "d4", "d4"]
    governorates = ["g1", "g1", "g1", "g1", "g2", "g2", "g2", "g2"]

    parts = nested_theil_shares(values, delegations, governorates, THEIL_T)
    reconstructed = (
        parts["between_outer"]
        + parts["between_inner_within_outer"]
        + parts["within_inner"]
    )
    assert reconstructed == pytest.approx(parts["total"])


def test_nested_middle_term_is_zero_when_inner_equals_outer():
    values = [1.0, 5.0, 2.0, 9.0]
    groups = ["g1", "g1", "g2", "g2"]
    parts = nested_theil_shares(values, groups, groups, THEIL_T)
    assert parts["between_inner_within_outer"] == pytest.approx(0.0)
