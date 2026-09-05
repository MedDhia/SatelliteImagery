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

#: What each country actually calls its admin levels, taken from GADM's own
#: ``ENGTYPE_1``/``ENGTYPE_2`` fields (modal value per country) rather than
#: guessed. Guessing got Algeria wrong: its ADM_2 units are *communes*, not
#: daïras - GADM labels 1 345 of 1 504 that way - and the wrong word was
#: rendered onto every Algerian admin-2 map before this was checked.
#:
#: Where GADM records no type (Djibouti's ADM_2 is literally "NA") the generic
#: fallback applies rather than a plausible-sounding invention.
COUNTRY_LEVEL_TITLES: Dict[str, Dict[int, str]] = {
    "AGO": {0: "national", 1: "province"},
    "ARE": {0: "national", 1: "emirate", 2: "district"},
    "BDI": {0: "national", 1: "province", 2: "commune"},
    "BEN": {0: "national", 1: "department", 2: "commune"},
    "BFA": {0: "national", 1: "region", 2: "province"},
    "BHR": {0: "national", 1: "governorate"},
    "BWA": {0: "national", 1: "district", 2: "sub-district"},
    "CAF": {0: "national", 1: "prefecture", 2: "sub-prefecture"},
    "CIV": {0: "national", 1: "district", 2: "region"},
    "CMR": {0: "national", 1: "region", 2: "department"},
    "COD": {0: "national", 1: "province", 2: "territory"},
    "COG": {0: "national", 1: "region", 2: "district"},
    "COM": {0: "national", 1: "autonomous island"},
    "CPV": {0: "national", 1: "county"},
    "DJI": {0: "national", 1: "region"},
    "DZA": {0: "national", 1: "province", 2: "commune"},
    "EGY": {0: "national", 1: "governorate", 2: "subdivision"},
    "ERI": {0: "national", 1: "region", 2: "district"},
    "ESH": {0: "national", 1: "province"},
    "ETH": {0: "national", 1: "state", 2: "zone"},
    "GAB": {0: "national", 1: "province", 2: "department"},
    "GHA": {0: "national", 1: "region", 2: "district"},
    "GIN": {0: "national", 1: "region", 2: "prefecture"},
    "GMB": {0: "national", 1: "division", 2: "district"},
    "GNB": {0: "national", 1: "region", 2: "sector"},
    "GNQ": {0: "national", 1: "province"},
    "IRQ": {0: "national", 1: "province", 2: "district"},
    "JOR": {0: "national", 1: "province", 2: "sub-province"},
    "KEN": {0: "national", 1: "county", 2: "constituency"},
    "KWT": {0: "national", 1: "province"},
    "LBN": {0: "national", 1: "governorate", 2: "district"},
    "LBR": {0: "national", 1: "county", 2: "district"},
    "LBY": {0: "national", 1: "district"},
    "LSO": {0: "national", 1: "district"},
    "MAR": {0: "national", 1: "region", 2: "province"},
    "MDG": {0: "national"},
    "MLI": {0: "national", 1: "region", 2: "circle"},
    "MOZ": {0: "national", 1: "province", 2: "district"},
    "MRT": {0: "national", 1: "region", 2: "department"},
    "MUS": {0: "national", 1: "district"},
    "MWI": {0: "national", 1: "district", 2: "traditional authority"},
    "NAM": {0: "national", 1: "region", 2: "constituency"},
    "NER": {0: "national", 1: "department", 2: "arrondissement"},
    "NGA": {0: "national", 1: "state", 2: "local authority"},
    "OMN": {0: "national", 1: "region", 2: "province"},
    "PSE": {0: "national", 1: "district", 2: "governorate"},
    "QAT": {0: "national", 1: "municipality"},
    "RWA": {0: "national", 1: "province", 2: "district"},
    "SAU": {0: "national", 1: "province", 2: "governorate"},
    "SDN": {0: "national", 1: "state", 2: "district"},
    "SEN": {0: "national", 1: "region", 2: "department"},
    "SLE": {0: "national", 1: "province", 2: "district"},
    "SOM": {0: "national", 1: "region", 2: "district"},
    "SSD": {0: "national", 1: "state", 2: "district"},
    "STP": {0: "national", 1: "municipality"},
    "SWZ": {0: "national", 1: "district", 2: "constituency"},
    "SYC": {0: "national", 1: "district"},
    "SYR": {0: "national", 1: "governorate", 2: "district"},
    "TCD": {0: "national", 1: "region", 2: "department"},
    "TGO": {0: "national", 1: "region", 2: "prefecture"},
    "THA": {0: "national", 1: "province", 2: "district"},
    "TUN": {0: "national", 1: "governorate", 2: "delegation"},
    "TZA": {0: "national", 1: "region", 2: "district"},
    "UGA": {0: "national", 1: "district", 2: "county"},
    "YEM": {0: "national", 1: "governorate", 2: "district"},
    "ZAF": {0: "national", 1: "province", 2: "district municipality"},
    "ZMB": {0: "national", 1: "province", 2: "district"},
    "ZWE": {0: "national", 1: "province", 2: "district"},
}

