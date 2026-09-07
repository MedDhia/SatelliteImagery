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
#: Derived from GADM's own ENGTYPE by majority, never invented. Three rules,
#: each forced by something GADM actually contains:
#:
#: * **A plurality is not a word.** The mode is used only when it covers more
#:   than half the units. Canada's most common ENGTYPE_2 is Quebec's "Regional
#:   County Municipality" at 93 of 293 (32%), and calling every Canadian census
#:   division that would be wrong; it falls back to the generic title instead.
#:   Applying this threshold changes none of the titles published before it.
#: * **"NA" and alternations mean GADM declined**, so they fall back too -
#:   Madagascar at both levels, Angola's "Municpality|City Council".
#: * **A misspelling is reconciled against GADM itself**, never against our own
#:   guess: Uruguay's "Municipiality" appears 124 times where the same column
#:   spells "Municipality" 14,370 times.
COUNTRY_LEVEL_TITLES: Dict[str, Dict[int, str]] = {
    "AGO": {0: "national", 1: "province"},
    "ALB": {0: "national", 1: "county"},
    "AND": {0: "national", 1: "parish"},
    "ARE": {0: "national", 1: "emirate", 2: "district"},
    "ARG": {0: "national", 1: "province", 2: "department"},
    "ATG": {0: "national", 1: "parish"},
    "AUT": {0: "national", 1: "state", 2: "district"},
    "BDI": {0: "national", 1: "province", 2: "commune"},
    "BEL": {0: "national", 1: "region"},
    "BEN": {0: "national", 1: "department", 2: "commune"},
    "BFA": {0: "national", 1: "region", 2: "province"},
    "BGR": {0: "national", 1: "province", 2: "municipality"},
    "BHR": {0: "national", 1: "governorate"},
    "BHS": {0: "national", 1: "district"},
    "BIH": {0: "national", 1: "entity", 2: "canton"},
    "BLR": {0: "national", 1: "region", 2: "district"},
    "BLZ": {0: "national", 1: "district"},
    "BOL": {0: "national", 1: "department", 2: "province"},
    "BRA": {0: "national", 1: "state", 2: "municipality"},
    "BRB": {0: "national", 1: "parish"},
    "BWA": {0: "national", 1: "district", 2: "sub-district"},
    "CAF": {0: "national", 1: "prefecture", 2: "sub-prefecture"},
    "CAN": {0: "national", 1: "province"},
    "CHE": {0: "national", 1: "canton", 2: "district"},
    "CHL": {0: "national", 1: "region", 2: "province"},
    "CIV": {0: "national", 1: "district", 2: "region"},
    "CMR": {0: "national", 1: "region", 2: "department"},
    "COD": {0: "national", 1: "province", 2: "territory"},
    "COG": {0: "national", 1: "region", 2: "district"},
    "COL": {0: "national", 1: "department", 2: "municipality"},
    "COM": {0: "national", 1: "autonomous island"},
    "CPV": {0: "national", 1: "county"},
    "CRI": {0: "national", 1: "province", 2: "canton"},
    "CUB": {0: "national", 1: "province", 2: "municipality"},
    "CYP": {0: "national", 1: "district"},
    "CZE": {0: "national", 1: "region", 2: "district"},
    "DEU": {0: "national", 1: "state", 2: "district"},
    "DJI": {0: "national", 1: "region"},
    "DMA": {0: "national", 1: "parish"},
    "DNK": {0: "national", 1: "region", 2: "municipality"},
    "DOM": {0: "national", 1: "province", 2: "municipality"},
    "DZA": {0: "national", 1: "province", 2: "commune"},
    "ECU": {0: "national", 1: "province", 2: "canton"},
    "EGY": {0: "national", 1: "governorate", 2: "subdivision"},
    "ERI": {0: "national", 1: "region", 2: "district"},
    "ESH": {0: "national", 1: "province"},
    "ESP": {0: "national", 1: "autonomous community", 2: "province"},
    "EST": {0: "national", 1: "county", 2: "parish"},
    "ETH": {0: "national", 1: "state", 2: "zone"},
    "FIN": {0: "national", 1: "province", 2: "region"},
    "FRA": {0: "national", 1: "region", 2: "department"},
    "GAB": {0: "national", 1: "province", 2: "department"},
    "GBR": {0: "national", 1: "constituent country"},
    "GHA": {0: "national", 1: "region", 2: "district"},
    "GIN": {0: "national", 1: "region", 2: "prefecture"},
    "GMB": {0: "national", 1: "division", 2: "district"},
    "GNB": {0: "national", 1: "region", 2: "sector"},
    "GNQ": {0: "national", 1: "province"},
    "GRC": {0: "national", 1: "decentralized administration", 2: "region"},
    "GRD": {0: "national", 1: "parish"},
    "GTM": {0: "national", 1: "department", 2: "municipality"},
    "GUY": {0: "national", 1: "region", 2: "neighbourhood democratic"},
    "HND": {0: "national", 1: "department", 2: "municipality"},
    "HRV": {0: "national", 1: "county", 2: "commune"},
    "HTI": {0: "national", 1: "department", 2: "district"},
    "HUN": {0: "national", 1: "county", 2: "subregion"},
    "IRL": {0: "national", 1: "county", 2: "municipal district"},
    "IRQ": {0: "national", 1: "province", 2: "district"},
    "ISL": {0: "national", 1: "region", 2: "municipality"},
    "ITA": {0: "national", 1: "region", 2: "province"},
    "JAM": {0: "national", 1: "parish"},
    "JOR": {0: "national", 1: "province", 2: "sub-province"},
    "KEN": {0: "national", 1: "county", 2: "constituency"},
    "KNA": {0: "national", 1: "parish"},
    "KWT": {0: "national", 1: "province"},
    "LBN": {0: "national", 1: "governorate", 2: "district"},
    "LBR": {0: "national", 1: "county", 2: "district"},
    "LBY": {0: "national", 1: "district"},
    "LCA": {0: "national", 1: "quarter"},
    "LIE": {0: "national", 1: "commune"},
    "LSO": {0: "national", 1: "district"},
    "LTU": {0: "national", 1: "county", 2: "district municipality"},
    "LUX": {0: "national", 1: "district", 2: "canton"},
    "LVA": {0: "national", 1: "province", 2: "district"},
    "MAR": {0: "national", 1: "region", 2: "province"},
    "MDA": {0: "national", 1: "district"},
    "MDG": {0: "national"},
    "MEX": {0: "national", 1: "state", 2: "municipality"},
    "MKD": {0: "national", 1: "municipality"},
    "MLI": {0: "national", 1: "region", 2: "circle"},
    "MLT": {0: "national", 1: "region", 2: "local council"},
    "MNE": {0: "national", 1: "municipality"},
    "MOZ": {0: "national", 1: "province", 2: "district"},
    "MRT": {0: "national", 1: "region", 2: "department"},
    "MUS": {0: "national", 1: "district"},
    "MWI": {0: "national", 1: "district", 2: "traditional authority"},
    "NAM": {0: "national", 1: "region", 2: "constituency"},
    "NER": {0: "national", 1: "department", 2: "arrondissement"},
    "NGA": {0: "national", 1: "state", 2: "local authority"},
    "NIC": {0: "national", 1: "department", 2: "municipality"},
    "NLD": {0: "national", 1: "province", 2: "municipality"},
    "NOR": {0: "national", 1: "county", 2: "municipality"},
    "OMN": {0: "national", 1: "region", 2: "province"},
    "PAN": {0: "national", 1: "province", 2: "district"},
    "PER": {0: "national", 1: "region", 2: "province"},
    "POL": {0: "national", 1: "voivodeship", 2: "county"},
    "PRT": {0: "national", 1: "district", 2: "municipality"},
    "PRY": {0: "national", 1: "department", 2: "district"},
    "PSE": {0: "national", 1: "district", 2: "governorate"},
    "QAT": {0: "national", 1: "municipality"},
    "ROU": {0: "national", 1: "county", 2: "commune"},
    "RWA": {0: "national", 1: "province", 2: "district"},
    "SAU": {0: "national", 1: "province", 2: "governorate"},
    "SDN": {0: "national", 1: "state", 2: "district"},
    "SEN": {0: "national", 1: "region", 2: "department"},
    "SLE": {0: "national", 1: "province", 2: "district"},
    "SLV": {0: "national", 1: "department", 2: "municipality"},
    "SMR": {0: "national", 1: "municipality"},
    "SOM": {0: "national", 1: "region", 2: "district"},
    "SRB": {0: "national", 1: "district"},
    "SSD": {0: "national", 1: "state", 2: "district"},
    "STP": {0: "national", 1: "municipality"},
    "SUR": {0: "national", 1: "district", 2: "ressort"},
    "SVK": {0: "national", 1: "region", 2: "district"},
    "SVN": {0: "national", 1: "statistical region"},
    "SWE": {0: "national", 1: "county", 2: "municipality"},
    "SWZ": {0: "national", 1: "district", 2: "constituency"},
    "SYC": {0: "national", 1: "district"},
    "SYR": {0: "national", 1: "governorate", 2: "district"},
    "TCD": {0: "national", 1: "region", 2: "department"},
    "TGO": {0: "national", 1: "region", 2: "prefecture"},
    "THA": {0: "national", 1: "province", 2: "district"},
    "TTO": {0: "national", 1: "region"},
    "TUN": {0: "national", 1: "governorate", 2: "delegation"},
    "TZA": {0: "national", 1: "region", 2: "district"},
    "UGA": {0: "national", 1: "district", 2: "county"},
    "UKR": {0: "national", 1: "region", 2: "district"},
    "URY": {0: "national", 1: "department", 2: "municipality"},
    "USA": {0: "national", 1: "state", 2: "county"},
    "VCT": {0: "national", 1: "parish"},
    "VEN": {0: "national", 1: "state", 2: "municipality"},
    "XKO": {0: "national", 1: "district"},
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
#: Countries where GADM 4.1 ships no ADM_2 layer at all, so the analysis stops
#: at admin-1 and there is no nested three-way split. Note this is about a
#: **missing layer**, not a missing name: Canada has 293 admin-2 units and is
#: deliberately absent here, it simply has no reliable word for them (see
#: COUNTRY_LEVEL_TITLES).
LEVELS_AVAILABLE: Dict[str, tuple] = {
    iso3: (0, 1)
    for iso3 in (
        # Arab League
        "BHR",
        "KWT",
        "LBY",
        "QAT",
        "COM",
        # Africa
        "CPV",
        "ESH",
        "LSO",
        "MUS",
        "SYC",
        # Caribbean and Central America
        "ATG",
        "BHS",
        "BLZ",
        "BRB",
        "DMA",
        "GRD",
        "JAM",
        "KNA",
        "LCA",
        "TTO",
        "VCT",
        # Europe
        "AND",
        "CYP",
        "LIE",
        "MDA",
        "MNE",
        "MKD",
        "SMR",
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
#: The Americas, split north and south rather than pooled as one. The two have
#: very different income spreads, and a pool's darkness cut is a median over its
#: own members - pooling Canada with Haiti would produce a cut that describes
#: neither. Central America and the Caribbean sit with the north by the usual
#: convention.
NORTH_AMERICA = (
    "CAN",
    "USA",
    "MEX",
    "BLZ",
    "CRI",
    "SLV",
    "GTM",
    "HND",
    "NIC",
    "PAN",
    "ATG",
    "BHS",
    "BRB",
    "CUB",
    "DMA",
    "DOM",
    "GRD",
    "HTI",
    "JAM",
    "KNA",
    "LCA",
    "VCT",
    "TTO",
)

SOUTH_AMERICA = (
    "ARG",
    "BOL",
    "BRA",
    "CHL",
    "COL",
    "ECU",
    "GUY",
    "PRY",
    "PER",
    "SUR",
    "URY",
    "VEN",
)

#: Europe, as GADM codes it: 43 countries.
#:
#: **Monaco and the Vatican are absent from GADM 4.1 entirely** - there is no
#: MCO or VAT feature at any level - so they cannot be analysed here at all.
#: That is a gap in the source, not a choice, and it is stated rather than left
#: to be noticed as two missing rows.
#:
#: **Russia is excluded deliberately.** Roughly three quarters of its area is
#: Asian, so it would dominate a European pool's median while being mostly not
#: in Europe. It also wraps the antimeridian, as the United States does, but
#: the Alaskan remedy does not transfer: cropping at 180 would drop 114,686 km2
#: of Chukotka - larger than Iceland, and about 15% of that federal subject -
#: against the 2,122 km2 of near-unlit Aleutian rock the American crop costs.
#: Including Russia would mean either that loss or a two-window stitch, and
#: neither is worth it for a country that is barely European.
#:
#: Kosovo appears as GADM's XKO on the same footing as Palestine and Western
#: Sahara elsewhere here: GADM's coding of the boundary set in use, not a
#: position on status.
EUROPE = (
    "ALB",  # Albania
    "AND",  # Andorra
    "AUT",  # Austria
    "BLR",  # Belarus
    "BEL",  # Belgium
    "BIH",  # Bosnia and Herzegovina
    "BGR",  # Bulgaria
    "HRV",  # Croatia
    "CYP",  # Cyprus
    "CZE",  # Czechia
    "DNK",  # Denmark
    "EST",  # Estonia
    "FIN",  # Finland
    "FRA",  # France
    "DEU",  # Germany
    "GRC",  # Greece
    "HUN",  # Hungary
    "ISL",  # Iceland
    "IRL",  # Ireland
    "ITA",  # Italy
    "LVA",  # Latvia
    "LIE",  # Liechtenstein
    "LTU",  # Lithuania
    "LUX",  # Luxembourg
    "MLT",  # Malta
    "MDA",  # Moldova
    "MNE",  # Montenegro
    "NLD",  # Netherlands
    "MKD",  # North Macedonia
    "NOR",  # Norway
    "POL",  # Poland
    "PRT",  # Portugal
    "ROU",  # Romania
    "SMR",  # San Marino
    "SRB",  # Serbia
    "SVK",  # Slovakia
    "SVN",  # Slovenia
    "ESP",  # Spain
    "SWE",  # Sweden
    "CHE",  # Switzerland
    "UKR",  # Ukraine
    "GBR",  # United Kingdom
    "XKO",  # Kosovo
)

COUNTRIES = (
    *ARAB_LEAGUE,
    "THA",
    *(iso3 for iso3 in AFRICA if iso3 not in ARAB_LEAGUE),
    *NORTH_AMERICA,
    *SOUTH_AMERICA,
    *EUROPE,
)

#: Named comparison pools. Each owns its own cross-country artefacts, and a
#: country may sit in more than one - ten African states are also Arab League
#: members and appear in both, each time against a different set of neighbours.
POOLS: Dict[str, tuple] = {
    "arab-league": ARAB_LEAGUE,
    "africa": AFRICA,
    "north-america": NORTH_AMERICA,
    "south-america": SOUTH_AMERICA,
    "europe": EUROPE,
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
    "AGO": "Angola",
    "ALB": "Albania",
    "AND": "Andorra",
    "ARE": "United Arab Emirates",
    "ARG": "Argentina",
    "ATG": "Antigua and Barbuda",
    "AUT": "Austria",
    "BDI": "Burundi",
    "BEL": "Belgium",
    "BEN": "Benin",
    "BFA": "Burkina Faso",
    "BGR": "Bulgaria",
    "BHR": "Bahrain",
    "BHS": "Bahamas",
    "BIH": "Bosnia and Herzegovina",
    "BLR": "Belarus",
    "BLZ": "Belize",
    "BOL": "Bolivia",
    "BRA": "Brazil",
    "BRB": "Barbados",
    "BWA": "Botswana",
    "CAF": "Central African Republic",
    "CAN": "Canada",
    "CHE": "Switzerland",
    "CHL": "Chile",
    "CIV": "Côte d'Ivoire",
    "CMR": "Cameroon",
    "COD": "DR Congo",
    "COG": "Republic of the Congo",
    "COL": "Colombia",
    "COM": "Comoros",
    "CPV": "Cabo Verde",
    "CRI": "Costa Rica",
    "CUB": "Cuba",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DEU": "Germany",
    "DJI": "Djibouti",
    "DMA": "Dominica",
    "DNK": "Denmark",
    "DOM": "Dominican Republic",
    "DZA": "Algeria",
    "ECU": "Ecuador",
    "EGY": "Egypt",
    "ERI": "Eritrea",
    "ESH": "Western Sahara",
    "ESP": "Spain",
    "EST": "Estonia",
    "ETH": "Ethiopia",
    "FIN": "Finland",
    "FRA": "France",
    "GAB": "Gabon",
    "GBR": "United Kingdom",
    "GHA": "Ghana",
    "GIN": "Guinea",
    "GMB": "Gambia",
    "GNB": "Guinea-Bissau",
    "GNQ": "Equatorial Guinea",
    "GRC": "Greece",
    "GRD": "Grenada",
    "GTM": "Guatemala",
    "GUY": "Guyana",
    "HND": "Honduras",
    "HRV": "Croatia",
    "HTI": "Haiti",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "IRQ": "Iraq",
    "ISL": "Iceland",
    "ITA": "Italy",
    "JAM": "Jamaica",
    "JOR": "Jordan",
    "KEN": "Kenya",
    "KNA": "Saint Kitts and Nevis",
    "KWT": "Kuwait",
    "LBN": "Lebanon",
    "LBR": "Liberia",
    "LBY": "Libya",
    "LCA": "Saint Lucia",
    "LIE": "Liechtenstein",
    "LSO": "Lesotho",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "LVA": "Latvia",
    "MAR": "Morocco",
    "MDA": "Moldova",
    "MDG": "Madagascar",
    "MEX": "Mexico",
    "MKD": "North Macedonia",
    "MLI": "Mali",
    "MLT": "Malta",
    "MNE": "Montenegro",
    "MOZ": "Mozambique",
    "MRT": "Mauritania",
    "MUS": "Mauritius",
    "MWI": "Malawi",
    "NAM": "Namibia",
    "NER": "Niger",
    "NGA": "Nigeria",
    "NIC": "Nicaragua",
    "NLD": "Netherlands",
    "NOR": "Norway",
    "OMN": "Oman",
    "PAN": "Panama",
    "PER": "Peru",
    "POL": "Poland",
    "PRT": "Portugal",
    "PRY": "Paraguay",
    "PSE": "Palestine",
    "QAT": "Qatar",
    "ROU": "Romania",
    "RWA": "Rwanda",
    "SAU": "Saudi Arabia",
    "SDN": "Sudan",
    "SEN": "Senegal",
    "SLE": "Sierra Leone",
    "SLV": "El Salvador",
    "SMR": "San Marino",
    "SOM": "Somalia",
    "SRB": "Serbia",
    "SSD": "South Sudan",
    "STP": "São Tomé and Príncipe",
    "SUR": "Suriname",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "SWE": "Sweden",
    "SWZ": "Eswatini",
    "SYC": "Seychelles",
    "SYR": "Syria",
    "TCD": "Chad",
    "TGO": "Togo",
    "THA": "Thailand",
    "TTO": "Trinidad and Tobago",
    "TUN": "Tunisia",
    "TZA": "Tanzania",
    "UGA": "Uganda",
    "UKR": "Ukraine",
    "URY": "Uruguay",
    "USA": "United States",
    "VCT": "Saint Vincent and the Grenadines",
    "VEN": "Venezuela",
    "XKO": "Kosovo",
    "YEM": "Yemen",
    "ZAF": "South Africa",
    "ZMB": "Zambia",
    "ZWE": "Zimbabwe",
}


def level_title(iso3: str, level: int) -> str:
    """What ``iso3`` calls this admin level."""
    titles = COUNTRY_LEVEL_TITLES.get(iso3.upper(), GENERIC_LEVEL_TITLES)
    return titles.get(level, GENERIC_LEVEL_TITLES[level])


#: Levels GADM *does* provide but this repository does not analyse, and why.
#:
#: Kept strictly apart from `LEVELS_AVAILABLE`, which records what GADM
#: lacks. Conflating the two would put a false statement about the source
#: data into a table other people read: it would say GADM has no Brazilian
#: municipalities, when GADM has 5,572 of them.
#:
#: * **BRA** — 5,572 municipalities, the largest ADM_2 set here by a wide
#:   margin: sixteen times Chile's 346, and nearly four times Algeria's 1,504,
#:   which was the previous ceiling. Burning that many polygons onto Brazil's
#:   21-megapixel frame, for each of 31 years, for each of four choropleth
#:   variants, is the most expensive computation in the pipeline — it ran for
#:   over half an hour on a single variant without emitting a file. It was cut
#:   by choice, not by capability: the state-level analysis is complete, and
#:   deleting this entry plus re-running the country restores the municipality
#:   layer.
LEVELS_NOT_ANALYSED: Dict[str, tuple] = {
    "BRA": (2,),
    "ROU": (2,),
}


def gadm_levels(iso3: str) -> tuple:
    """Admin levels GADM actually provides for a country.

    What the *source* has, irrespective of what this repository does with it.
    Use `available_levels` for the analysed set.
    """
    return LEVELS_AVAILABLE.get(iso3.upper(), COUNTRY_LEVELS)


def available_levels(iso3: str) -> tuple:
    """Admin levels this repository analyses for a country.

    GADM's levels minus any this repository declines to analyse. Everything
    downstream — the figures, the catalogues, the decomposition — keys off
    this, so a level dropped here leaves no half-built artefacts behind.
    """
    skip = LEVELS_NOT_ANALYSED.get(iso3.upper(), ())
    return tuple(lv for lv in gadm_levels(iso3) if lv not in skip)


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
