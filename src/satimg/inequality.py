"""Inequality measures for nighttime-light distributions.

Kept free of raster and GIS dependencies so it can be tested against
hand-computed values, and reused for any distribution - pixels, governorates
or delegations.

A note on what a Gini of DN means: LRCC-DVNL digital numbers are a *relative*
brightness index on a 0-63 scale, not radiance and not income. A Gini computed
over them describes how concentrated observed light is; it is not a Gini of
output or welfare, and it should not be reported as one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


def gini(values: Sequence[float], weights: Optional[Sequence[float]] = None) -> float:
    """Gini coefficient of a non-negative distribution.

    Uses the sorted-rank form ``G = (2 * sum(i * x_i)) / (n * sum(x)) - (n+1)/n``
    with ``x`` sorted ascending and ``i`` one-based, which is exact for a finite
    sample rather than an approximation from a binned Lorenz curve.

    Returns ``nan`` rather than 0.0 for an empty input or an all-zero
    distribution: with no light anywhere, inequality is undefined, and
    reporting 0.0 would read as "perfectly equal" in a results table.

    ``weights`` gives a frequency weight per observation (e.g. area), for the
    area-weighted variant.
    """
    import numpy as np

    x = np.asarray(values, dtype="float64").ravel()
    if x.size == 0:
        return float("nan")
    if np.isnan(x).any():
        raise ValueError("gini() received NaN values")
    if (x < 0).any():
        raise ValueError("gini() is undefined for negative values")

    if weights is None:
        x = np.sort(x)
        total = x.sum()
        if total <= 0:
            return float("nan")
        n = x.size
        index = np.arange(1, n + 1, dtype="float64")
        return float((2.0 * (index * x).sum()) / (n * total) - (n + 1.0) / n)

    w = np.asarray(weights, dtype="float64").ravel()
    if w.size != x.size:
        raise ValueError(
            f"weights length {w.size} does not match values length {x.size}"
        )
    if (w < 0).any():
        raise ValueError("gini() weights must be non-negative")
    if w.sum() <= 0:
        return float("nan")

    order = np.argsort(x)
    x, w = x[order], w[order]
    total = (x * w).sum()
    if total <= 0:
        return float("nan")

    # Weighted Gini via the covariance/Lorenz form: cumulative population share
    # at the midpoint of each observation's weight band.
    cum_w = np.cumsum(w)
    pop = cum_w[-1]
    midpoints = (cum_w - w / 2.0) / pop
    mean = total / pop
    return float((2.0 / (pop * mean)) * (w * midpoints * x).sum() - 1.0)


def lorenz(values: Sequence[float]) -> Tuple[list, list]:
    """Lorenz curve points ``(population_share, value_share)``, both from 0 to 1."""
    import numpy as np

    x = np.sort(np.asarray(values, dtype="float64").ravel())
    if x.size == 0 or x.sum() <= 0:
        return [0.0, 1.0], [0.0, 1.0]
    pop = np.concatenate(([0.0], np.arange(1, x.size + 1) / x.size))
    share = np.concatenate(([0.0], np.cumsum(x) / x.sum()))
    return pop.tolist(), share.tolist()


def share_of_top(values: Sequence[float], fraction: float = 0.1) -> float:
    """Share of the total held by the brightest ``fraction`` of observations."""
    import numpy as np

    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    x = np.sort(np.asarray(values, dtype="float64").ravel())[::-1]
    if x.size == 0 or x.sum() <= 0:
        return float("nan")
    k = max(1, math.ceil(x.size * fraction))
    return float(x[:k].sum() / x.sum())


# --------------------------------------------------------------------------- #
# Theil indices (generalised entropy)
# --------------------------------------------------------------------------- #
# Why Theil alongside Gini: it is additively decomposable. Total inequality
# splits exactly into a between-group and a within-group part, which Gini
# cannot do (Gini's group decomposition leaves an overlap residual). With a
# nested hierarchy - pixels inside delegations inside governorates - that is
# the whole point.
#
# Zeros are the practical dividing line between the two:
#   * Theil T (GE(1)) weights by value share, and the 0*ln(0) term goes to 0 in
#     the limit, so an unlit pixel contributes nothing and T is well defined.
#   * Theil L (GE(0)) needs ln(mean/x), which diverges at x = 0. With 86% of
#     Tunisian pixels unlit in 1992, L is genuinely undefined there. It is
#     reported as nan rather than computed on a silently filtered sample.

THEIL_T = "theil_t"
THEIL_L = "theil_l"


def _mean_and_weights(values, weights):
    import numpy as np

    x = np.asarray(values, dtype="float64").ravel()
    if x.size == 0:
        return None, None, None
    if np.isnan(x).any():
        raise ValueError("Theil received NaN values")
    if (x < 0).any():
        raise ValueError("Theil is undefined for negative values")

    if weights is None:
        w = np.ones_like(x)
    else:
        w = np.asarray(weights, dtype="float64").ravel()
        if w.size != x.size:
            raise ValueError(
                f"weights length {w.size} does not match values length {x.size}"
            )
        if (w < 0).any():
            raise ValueError("Theil weights must be non-negative")

    total_w = w.sum()
    if total_w <= 0:
        return None, None, None
    mean = float((w * x).sum() / total_w)
    return x, w / total_w, mean


def theil_t(
    values: Sequence[float], weights: Optional[Sequence[float]] = None
) -> float:
    """Theil T index, GE(1): ``sum(p_i * (x_i/mu) * ln(x_i/mu))``.

    Zero-safe: an ``x_i`` of 0 contributes 0, matching the limit of
    ``t*ln(t)`` as ``t -> 0``. Returns ``nan`` for an empty or all-zero input.
    Ranges from 0 to ``ln(N)``, so values are not comparable across samples of
    different size without care.
    """
    import numpy as np

    x, p, mean = _mean_and_weights(values, weights)
    if x is None or mean is None or mean <= 0:
        return float("nan")
    ratio = x / mean
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(ratio > 0, ratio * np.log(ratio), 0.0)
    return float((p * terms).sum())


def theil_l(
    values: Sequence[float], weights: Optional[Sequence[float]] = None
) -> float:
    """Theil L index, GE(0), the mean log deviation: ``sum(p_i * ln(mu/x_i))``.

    Undefined when any value is 0, and reported as ``nan`` in that case rather
    than dropping the zeros - which would change the population being measured.
    """
    import numpy as np

    x, p, mean = _mean_and_weights(values, weights)
    if x is None or mean is None or mean <= 0:
        return float("nan")
    if (x[p > 0] <= 0).any():
        return float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(p > 0, np.log(mean / np.where(x > 0, x, 1.0)), 0.0)
    return float((p * terms).sum())


def theil(
    values: Sequence[float],
    measure: str = THEIL_T,
    weights: Optional[Sequence[float]] = None,
) -> float:
    """Dispatch to :func:`theil_t` or :func:`theil_l`."""
    if measure == THEIL_T:
        return theil_t(values, weights)
    if measure == THEIL_L:
        return theil_l(values, weights)
    raise ValueError(f"unknown measure {measure!r}; use {THEIL_T!r} or {THEIL_L!r}")


@dataclass(frozen=True)
class GroupPart:
    """One group's row in a decomposition."""

    key: str
    n: int
    mean: float
    population_share: float
    value_share: float
    index: float
    within_contribution: float


