"""Country-scoped analysis regions and the desert-exclusion variants.

Holds the Tunisia-specific domain knowledge that does not belong in the generic
boundary or zonal machinery: which GADM units count as "desertic", and how a
country's three levels are named.

The desert sets are keyed on GADM ``GID_1`` codes rather than names. GADM's
names carry diacritics and vary in transliteration ("Kebili"/"Kébili",
"Médenine"/"Medenine"), so matching on them would break silently on a GADM
version bump; the codes are stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

from .boundaries import DEFAULT_ROOT, BoundaryLayer, prepare_level

#: Levels used by the country workflow: national plus two subnational.
COUNTRY_LEVELS = (0, 1, 2)

LEVEL_TITLES: Dict[int, str] = {
    0: "national",
    1: "governorate",
    2: "delegation",
}


@dataclass(frozen=True)
class DesertScope:
    """A named subset of admin-1 units to exclude, with its rationale."""

    key: str
    label: str
    gid1: FrozenSet[str]
    rationale: str


#: Tunisia. Measured against LACC_2022: the trio is 67,570 km² (44% of the
#: land area) at 9.8/11.3/17.7% lit and 1.3-2.6 SOL/km², a clear break from the
#: next governorate (Médenine, 42% lit, 6.2 SOL/km²).
TUNISIA_DESERT_SCOPES: Dict[str, DesertScope] = {
    "narrow": DesertScope(
        key="narrow",
        label="Saharan trio",
        gid1=frozenset({"TUN.21_1", "TUN.10_1", "TUN.22_1"}),
        rationale="Tataouine, Kebili, Tozeur - the true Sahara/chott governorates",
    ),
    "wide": DesertScope(
        key="wide",
        label="six southern",
        gid1=frozenset(
            {"TUN.21_1", "TUN.10_1", "TUN.22_1", "TUN.14_1", "TUN.5_1", "TUN.6_1"}
        ),
        rationale=(
            "adds Médenine, Gabès, Gafsa - the conventional Tunisian South, "
            "which also removes coastal and mining light"
        ),
    ),
}

DESERT_SCOPES: Dict[str, Dict[str, DesertScope]] = {"TUN": TUNISIA_DESERT_SCOPES}

#: Analysis scopes applied to every level: the full country, then each exclusion.
SCOPE_ALL = "all"


def check_level_for_country(level: int) -> int:
    """Validate an admin level for the country workflow (0, 1 or 2)."""
    if level not in COUNTRY_LEVELS:
        raise ValueError(
            f"country workflow supports levels {list(COUNTRY_LEVELS)}, got {level!r}"
        )
    return level


def desert_scopes(iso3: str) -> Dict[str, DesertScope]:
    """Desert-exclusion definitions available for a country (may be empty)."""
    return DESERT_SCOPES.get(iso3.upper(), {})


def scope_keys(iso3: str) -> List[str]:
    return [SCOPE_ALL, *desert_scopes(iso3)]


def excluded_gid1(iso3: str, scope: str) -> FrozenSet[str]:
    """GID_1 codes excluded by a scope. ``all`` excludes nothing."""
    if scope == SCOPE_ALL:
        return frozenset()
    scopes = desert_scopes(iso3)
    if scope not in scopes:
        known = ", ".join([SCOPE_ALL, *scopes])
        raise ValueError(f"unknown scope {scope!r} for {iso3}; known: {known}")
    return scopes[scope].gid1


#: Zonal statistics use UNSIMPLIFIED geometry. ``simplify`` runs per polygon,
#: so neighbouring units stop tiling exactly: gaps and slivers appear along
#: shared borders, pixels fall through them, and the per-unit sums stop adding
#: back to the national total. Measured on Tunisia at 500 m, that lost 1,940 of
#: 253,365 SOL at admin-2 and starved one delegation to zero pixels. The
#: simplification exists to make 124k global rings drawable; a country's 268
#: units need no such help.
ANALYSIS_TOLERANCE_M = 0.0


def country_layer(
    iso3: str,
    level: int,
    *,
    root: str | Path = DEFAULT_ROOT,
    force: bool = False,
    tolerance_m: float = ANALYSIS_TOLERANCE_M,
) -> BoundaryLayer:
    """Prepared, reprojected boundary layer for one country and admin level.

    Defaults to exact geometry - see :data:`ANALYSIS_TOLERANCE_M`.
    """
    return prepare_level(
        root, level=level, iso3=iso3, force=force, tolerance_m=tolerance_m
    )


def load_units(layer: BoundaryLayer):
    """Read a prepared country layer as a GeoDataFrame."""
    import geopandas as gpd

    return gpd.read_file(layer.path, engine="pyogrio")


def id_fields(level: int) -> tuple:
    """(id_field, name_field) for a GADM admin level."""
    if level == 0:
        return "GID_0", "COUNTRY"
    if level == 1:
        return "GID_1", "NAME_1"
    return "GID_2", "NAME_2"


def parent_gid1(frame, level: int) -> Optional[List[str]]:
    """The GID_1 each unit belongs to, for applying a desert exclusion.

    Admin-1 units are their own parent; admin-2 units carry GID_1 directly.
    Admin-0 has no parent, so exclusions cannot apply.
    """
    if level == 0:
        return None
    if "GID_1" not in frame.columns:
        raise ValueError("layer has no GID_1 column; cannot apply a desert scope")
    return frame["GID_1"].astype(str).tolist()
