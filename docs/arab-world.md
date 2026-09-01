# Nighttime-light inequality across the Arab world, 1992–2022

All 22 Arab League members extracted from the LRCC-DVNL global grid at national
and subnational levels, with Gini, Theil T and Theil L series and an additive
between/within decomposition of Theil.

This supersedes the earlier Maghreb-only write-up. Tunisia, done first and in
most detail, keeps its own page: [`tunisia.md`](tunisia.md).

> **Read [`lrcc-dvnl.md`](lrcc-dvnl.md) before quoting any number here.** In
> this series a lit pixel's DN never steps down while it stays lit: every
> decrease is a pixel going out entirely. Gradual dimming is invisible;
> extinction is not. That distinction matters more in this region than
> anywhere — several of these countries went through wars in the window, and
> the series registers those as pixels extinguished rather than dimmed. 2014
> is also a sensor handover.

---

## Coverage

| Country | ISO3 | admin-1 | admin-2 | land px | scopes |
|---|---|---|---|---:|---|
| Algeria | DZA | 48 provinces | 1,504 communes | 2,308,015 | `all`, `dark`, `dark_wide` |
| Saudi Arabia | SAU | 13 provinces | 147 governorates | 1,922,985 | `all`, `dark` |
| Sudan | SDN | 18 states | 80 districts | 1,872,206 | `all`, `dark`, `dark_wide` |
| Libya | LBY | 22 districts | **none** | 1,616,024 | `all`, `dark`, `dark_wide` |
| Mauritania | MRT | 13 regions | 44 departments | 1,040,998 | `all`, `dark`, `dark_wide` |
| Egypt | EGY | 27 governorates | 343 subdivisions | 983,814 | `all`, `dark`, `dark_wide` |
| Somalia | SOM | 18 regions | 74 districts | 633,509 | `all`, `dark`, `dark_wide` |
| Yemen | YEM | 21 governorates | 332 districts | 452,188 | `all`, `dark`, `dark_wide` |
| Iraq | IRQ | 18 provinces | 102 districts | 436,464 | `all`, `dark`, `dark_wide` |
| Morocco | MAR | 15 regions | 54 provinces | 413,507 | `all`, `dark`, `dark_wide` |
| Oman | OMN | 11 regions | 49 provinces | 309,155 | `all`, `dark`, `dark_wide` |
| Syria | SYR | 14 governorates | 60 districts | 186,929 | `all`, `dark`, `dark_wide` |
| Tunisia | TUN | 24 governorates | 268 delegations | 154,885 | `all`, `narrow`, `wide`, `dark_wide` |
| Jordan | JOR | 12 provinces | 52 sub-provinces | 89,197 | `all`, `dark`, `dark_wide` |
| United Arab Emirates | ARE | 7 emirates | 195 districts | 71,076 | `all` |
| Djibouti | DJI | 6 regions | 21 admin-2 units | 22,356 | `all` |
| Kuwait | KWT | 6 provinces | **none** | 17,432 | `all` |
| Qatar | QAT | 7 municipalitys | **none** | 11,582 | `all` |
| Lebanon | LBN | 8 governorates | 30 districts | 10,252 | `all` |
| Palestine | PSE | 2 districts | 16 governorates | 6,220 | `all` |
| Comoros | COM | 3 autonomous islands | **none** | 1,678 | `all` |
| Bahrain | BHR | 4 governorates | **none** | 717 | `all` |

**Total: 12,561,189 land pixels** across 22 countries.

Land-pixel counts are measured from the rasterised GADM national boundary at
1 km in EPSG:8857. Palestine appears with GADM's own coding of the West Bank
and Gaza; that is the boundary set in use, not a position on its status.

### Level names come from GADM, not from us

Each country's admin levels are labelled with GADM's own `ENGTYPE_1` and
`ENGTYPE_2` values. This is not fussiness: the labels were hand-written for the
Maghreb first, and that got **Algeria wrong** — its ADM_2 units are *communes*
(GADM labels 1 345 of 1 504 that way), not the coarser *daïras*, and the wrong
word was rendered onto every Algerian admin-2 map before it was checked.

Where GADM records no type at all — Djibouti's `ENGTYPE_2` is literally `"NA"`
— a generic label applies rather than a plausible-sounding invention.