@dataclass(frozen=True)
class Decomposition:
    """An additive between/within split. ``total == between + within``."""

    measure: str
    total: float
    between: float
    within: float
    groups: List[GroupPart]

    @property
    def between_share(self) -> float:
        return self.between / self.total if self.total else float("nan")

    @property
    def within_share(self) -> float:
        return self.within / self.total if self.total else float("nan")

    def residual(self) -> float:
        """Departure from the identity - should be at machine precision."""
        return abs(self.total - (self.between + self.within))


def decompose_theil(
    values: Sequence[float],
    groups: Sequence,
    measure: str = THEIL_T,
) -> Decomposition:
    """Split a Theil index into between-group and within-group components.

    For **T** the within-group weights are value (light) shares and
    ``between = sum(s_g * ln(mu_g/mu))``; for **L** they are population shares
    and ``between = sum(p_g * ln(mu/mu_g))``. Both identities are exact, and a
    test asserts the residual stays at machine precision.

    A group holding no light has zero value share, so it drops out of T with no
    contribution (the limit of ``s*ln(s)``). For L such a group makes the index
    undefined, and ``nan`` is returned.
    """
    import numpy as np

    x = np.asarray(values, dtype="float64").ravel()
    g = np.asarray(groups).ravel()
    if g.size != x.size:
        raise ValueError(f"groups length {g.size} does not match values {x.size}")
    if x.size == 0:
        return Decomposition(measure, float("nan"), float("nan"), float("nan"), [])
    if (x < 0).any():
        raise ValueError("Theil is undefined for negative values")

    total_index = theil(x, measure)
    n = x.size
    mean = float(x.mean())
    if mean <= 0 or math.isnan(total_index):
        return Decomposition(measure, total_index, float("nan"), float("nan"), [])

    keys = np.unique(g)
    between = 0.0
    within = 0.0
    parts: List[GroupPart] = []
    undefined = False

    for key in keys:
        selection = x[g == key]
        n_g = selection.size
        mean_g = float(selection.mean()) if n_g else 0.0
        p_g = n_g / n
        s_g = (n_g * mean_g) / (n * mean)
        index_g = theil(selection, measure)

        if measure == THEIL_T:
            between_g = s_g * math.log(mean_g / mean) if s_g > 0 else 0.0
            contribution = s_g * index_g if s_g > 0 else 0.0
        else:
            if mean_g <= 0 or math.isnan(index_g):
                undefined = True
                between_g = float("nan")
                contribution = float("nan")
            else:
                between_g = p_g * math.log(mean / mean_g)
                contribution = p_g * index_g

        between += between_g
        within += contribution
        parts.append(
            GroupPart(
                key=str(key),
                n=n_g,
                mean=mean_g,
                population_share=p_g,
                value_share=s_g,
                index=index_g,
                within_contribution=contribution,
            )
        )

    if undefined:
        between = within = float("nan")
    return Decomposition(measure, total_index, between, within, parts)


