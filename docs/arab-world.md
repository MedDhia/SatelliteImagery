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

## What the 22 countries show

Theil T over all land pixels, scope `all`, decomposed against each country's
admin-1 units. **Bold** marks a value that rose.

| Country | admin-1 unit | Theil T 1992 | 2022 | between share 1992 | 2022 |
|---|---|---:|---:|---:|---:|
| Somalia | region | 8.503 | 5.674 | 0.420 | 0.205 |
| Mauritania | region | 7.998 | 6.031 | 0.468 | 0.444 |
| Sudan | state | 5.850 | 4.117 | 0.345 | 0.281 |
| Djibouti | region | 5.195 | 3.761 | 0.577 | 0.471 |
| Yemen | governorate | 3.810 | 2.761 | 0.297 | 0.133 |
| Libya | district | 3.627 | 3.440 | 0.327 | **0.341** |
| Algeria | province | 3.570 | 2.713 | 0.337 | **0.416** |
| Morocco | region | 3.492 | 1.618 | 0.156 | **0.205** |
| Comoros † | autonomous island | 3.264 | 2.272 | 0.043 | 0.019 |
| Oman | region | 3.001 | 1.794 | 0.170 | **0.205** |
| Egypt | governorate | 2.983 | 2.396 | 0.490 | **0.492** |
| Saudi Arabia | province | 2.963 | 1.926 | 0.080 | **0.132** |
| Jordan | province | 2.475 | 1.646 | 0.408 | 0.371 |
| Tunisia | governorate | 2.439 | 1.231 | 0.292 | **0.341** |
| Iraq | province | 2.326 | 1.284 | 0.283 | **0.343** |
| Syria | governorate | 1.808 | **1.904** | 0.218 | 0.167 |
| UAE | emirate | 1.425 | 0.827 | 0.142 | **0.144** |
| Kuwait | province | 0.923 | 0.439 | 0.329 | 0.196 |
| Qatar | municipality | 0.794 | 0.314 | 0.162 | 0.121 |
| Lebanon | governorate | 0.665 | 0.327 | 0.407 | 0.313 |
| Palestine † | district | 0.334 | 0.157 | 0.024 | 0.019 |
| Bahrain † | governorate | 0.193 | 0.054 | 0.247 | 0.056 |

† Bahrain (4 units), Comoros (3) and Palestine (2) are too small for a
subnational decomposition to carry much meaning. They are listed for
completeness, not for interpretation.

### Total inequality falls almost everywhere — Syria excepted

Theil T falls in **21 of 22**. The single exception is **Syria**, where it rises
1.808 → 1.904. That is the war: the series records the conflict as pixels going
out, and light that survives is more concentrated than what preceded it. Syria
is also the only country whose national sum of lights ends the period below
where it started.

### The Maghreb pattern does **not** generalize

Working with the Maghreb five, four of them showed total inequality falling
while the share *between* admin-1 units rose — light spreading within regions
faster than between them. That looked like a regional finding.

Across all 22 it is not. The between-share rises in only **9 of 22**:

* **Rises** — Algeria, Iraq, Tunisia, Libya, Morocco, Oman, Saudi Arabia,
  Egypt, UAE.
* **Falls** — Somalia, Djibouti, Yemen, Sudan, Mauritania, Kuwait, Lebanon,
  Jordan, Qatar, Syria, Bahrain, Comoros, Palestine.

The split is not random. The risers are mostly large states with a bright core
and a vast dark interior, where growth concentrated in places already lit. The
fallers are dominated by the poorest countries in the region — Somalia,
Djibouti, Yemen, Sudan, Mauritania — where light arrived in regions that had
almost none, which is exactly what makes a between-group share fall.

So the honest summary is narrower than the Maghreb result suggested: **falling
total inequality is near-universal here; whether it is driven by convergence
between regions or within them depends on the country, and splits roughly along
income and settlement geography.**

### Two more things the numbers say

**Egypt is the most between-concentrated country in the region** (between share
0.490 → 0.492, both years the highest of the 22). Almost all Egyptian light is
in the Nile valley and Delta, and 30 years did not change that.

**Saudi Arabia's between-share nearly doubles** (0.080 → 0.132) off the lowest
base of the large countries. Its light started unusually evenly spread across
provinces and became less so.

Per-country series, decompositions and per-unit contributions are in
[`../results/`](../results/), with a generated data dictionary for every column.

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