#: Generic fallback for a country with no entry above.
GENERIC_LEVEL_TITLES: Dict[int, str] = {
    0: "national",
    1: "admin-1 unit",
    2: "admin-2 unit",
}

#: Countries where GADM 4.1 ships no ADM_2 layer, so the analysis stops at
#: admin-1 and the nested three-way Theil split degenerates to the two-way one.
#: Stated here rather than discovered as an empty layer halfway through a run.
LEVELS_AVAILABLE: Dict[str, tuple] = {
    iso3: (0, 1)
    for iso3 in (
        "LBY",
        "BHR",
        "COM",
        "KWT",
        "QAT",
        "COM",
        "CPV",
        "ESH",
        "LBY",
        "LSO",
        "MUS",
        "SYC",
    )
}

#: The Arab Maghreb Union, in the order its members are usually listed.
MAGHREB = ("MAR", "DZA", "TUN", "LBY", "MRT")

#: The Arab League's 22 members, Maghreb first so the earlier work keeps its
#: place in every generated index. Palestine appears with GADM's own coding of
#: the West Bank and Gaza; that is the boundary set in use, not a position on
#: its status.
ARAB_LEAGUE = (
    *MAGHREB,
    "EGY",
    "SDN",
    "SAU",
    "YEM",
    "OMN",
    "ARE",
    "QAT",
    "BHR",
    "KWT",
    "IRQ",
    "SYR",
    "LBN",
    "JOR",
    "PSE",
    "SOM",
    "DJI",
    "COM",
)

#: The 54 UN member states of Africa, plus Western Sahara. `ESH` appears with
#: GADM's own coding of the territory - the same footing Palestine is on here,
#: and for the same reason: it is the boundary set in use, not a position on
#: status. GADM's `MAR` excludes it, so leaving it out would put a hole in the
#: continent.
AFRICA = (
    "AGO",
    "BDI",
    "BEN",
    "BFA",
    "BWA",
    "CAF",
    "CIV",
    "CMR",
    "COD",
    "COG",
    "COM",
    "CPV",
    "DJI",
    "DZA",
    "EGY",
    "ERI",
    "ESH",
    "ETH",
    "GAB",
    "GHA",
    "GIN",
    "GMB",
    "GNB",
    "GNQ",
    "KEN",
    "LBR",
    "LBY",
    "LSO",
    "MAR",
    "MDG",
    "MLI",
    "MOZ",
    "MRT",
    "MUS",
    "MWI",
    "NAM",
    "NER",
    "NGA",
    "RWA",
    "SDN",
    "SEN",
    "SLE",
    "SOM",
    "SSD",
    "STP",
    "SWZ",
    "SYC",
    "TCD",
    "TGO",
    "TUN",
    "TZA",
    "UGA",
    "ZAF",
    "ZMB",
    "ZWE",
)

