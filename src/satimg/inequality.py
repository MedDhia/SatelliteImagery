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
from typing import Optional, Sequence, Tuple


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