### Five countries have no admin-2 layer

GADM 4.1 ships no `ADM_2` for **Libya, Bahrain, Comoros, Kuwait or Qatar**.
Their analyses run at levels 0 and 1 only, and the nested three-way split
(pixel → admin-2 → admin-1) collapses to the two-way pixel → admin-1 split.
Nothing downstream fakes it: no admin-2 figure directories, no admin-2 zonal
table, no `nested` decomposition rows.

### Very small countries

Bahrain covers 717 land pixels across 4 units, Comoros 1 678 across 3, and
Palestine 6 220 across 2. A subnational inequality index over two to four
observations is close to meaningless. These are computed and published rather
than silently dropped, so the choice is visible — but do not read those rows
the way you would read Algeria's.

---

## Scopes: what the low-light rule does and does not find

Exclusion scopes are derived from the light itself by
[`scripts/derive_low_light_scopes.py`](../scripts/derive_low_light_scopes.py):

> Sort a country's admin-1 units by lit share in 2022. Consider every gap in
> the lower half of that ranking. Cut at the largest relative gap that still
> leaves at least 8 units standing. `dark` is that cut; `dark_wide` is the
> largest remaining gap above it.

The output is frozen into `satimg/regions.py` rather than recomputed at run
time, for the same reason the dataset manifest is committed.

**The validity check:** on Tunisia the rule selects Tataouine, Kebili and
Tozeur — *exactly* the three governorates hand-picked as `narrow` before the
rule existed. That agreement is the evidence it finds real geography.

### Where it finds something other than desert

At Maghreb scale the mismatches were minor. Across 22 countries they are not,
and the scope names say `dark`, never `desert`, for this reason:

| Country | What the cut actually selects |
|---|---|
| **Syria** | Hims, Dayr Az Zawr, Ar Raqqah are desert governorates *and* the most war-destroyed; the causes cannot be separated here. `dark_wide` adds **Aleppo** — Syria's largest city. Unambiguously conflict. |
| **Iraq** | The sharpest break of all 22 (×4.90) lands on genuinely desert governorates — but `dark_wide` adds **Ninawa**, i.e. Mosul. War damage. |
| **Somalia** | Bakool, Jubbada Dhexe and Gedo are southern *riverine farmland*. Their darkness is poverty and conflict, not aridity. |
| **Saudi Arabia** | Excludes **Ash-Sharqīyah**, the oil and industrial heartland, because lit *share* penalises a province that is mostly Rub' al Khali. The guard also binds, so there is no second scope. |
| **Sudan** | North and Central Darfur — arid, but their darkness is also displacement. |
| **Yemen** | `dark` includes **Raymah**, a small mountainous governorate. Poverty, not desert. |
| Egypt, Jordan, Oman, Morocco, Tunisia | Clean. New Valley, Red Sea, Ma'an, Mafraq, Dhofar, Al Wusta and the Saharan trio are all genuinely desert. |

Every one of these readings is recorded in the scope's `rationale` in
`regions.py`, and tests assert the conflict-related ones so that a later edit
cannot quietly recast them as desert sets.

**Eight countries get no derived scope at all** — ARE, QAT, BHR, KWT, LBN, PSE,
DJI and COM — because fewer than eight admin-1 units would remain. They run
with `all` only. That is the guard working, not a gap.

---

## Reproducing

```bash
pip install -e ".[dev]"
satimg lrcc-dvnl download
satimg boundaries fetch
python - <<'PY'
from satimg.regions import ARAB_LEAGUE; print(" ".join(ARAB_LEAGUE))
PY
# then, per country:
satimg lrcc-dvnl extract     --country "$ISO" --levels 0,1,2
satimg lrcc-dvnl choropleth  --country "$ISO" --levels 1,2
satimg lrcc-dvnl inequality  --country "$ISO"
satimg figures build
satimg results build
```

Outputs land under gitignored `data/regions/<ISO3>/`; the committed subsets are
[`figures/`](../figures/) and [`results/`](../results/).

---

## Licensing

Boundaries are GADM 4.1, which is non-commercial with no redistribution, so the
figures and tables are carved out of the repository's MIT licence by
[`../figures/NOTICE.md`](../figures/NOTICE.md).