#: Every country this repository analyses. Wider than any single pool, and the
#: difference is load-bearing rather than cosmetic.
#:
#: The cross-country artefacts are **pooled**, and one of them pools in a way
#: that adding a row does not undo: each aridity join cuts `dark_2022` at the
#: *median* mean DN **of its own pool**. Adding a country to a pool moves that
#: pool's median and rewrites every `dark_2022` and `cell` in it.
#:
#: So a country is analysed on its own terms - clipped rasters, zonal tables,
#: inequality series, decomposition, charts, figures - and separately belongs to
#: zero or more pools. Use `COUNTRIES` for "what exists here" and a pool for
#: "what is being compared with what".
COUNTRIES = (
    *ARAB_LEAGUE,
    "THA",
    *(iso3 for iso3 in AFRICA if iso3 not in ARAB_LEAGUE),
)

#: Named comparison pools. Each owns its own cross-country artefacts, and a
#: country may sit in more than one - ten African states are also Arab League
#: members and appear in both, each time against a different set of neighbours.
POOLS: Dict[str, tuple] = {
    "arab-league": ARAB_LEAGUE,
    "africa": AFRICA,
}
DEFAULT_POOL = "arab-league"


def pool_countries(pool: str) -> tuple:
    """The countries a pool compares. Raises rather than silently emptying."""
    try:
        return POOLS[pool]
    except KeyError:
        raise KeyError(
            f"unknown pool {pool!r}; known pools: {', '.join(sorted(POOLS))}"
        ) from None


