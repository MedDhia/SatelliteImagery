"""Pace of change in the inequality series, and what kind of change it is.

The cross-country tables elsewhere in this project compare *levels* - Theil T in
1992 against 2022. That comparison is partly mechanical: Theil T is bounded by
ln(N), and N ranges from Bahrain's 717 land pixels to Algeria's 2 308 015.
Measured across the 22 Arab League countries, Spearman(N, Theil T in 1992) is
**+0.68**; normalising by ln(N) only brings it to +0.53.

Rates do not have that problem. N is fixed over time within a country - the same
land area every year - so ln(N) is a constant offset that cancels out of any
proportional change. Comparing how *fast* inequality moves is therefore sound
where comparing how *high* it sits is not, which is the reason this module
exists.

Everything here reads the committed CSVs under ``results/``. No rasters, no
GADM, no network - and so no optional dependencies either, like
:mod:`satimg.inequality`.

Two properties of the source decide how the results must be read, and both are
carried into the output rather than left to a footnote:

* **A falling total is partly an artefact.** A lit pixel in LRCC-DVNL never
  dims; it goes out (see ``docs/lrcc-dvnl.md``). As lit area grows, the
  zeros-included index falls almost by construction. The lit-only rate is
  reported beside it precisely so the two can be told apart.
* **The 2014 sensor handover moves the rates.** 18 of 22 countries decline
  faster in the VIIRS era than the DMSP era. A near-universal acceleration at
  exactly the instrument boundary is an instrument signature, so the windows are
  reported separately and never averaged into one headline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

#: The DMSP->VIIRS handover. Rates either side are not comparable.
BREAK_YEAR = 2014

#: Fit windows. "full" is reported for completeness and is the one to distrust.
WINDOWS: Tuple[Tuple[str, Optional[int], Optional[int]], ...] = (
    ("full", None, None),
    ("dmsp", None, BREAK_YEAR - 1),
    ("viirs", BREAK_YEAR, None),
)

#: Below this, a single slope is not describing the series - say so instead of
#: printing a rate. Syria rises then partly recovers; one number would hide it.
MONOTONE_R2 = 0.5

#: Minimum points before a fit means anything.
MIN_POINTS = 5

#: Relative spread below which a series counts as having no variation at all.
FLAT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Rate:
    """A log-linear fit: proportional change per year, and how well it fits."""

    percent_per_year: float
    r_squared: float
    n_years: int
    first_year: Optional[int] = None
    last_year: Optional[int] = None

    @property
    def half_life_years(self) -> float:
        """Years to halve. ``nan`` when the series is not falling.

        A rising series has no half-life; returning a negative number would
        invite it being read as one.
        """
        if not math.isfinite(self.percent_per_year) or self.percent_per_year >= 0:
            return float("nan")
        return math.log(2) / (-self.percent_per_year / 100.0)

    @property
    def is_monotone(self) -> bool:
        return math.isfinite(self.r_squared) and self.r_squared >= MONOTONE_R2

    @property
    def direction(self) -> str:
        if not math.isfinite(self.percent_per_year):
            return "undefined"
        if abs(self.percent_per_year) < 0.05:
            return "flat"
        return "falling" if self.percent_per_year < 0 else "rising"


UNDEFINED = Rate(float("nan"), float("nan"), 0)


def log_linear_rate(years: Sequence[int], values: Sequence[float]) -> Rate:
    """Fit ``ln(value) = a + b*year``; return ``b`` as percent per year.

    Proportional rather than absolute because these are ratio-scale indices: a
    fall from 8.0 to 6.0 and one from 0.8 to 0.6 are the same *pace*, and an
    absolute slope would call the first ten times larger.

    Non-positive and non-finite values are dropped, not clamped. ``lit_share``
    reaches 0 and Theil L is ``nan`` wherever any unit is unlit; substituting a
    small epsilon would invent a rate out of a missing observation.
    """
    points = [
        (year, value)
        for year, value in zip(years, values)
        if value is not None and math.isfinite(value) and value > 0
    ]
    if len(points) < MIN_POINTS:
        return UNDEFINED

    xs = [float(p[0]) for p in points]
    ys = [math.log(p[1]) for p in points]
    n = len(points)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return UNDEFINED
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx

    # A flat series has no variance to explain, so R^2 is 0/0 - undefined, not
    # 1.0, and reporting 1.0 would call a flat line a perfect trend. Detected on
    # the spread of the inputs rather than on the residual sum, because summing
    # 31 identical floats leaves a few ulps of noise and the ratio of two noise
    # terms lands anywhere in [0, 1].
    if max(ys) - min(ys) <= FLAT_TOLERANCE * max(1.0, abs(mean_y)):
        return Rate(0.0, float("nan"), n, int(min(xs)), int(max(xs)))

    syy = sum((y - mean_y) ** 2 for y in ys)
    r_squared = sxy**2 / (sxx * syy)

    return Rate(
        percent_per_year=slope * 100.0,
        r_squared=r_squared,
        n_years=n,
        first_year=int(min(xs)),
        last_year=int(max(xs)),
    )


def window_rate(
    series: Dict[int, float], first: Optional[int], last: Optional[int]
) -> Rate:
    """Fit one window of a ``{year: value}`` series."""
    years = sorted(
        year
        for year in series
        if (first is None or year >= first) and (last is None or year <= last)
    )
    return log_linear_rate(years, [series[year] for year in years])


# --------------------------------------------------------------------------- #
# reading the committed series
# --------------------------------------------------------------------------- #
#: The measures compared, and what each one answers.
MEASURES: Tuple[Tuple[str, str], ...] = (
    ("total", "Theil T over all land pixels - both margins together"),
    ("intensive", "Theil T over lit pixels only - convergence among the already lit"),
    ("extensive", "share of land pixels that are lit - light reaching new ground"),
    ("between_share", "share of Theil T lying between admin-1 units"),
)


def series_from_rows(rows: Sequence[dict]) -> Dict[str, Dict[int, float]]:
    """Pull the pixel-level, all-units series out of an inequality CSV."""

    def number(value):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return float("nan")
        return result

    out: Dict[str, Dict[int, float]] = {key: {} for key, _ in MEASURES}
    for row in rows:
        if row.get("level") != "pixel" or row.get("scope") != "all":
            continue
        year = int(row["year"])
        if row.get("zeros") == "zeros_included":
            out["total"][year] = number(row.get("theil_t"))
            out["extensive"][year] = number(row.get("lit_share"))
        elif row.get("zeros") == "lit_only":
            out["intensive"][year] = number(row.get("theil_t"))
    return out


def between_share_series(rows: Sequence[dict], grouping: str) -> Dict[int, float]:
    """Between-group share of Theil T, from a decomposition CSV."""
    out: Dict[int, float] = {}
    for row in rows:
        if (
            row.get("measure") != "theil_t"
            or row.get("grouping") != grouping
            or row.get("scope") != "all"
            or row.get("zeros") != "zeros_included"
        ):
            continue
        try:
            out[int(row["year"])] = float(row["between_share"])
        except (TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------- #
# typology
# --------------------------------------------------------------------------- #
#: Thresholds are module constants rather than inline magic numbers so the
#: classification below can be checked, and argued with, from the output table.
FLAT = 0.25  # |%/yr| under this counts as no movement
RISING = 0.05  # above this the intensive margin is genuinely going the wrong way

INTENSIVE_CONVERGER = "intensive converger"
EXTENSIVE_SPREADER = "extensive spreader"
DISRUPTED = "disrupted"
MIXED = "mixed"
FLAT_LABEL = "flat"


def classify_trajectory(
    total: Rate, intensive: Rate, extensive: Rate
) -> Tuple[str, str]:
    """Name the kind of change, and say why in one clause.

    The distinction that matters: a country whose total inequality falls while
    inequality *among already-lit places* rises is not converging at all - light
    is simply arriving somewhere new. Reporting only the total calls that the
    same thing as genuine convergence.
    """
    if not math.isfinite(total.percent_per_year):
        return "undefined", "no usable series"

    # Light retreating is a different regime from any of the others.
    if extensive.direction == "falling" and math.isfinite(extensive.percent_per_year):
        return DISRUPTED, "lit area shrinking"
    if total.direction == "rising":
        return DISRUPTED, "total inequality rising"
    if abs(total.percent_per_year) < FLAT:
        return FLAT_LABEL, "total inequality barely moving"

    if intensive.percent_per_year > RISING:
        return (
            EXTENSIVE_SPREADER,
            (
                "total falls only because light reaches new ground; "
                "inequality among lit places rises"
            ),
        )
    if intensive.percent_per_year < -FLAT and extensive.percent_per_year < 1.0:
        return (
            INTENSIVE_CONVERGER,
            "already largely lit; the decline is convergence among lit places",
        )
    return MIXED, "both margins contribute"


def country_rows(iso3: str, series: Dict[str, Dict[int, float]]) -> List[dict]:
    """One row per measure per window, plus the trajectory label."""
    rates: Dict[Tuple[str, str], Rate] = {}
    for key, _ in MEASURES:
        for window, first, last in WINDOWS:
            rates[(key, window)] = window_rate(series.get(key, {}), first, last)

    label, why = classify_trajectory(
        rates[("total", "full")],
        rates[("intensive", "full")],
        rates[("extensive", "full")],
    )

    rows: List[dict] = []
    for key, description in MEASURES:
        for window, _, _ in WINDOWS:
            rate = rates[(key, window)]
            rows.append(
                {
                    "iso3": iso3,
                    "measure": key,
                    "measure_note": description,
                    "window": window,
                    "first_year": rate.first_year,
                    "last_year": rate.last_year,
                    "n_years": rate.n_years,
                    "percent_per_year": rate.percent_per_year,
                    "r_squared": rate.r_squared,
                    "half_life_years": rate.half_life_years,
                    "direction": rate.direction,
                    "monotone": rate.is_monotone,
                    "trajectory": label,
                    "trajectory_reason": why,
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# publication
# --------------------------------------------------------------------------- #
#: Where the committed CSVs live. Everything below reads only from here.
RESULTS_DIR = "results"

#: The published table.
TRENDS_TABLE = "trends_by_country.csv"

#: The published figure, relative to the gallery root.
PACE_FIGURE = "trends/pace_total_vs_intensive.png"


def _read_csv(path) -> List[dict]:
    import csv
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def country_series(iso3: str, results_dir=RESULTS_DIR) -> Dict[str, Dict[int, float]]:
    """Every measured series for one country, read from ``results/``."""
    from pathlib import Path

    from . import regions as R

    root = Path(results_dir) / iso3
    series = series_from_rows(_read_csv(root / f"{iso3}_inequality_series.csv"))
    series["between_share"] = between_share_series(
        _read_csv(root / f"{iso3}_theil_decomposition.csv"),
        R.level_title(iso3, 1),
    )
    return series


def build_rows(results_dir=RESULTS_DIR, countries: Optional[Sequence[str]] = None):
    """The published table: one row per country x measure x window."""
    from . import regions as R

    isos = list(countries) if countries is not None else list(R.ARAB_LEAGUE)
    rows: List[dict] = []
    for iso3 in isos:
        series = country_series(iso3, results_dir)
        if not series.get("total"):
            continue
        rows.extend(country_rows(iso3, series))
    return rows


def build(results_dir=RESULTS_DIR, countries: Optional[Sequence[str]] = None):
    """Write ``results/trends_by_country.csv`` and return (path, rows)."""
    from pathlib import Path

    from .analysis import write_csv

    rows = build_rows(results_dir, countries)
    if not rows:
        return None, rows
    path = write_csv(rows, Path(results_dir) / TRENDS_TABLE)
    return path, rows


def full_window(rows: Sequence[dict], measure: str) -> Dict[str, dict]:
    """Index the full-window rows of one measure by country."""
    return {
        row["iso3"]: row
        for row in rows
        if row["measure"] == measure and row["window"] == "full"
    }


def era_comparison(rows: Sequence[dict], measure: str = "total"):
    """(iso3, dmsp %/yr, viirs %/yr) for every country with both windows fit."""
    by_country: Dict[str, Dict[str, dict]] = {}
    for row in rows:
        if row["measure"] != measure:
            continue
        by_country.setdefault(row["iso3"], {})[row["window"]] = row
    out = []
    for iso3, windows in sorted(by_country.items()):
        dmsp, viirs = windows.get("dmsp"), windows.get("viirs")
        if not dmsp or not viirs:
            continue
        a, b = float(dmsp["percent_per_year"]), float(viirs["percent_per_year"])
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        out.append((iso3, a, b))
    return out