def nested_theil_shares(
    values: Sequence[float],
    inner_groups: Sequence,
    outer_groups: Sequence,
    measure: str = THEIL_T,
) -> Dict[str, float]:
    """Three-way split for a nested hierarchy, e.g. pixels < delegations < governorates.

    Because the inner groups nest exactly inside the outer ones, the between
    component of the finer partition already contains the coarser one:

        between(inner) = between(outer) + between-inner-within-outer

    so the total splits into three additive parts without computing per-outer
    sub-decompositions. Nesting is the precondition; the caller must derive the
    outer key from the inner one (verified on Tunisia: the delegation and
    governorate grids agree on all 154,885 pixels).
    """
    outer = decompose_theil(values, outer_groups, measure)
    inner = decompose_theil(values, inner_groups, measure)
    return {
        "total": outer.total,
        "between_outer": outer.between,
        "between_inner_within_outer": inner.between - outer.between,
        "within_inner": inner.within,
    }


def decompose_theil_by_ids(
    values,
    ids,
    n_groups: int,
    measure: str = THEIL_T,
    keys: Optional[Sequence[str]] = None,
) -> Decomposition:
    """Vectorised :func:`decompose_theil` for integer group ids ``1..n_groups``.

    Same result as the reference implementation (a test asserts agreement), but
    built from ``bincount`` rather than a boolean mask per group. Measured at
    pixel scale (155k pixels, 268 delegations) it runs in ~13 ms against ~65 ms
    for the reference - a 5x saving that matters because the Tunisia run does
    this 372 times over year, scope, grouping and measure.

    The per-group index comes out of three accumulations, using
    ``T_g = (sum_g x*ln x)/(n_g*mu_g) - ln(mu_g)`` and
    ``L_g = ln(mu_g) - (sum_g ln x)/n_g``. Id 0 means "outside every group" and
    is excluded.
    """
    import numpy as np

    x = np.asarray(values, dtype="float64").ravel()
    g = np.asarray(ids).ravel()
    if g.size != x.size:
        raise ValueError(f"ids length {g.size} does not match values {x.size}")
    if (x < 0).any():
        raise ValueError("Theil is undefined for negative values")

    inside = g > 0
    x = x[inside]
    g = g[inside].astype(np.int64)
    if x.size == 0:
        return Decomposition(measure, float("nan"), float("nan"), float("nan"), [])

    n = x.size
    mean = float(x.mean())
    total_index = theil(x, measure)
    if mean <= 0 or math.isnan(total_index):
        return Decomposition(measure, total_index, float("nan"), float("nan"), [])

    size = n_groups + 1
    counts = np.bincount(g, minlength=size)[1:].astype("float64")
    sums = np.bincount(g, weights=x, minlength=size)[1:]

    with np.errstate(divide="ignore", invalid="ignore"):
        x_log_x = np.where(x > 0, x * np.log(x), 0.0)
    sum_xlogx = np.bincount(g, weights=x_log_x, minlength=size)[1:]

    present = counts > 0
    means = np.zeros_like(sums)
    np.divide(sums, counts, out=means, where=present)

    pop_share = np.zeros_like(sums)
    np.divide(counts, float(n), out=pop_share, where=present)
    value_share = sums / (n * mean)

    lit = present & (means > 0)
    index_g = np.full(sums.shape, np.nan)

    if measure == THEIL_T:
        with np.errstate(divide="ignore", invalid="ignore"):
            index_g[lit] = sum_xlogx[lit] / sums[lit] - np.log(means[lit])
        # A dark group has zero value share, so it drops out of both parts.
        index_g[present & ~lit] = 0.0
        between_terms = np.zeros_like(sums)
        between_terms[lit] = value_share[lit] * np.log(means[lit] / mean)
        within_terms = value_share * np.nan_to_num(index_g)
        between = float(between_terms.sum())
        within = float(within_terms.sum())
    else:
        if (x <= 0).any() or not bool(lit[present].all()):
            between = within = float("nan")
            within_terms = np.full(sums.shape, np.nan)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                sum_logx = np.bincount(g, weights=np.log(x), minlength=size)[1:]
                index_g[lit] = np.log(means[lit]) - sum_logx[lit] / counts[lit]
            between_terms = np.zeros_like(sums)
            between_terms[lit] = pop_share[lit] * np.log(mean / means[lit])
            within_terms = pop_share * index_g
            between = float(between_terms.sum())
            within = float(np.nansum(within_terms))

    parts = [
        GroupPart(
            key=str(keys[i]) if keys is not None and i < len(keys) else str(i + 1),
            n=int(counts[i]),
            mean=float(means[i]),
            population_share=float(pop_share[i]),
            value_share=float(value_share[i]),
            index=float(index_g[i]),
            within_contribution=float(within_terms[i]),
        )
        for i in range(n_groups)
        if present[i]
    ]
    return Decomposition(measure, total_index, between, within, parts)