#: Display names, in one place because the gallery, the results catalogue and
#: the docs must not disagree about what a country is called. Where GADM 4.1
#: carries a stale name the current one is used: Eswatini, not Swaziland.
COUNTRY_NAMES: Dict[str, str] = {
    "MAR": "Morocco",
    "DZA": "Algeria",
    "TUN": "Tunisia",
    "LBY": "Libya",
    "MRT": "Mauritania",
    "EGY": "Egypt",
    "SDN": "Sudan",
    "SAU": "Saudi Arabia",
    "YEM": "Yemen",
    "OMN": "Oman",
    "ARE": "United Arab Emirates",
    "QAT": "Qatar",
    "BHR": "Bahrain",
    "KWT": "Kuwait",
    "IRQ": "Iraq",
    "SYR": "Syria",
    "LBN": "Lebanon",
    "JOR": "Jordan",
    "PSE": "Palestine",
    "SOM": "Somalia",
    "DJI": "Djibouti",
    "COM": "Comoros",
    "THA": "Thailand",
    "AGO": "Angola",
    "BDI": "Burundi",
    "BEN": "Benin",
    "BFA": "Burkina Faso",
    "BWA": "Botswana",
    "CAF": "Central African Republic",
    "CIV": "Côte d'Ivoire",
    "CMR": "Cameroon",
    "COD": "DR Congo",
    "COG": "Republic of the Congo",
    "CPV": "Cabo Verde",
    "ERI": "Eritrea",
    "ESH": "Western Sahara",
    "ETH": "Ethiopia",
    "GAB": "Gabon",
    "GHA": "Ghana",
    "GIN": "Guinea",
    "GMB": "Gambia",
    "GNB": "Guinea-Bissau",
    "GNQ": "Equatorial Guinea",
    "KEN": "Kenya",
    "LBR": "Liberia",
    "LSO": "Lesotho",
    "MDG": "Madagascar",
    "MLI": "Mali",
    "MOZ": "Mozambique",
    "MUS": "Mauritius",
    "MWI": "Malawi",
    "NAM": "Namibia",
    "NER": "Niger",
    "NGA": "Nigeria",
    "RWA": "Rwanda",
    "SEN": "Senegal",
    "SLE": "Sierra Leone",
    "SSD": "South Sudan",
    "STP": "São Tomé and Príncipe",
    "SWZ": "Eswatini",
    "SYC": "Seychelles",
    "TCD": "Chad",
    "TGO": "Togo",
    "TZA": "Tanzania",
    "UGA": "Uganda",
    "ZAF": "South Africa",
    "ZMB": "Zambia",
    "ZWE": "Zimbabwe",
}


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
#: That distinction was first argued here from eyeballing which units looked
#: like cities, farmland or mountains. Measuring it against the Global Aridity
#: Index (see :mod:`satimg.aridity` and ``docs/aridity.md``) refuted most of it:
#: Aleppo is 70% arid, Ninawa 58%, Raymah 97%, Nalut and Al Jabal al Gharbi
#: 100%. A city, a farm or a mountain in an arid climate is still arid, and
#: conflating "where people live" with "what the climate is" was the error.
#:
#: What survives, measured across all 317 admin-1 units:
#:
#: * The rule tracks climate **better** than the prose implied - 94% of the
#:   units it excludes are majority-arid, against a 73% base rate (lift 1.29).
#: * A genuinely non-arid dark set exists, but it is 23 units and it is not
#:   Aleppo or Mosul: it is Darfur, South Kurdufan, Blue Nile and southern
#:   Somalia - the poorest and most conflict-affected non-arid regions.
#: * Saudi Arabia's Ash-Sharqiyah measures 100% arid, so excluding it is
#:   climatically correct even though it holds the oil and industrial core.
#:
#: Eight countries get no derived scope at all, because fewer than eight
#: admin-1 units would remain: ARE, QAT, BHR, KWT, LBN, PSE, DJI and COM.
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
                "nine districts below a x1.69 break at 6.6% lit. Al Jabal al "
                "Gharbi and Nalut were flagged here as populated Nafusa "
                "Mountain districts rather than desert; both measure 100% arid. "
                "Populated and arid are not alternatives"
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
    "EGY": {
        "dark": DesertScope(
            key="dark",
            label="darkest 1",
            gid1=frozenset({"EGY.14_1"}),
            rationale=(
                "Al Wadi al Jadid (New Valley) below a x2.46 break at 2.4% lit "
                "- the Western Desert governorate"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 2",
            gid1=frozenset({"EGY.14_1", "EGY.2_1"}),
            rationale=(
                "adds Al Bahr al Ahmar (Red Sea) below a x1.88 break at 5.9% "
                "lit. Both are genuinely desert"
            ),
            derived=True,
        ),
    },
    "SDN": {
        "dark": DesertScope(
            key="dark",
            label="darkest 1",
            gid1=frozenset({"SDN.8_1"}),
            rationale=("North Darfur below a x2.65 break at 0.2% lit"),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 2",
            gid1=frozenset({"SDN.8_1", "SDN.4_1"}),
            rationale=(
                "adds Central Darfur below a x1.67 break at 0.4% lit. Darfur's "
                "darkness is conflict and displacement as much as aridity"
            ),
            derived=True,
        ),
    },
    "SAU": {
        "dark": DesertScope(
            key="dark",
            label="darkest 5",
            gid1=frozenset({"SAU.12_1", "SAU.3_1", "SAU.8_1", "SAU.4_1", "SAU.13_1"}),
            rationale=(
                "Najran, Al Hudud ash Shamaliyah, Ash-Sharqiyah, Al Jawf, Tabuk "
                "below a x1.91 break at 14.2% lit, with the eight-unit guard "
                "binding. Read with care: Ash-Sharqiyah is the Eastern "
                "Province, Saudi Arabia's oil and industrial heartland - it "
                "scores low because it is enormous and mostly Rub al Khali, not "
                "because it is unlit"
            ),
            derived=True,
        ),
    },
    "YEM": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"YEM.6_1", "YEM.17_1", "YEM.7_1"}),
            rationale=(
                "Al Jawf, Raymah, Al Mahrah below a x3.58 break at 2.1% lit. "
                "Raymah was called 'not desert' here on the grounds that it is "
                "mountainous; it is 97% arid. Altitude is not humidity"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 5",
            gid1=frozenset({"YEM.6_1", "YEM.17_1", "YEM.7_1", "YEM.12_1", "YEM.2_1"}),
            rationale=("adds Hadramawt and Abyan below a x1.31 break at 8.9% lit"),
            derived=True,
        ),
    },
    "OMN": {
        "dark": DesertScope(
            key="dark",
            label="darkest 2",
            gid1=frozenset({"OMN.9_1", "OMN.6_1"}),
            rationale=(
                "Dhofar and Al Wusta below a x1.71 break at 15.9% lit - the Rub "
                "al Khali margin and the empty central coast"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 3",
            gid1=frozenset({"OMN.9_1", "OMN.6_1", "OMN.7_1"}),
            rationale=("adds Ash Sharqiyah North below a x1.43 break at 27.2% lit"),
            derived=True,
        ),
    },
    "IRQ": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"IRQ.5_1", "IRQ.3_1", "IRQ.1_1"}),
            rationale=(
                "An-Najaf, Al-Muthannia, Al-Anbar below a x4.90 break at 10.5% "
                "lit - all desert-dominated, and the sharpest break of the 22"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 4",
            gid1=frozenset({"IRQ.5_1", "IRQ.3_1", "IRQ.1_1", "IRQ.16_1"}),
            rationale=(
                "adds Ninawa below a x1.24 break at 51.6% lit. Described here "
                "as 'NOT a desert'; measurement says otherwise - Ninawa is 58% "
                "arid. Mosul sits in it, but the governorate is majority desert"
            ),
            derived=True,
        ),
    },
    "SYR": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"SYR.9_1", "SYR.7_1", "SYR.3_1"}),
            rationale=(
                "Hims, Dayr Az Zawr, Ar Raqqah below a x1.63 break at 15.9% "
                "lit. These are desert governorates AND the most war-destroyed; "
                "the two causes cannot be separated in this measure"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 4",
            gid1=frozenset({"SYR.9_1", "SYR.7_1", "SYR.3_1", "SYR.2_1"}),
            rationale=(
                "adds Aleppo below a x1.11 break at 25.9% lit. This was "
                "described here as 'unambiguously conflict, not aridity'; "
                "measuring it refuted that - Aleppo governorate is 70% arid by "
                "UNEP class. The city is a small part of a governorate that "
                "reaches east into the steppe"
            ),
            derived=True,
        ),
    },
    "JOR": {
        "dark": DesertScope(
            key="dark",
            label="darkest 2",
            gid1=frozenset({"JOR.8_1", "JOR.10_1"}),
            rationale=(
                "Ma`an and Mafraq below a x3.36 break at 11.9% lit - the "
                "eastern and southern desert"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 3",
            gid1=frozenset({"JOR.8_1", "JOR.10_1", "JOR.3_1"}),
            rationale=(
                "adds Aqaba below a x1.16 break at 40.0% lit; Aqaba is a port "
                "city in a mostly desert governorate"
            ),
            derived=True,
        ),
    },
    "SOM": {
        "dark": DesertScope(
            key="dark",
            label="darkest 3",
            gid1=frozenset({"SOM.2_1", "SOM.9_1", "SOM.7_1"}),
            rationale=(
                "Bakool, Jubbada Dhexe, Gedo below a x1.84 break at 0.1% lit. "
                "Called 'NOT desert' here; only Jubbada Dhexe is (0% arid). "
                "Bakool is 96% arid and Gedo 82%. Somalia's genuinely non-arid "
                "dark regions are Jubbada Dhexe, Bay and Jubbada Hoose"
            ),
            derived=True,
        ),
        "dark_wide": DesertScope(
            key="dark_wide",
            label="darkest 4",
            gid1=frozenset({"SOM.2_1", "SOM.9_1", "SOM.7_1", "SOM.10_1"}),
            rationale=(
                "adds Jubbada Hoose below a x1.32 break at 0.2% lit; same "
                "reading applies"
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
