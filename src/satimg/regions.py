"""Country-scoped analysis regions and the unit-exclusion variants.

Holds the per-country domain knowledge that does not belong in the generic
boundary or zonal machinery: what each country's admin levels are called, which
levels GADM actually has for it, and which units an analysis scope drops.

Every exclusion set is keyed on GADM ``GID_1`` codes rather than names. GADM's
names carry diacritics and vary in transliteration ("Kebili"/"Kébili",
"Médenine"/"Medenine"), so matching on them would break silently on a GADM
version bump; the codes are stable.

Two kinds of scope live here, and the difference matters when reading a result:

* **Hand-picked** (Tunisia's ``narrow``/``wide``) — a geographic judgement about
  which governorates are Saharan, made once and documented.
* **Derived** (``dark``/``dark_wide``, every country) — the output of
  ``scripts/derive_low_light_scopes.py``, which cuts each country's admin-1
  units at the largest discontinuity in their observed lit share. That finds a
  break in *light*, which is not the same thing as a desert: on Tunisia it
  reproduces the hand-picked Saharan trio exactly, but Libya's second break also
  catches populated Nafusa Mountain districts. The per-scope ``rationale``
  records what each one actually contains.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence

from .boundaries import DEFAULT_ROOT, BoundaryLayer, prepare_level

#: Levels the country workflow can use: national plus two subnational.
COUNTRY_LEVELS = (0, 1, 2)

#: Tunisia's names, kept as the module-level default for backwards
#: compatibility. Prefer :func:`level_title`, which is country-aware.
LEVEL_TITLES: Dict[int, str] = {
    0: "national",
    1: "governorate",
    2: "delegation",
}

#: What each country actually calls its admin levels. Using "governorate" for
#: an Algerian wilaya or a Mauritanian région would put a wrong word on 93 maps.
COUNTRY_LEVEL_TITLES: Dict[str, Dict[int, str]] = {
    "TUN": {0: "national", 1: "governorate", 2: "delegation"},
    "MAR": {0: "national", 1: "region", 2: "province"},
    "DZA": {0: "national", 1: "wilaya", 2: "daira"},
    "LBY": {0: "national", 1: "district"},
    "MRT": {0: "national", 1: "region", 2: "department"},
}

#: Generic fallback for a country with no entry above.
GENERIC_LEVEL_TITLES: Dict[int, str] = {
    0: "national",
    1: "admin-1 unit",
    2: "admin-2 unit",
}

#: GADM 4.1 has no ADM_2 layer for Libya, so its analysis stops at admin-1 and
#: the nested three-way Theil split degenerates to the two-way one. Stated here
#: rather than discovered as an empty layer halfway through a run.
LEVELS_AVAILABLE: Dict[str, tuple] = {"LBY": (0, 1)}

#: The Arab Maghreb Union, in the order its members are usually listed.
MAGHREB = ("MAR", "DZA", "TUN", "LBY", "MRT")


def level_title(iso3: str, level: int) -> str:
    """What ``iso3`` calls this admin level."""
    titles = COUNTRY_LEVEL_TITLES.get(iso3.upper(), GENERIC_LEVEL_TITLES)
    return titles.get(level, GENERIC_LEVEL_TITLES[level])


def available_levels(iso3: str) -> tuple:
    """Admin levels GADM actually provides for a country."""
    return LEVELS_AVAILABLE.get(iso3.upper(), COUNTRY_LEVELS)


def has_level(iso3: str, level: int) -> bool:
    return level in available_levels(iso3)


@dataclass(frozen=True)
class DesertScope:
    """A named subset of admin-1 units to exclude, with its rationale.

    ``derived`` distinguishes a scope produced by the low-light rule from one
    picked by hand, so a reader can tell whether "excluded" means "we judged
    this Saharan" or "the light data put it below the break".
    """

    key: str
    label: str
    gid1: FrozenSet[str]
    rationale: str
    derived: bool = False


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


# --------------------------------------------------------------------------- #
# Derived low-light scopes
# --------------------------------------------------------------------------- #
#: Frozen output of ``scripts/derive_low_light_scopes.py --year 2022`` against
#: GADM 4.1. Committed rather than recomputed at run time for the same reason
#: the dataset manifest is: a scope that silently re-derives itself is a scope
#: no reviewer ever sees change. Re-run the script and commit the diff when the
#: reference year or the boundary version moves.
#:
#: Read the rationales. The rule cuts at a break in observed light, and the
#: name of each scope says so - it does not claim the excluded units are desert.
LOW_LIGHT_REFERENCE_YEAR = 2022

DERIVED_SCOPES: Dict[str, Dict[str, DesertScope]] = {
    "TUN": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"TUN.21_1", "TUN.10_1", "TUN.22_1"}),
            rationale=(
                "Tataouine, Kebili, Tozeur - below a x2.37 break at 17.7% lit. "
                "Identical to the hand-picked `narrow` set, which is the check "
                "that the rule measures something real"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 6",
            gid1=frozenset(
                {"TUN.21_1", "TUN.10_1", "TUN.22_1", "TUN.14_1", "TUN.5_1", "TUN.19_1"}
            ),
            rationale=(
                "adds Médenine, Gabès and Siliana below a x1.21 break at 46.8% "
                "lit. NOT a desert set: Siliana is a northwestern interior "
                "governorate, and the hand-picked `wide` takes Gafsa instead"
            ),
            derived=True,
        ),
    },
    "MAR": {
        "dark": DesertScope(
            key="dark",
            label="darkest 2",
            gid1=frozenset({"MAR.7_1", "MAR.6_1"}),
            rationale=(
                "Laâyoune-Boujdour-Sakia El Hamra and Guelmim-Es-Semara, below "
                "a x4.01 break at 4.9% lit - the Saharan south, and the "
                "sharpest break of any country here"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 5",
            gid1=frozenset({"MAR.7_1", "MAR.6_1", "MAR.12_1", "MAR.9_1", "MAR.10_1"}),
            rationale=(
                "adds Souss-Massa-Drâa, Meknès-Tafilalet and Oriental below a "
                "x1.52 break at 23.5% lit - the pre-Saharan and arid interior"
            ),
            derived=True,
        ),
    },
    "DZA": {
        "dark": DesertScope(
            key="dark",
            label="darkest 4",
            gid1=frozenset({"DZA.41_1", "DZA.44_1", "DZA.1_1", "DZA.7_1"}),
            rationale=(
                "Tamanghasset, Tindouf, Adrar, Béchar below a x1.92 break at "
                "2.7% lit. Under-inclusive as a Sahara definition: Illizi, "
                "Ghardaïa, Ouargla and El Oued are Saharan but carry oil-town "
                "and oasis light"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 7",
            gid1=frozenset(
                {
                    "DZA.41_1",
                    "DZA.44_1",
                    "DZA.1_1",
                    "DZA.7_1",
                    "DZA.17_1",
                    "DZA.22_1",
                    "DZA.20_1",
                }
            ),
            rationale=(
                "adds El Bayadh, Illizi and Ghardaïa below a x1.58 break at "
                "6.7% lit - closer to the conventional Algerian Sahara"
            ),
            derived=True,
        ),
    },
    "LBY": {
        "dark": DesertScope(
            key="dark",
            label="darkest 1",
            gid1=frozenset({"LBY.6_1"}),
            rationale=(
                "Al Kufrah alone, below a x3.05 break at 0.3% lit. Badly "
                "under-inclusive: Murzuq, Ghat and Al Jufrah are equally "
                "Saharan but sit above the break"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 9",
            gid1=frozenset(
                {
                    "LBY.6_1",
                    "LBY.16_1",
                    "LBY.14_1",
                    "LBY.5_1",
                    "LBY.22_1",
                    "LBY.1_1",
                    "LBY.19_1",
                    "LBY.3_1",
                    "LBY.17_1",
                }
            ),
            rationale=(
                "nine districts below a x1.69 break at 6.6% lit. Mixed: Murzuq, "
                "Ghat and Al Jufrah are Sahara, but Al Jabal al Gharbi and "
                "Nalut are populated Nafusa Mountain districts"
            ),
            derived=True,
        ),
    },
    "MRT": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"MRT.11_1", "MRT.1_1", "MRT.7_1"}),
            rationale=(
                "Tagant, Adrar, Hodh ech Chargui below a x2.21 break at 0.1% "
                "lit - all genuinely Saharan"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 5",
            gid1=frozenset({"MRT.11_1", "MRT.1_1", "MRT.7_1", "MRT.12_1", "MRT.8_1"}),
            rationale=(
                "adds Tiris Zemmour (deep Sahara) and Hodh el Gharbi (Sahel) "
                "below a x2.07 break at 0.2% lit. This is the guard binding: "
                "Mauritania has 13 regions and Nouakchott alone holds 79% lit "
                "against a national median of 0.9%, so no further cut can leave "
                "enough units to measure"
            ),
            derived=True,
        ),
    },
}


def _merge_scopes() -> Dict[str, Dict[str, DesertScope]]:
    """Hand-picked scopes first, then the derived ones, per country.

    A derived scope that excludes exactly the same units as a hand-picked one is
    dropped rather than emitted twice: it would double every downstream series
    for no new information. Tunisia's ``dark`` is exactly its ``narrow``, and
    that equality is the evidence the low-light rule finds real geography - it
    is recorded in the module docstring and the datasheet, not as a duplicate
    row in 372 output series.
    """
    merged: Dict[str, Dict[str, DesertScope]] = {"TUN": dict(TUNISIA_DESERT_SCOPES)}
    for iso3, scopes in DERIVED_SCOPES.items():
        existing = merged.setdefault(iso3, {})
        already = {scope.gid1 for scope in existing.values()}
        for key, scope in scopes.items():
            if scope.gid1 not in already:
                existing[key] = scope
    return merged


DESERT_SCOPES: Dict[str, Dict[str, DesertScope]] = _merge_scopes()

#: Analysis scopes applied to every level: the full country, then each exclusion.
SCOPE_ALL = "all"


def resolve_levels(iso3: str, requested: Sequence[int]) -> tuple:
    """Requested levels intersected with what GADM has, plus what was dropped.

    Returns ``(levels, dropped)``. Libya is the live case: asking for 0,1,2
    should yield a Libya analysis at 0,1 with the gap reported, not an empty
    admin-2 layer discovered several minutes into a render.
    """
    have = available_levels(iso3)
    levels = [lv for lv in requested if lv in have]
    dropped = [lv for lv in requested if lv not in have]
    if not levels:
        raise ValueError(
            f"{iso3} has no requested level available; GADM provides {list(have)}"
        )
    return tuple(levels), tuple(dropped)


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
