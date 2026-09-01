# Nighttime-light inequality across the Maghreb, 1992–2022

Five countries — Morocco, Algeria, Tunisia, Libya and Mauritania, the Arab
Maghreb Union — each extracted from the LRCC-DVNL global grid at national and
subnational levels, with Gini, Theil T and Theil L series and an additive
between/within decomposition of Theil.

Tunisia came first and is documented in detail in [`tunisia.md`](tunisia.md);
this page covers what changes when the same treatment is applied to the rest.

> **Read [`lrcc-dvnl.md`](lrcc-dvnl.md) before quoting any number here.** The
> source series forbids year-on-year decreases by construction, so a falling
> Gini is partly imposed rather than observed, and 2014 is a sensor handover.

---

## What each country got

| | Morocco | Algeria | Tunisia | Libya | Mauritania |
|---|---|---|---|---|---|
| ISO3 | MAR | DZA | TUN | LBY | MRT |
| admin-1 | 15 regions | 48 wilayas | 24 governorates | 22 districts | 13 regions |
| admin-2 | 54 provinces | 1 504 dairas | 268 delegations | **none** | 44 departments |
| land pixels | 413 507 | 2 308 015 | 154 885 | 1 616 024 | 1 040 998 |
| window | 1106×976 | 1892×2181 | 368×856 | 1487×1659 | 1144×1561 |

Land-pixel counts are measured from the rasterised GADM national boundary at
1 km in EPSG:8857; each is within a percent or two of the country's published
land area, which is the check that the clip is right.

### Libya has no admin-2 layer

GADM 4.1 ships no `ADM_2` for Libya. Its analysis therefore runs at levels 0
and 1 only, and the nested three-way split (pixel → admin-2 → admin-1)
collapses to the two-way pixel → admin-1 split. Nothing downstream fakes it:
`satimg.regions.available_levels("LBY")` returns `(0, 1)`, the figure and result
catalogues emit no admin-2 entries, and the decomposition writes no `nested`
rows. Western Sahara (ESH) has the same gap and is not included here at all.

---

## Scopes: what "excluding the desert" can and cannot mean

Tunisia's original analysis used two hand-picked exclusions, `narrow` and
`wide`, chosen by judging which governorates are Saharan. That does not scale:
in Algeria, Libya and Mauritania most of the country *is* Sahara, and hand-
picking four more sets would be four more undocumented judgement calls.

So the exclusions are now **derived from the light itself**, by
[`scripts/derive_low_light_scopes.py`](../scripts/derive_low_light_scopes.py):

> Sort a country's admin-1 units by lit share in 2022. Consider every gap in
> the lower half of that ranking. Cut at the largest relative gap that still
> leaves at least 8 units standing. `dark` is that cut; `dark_wide` is the
> largest remaining gap above it.

The output is frozen into `satimg/regions.py` rather than recomputed at run
time, for the same reason the dataset manifest is committed: a scope that
silently re-derives itself is a scope no reviewer ever sees change.

### The validity check

On Tunisia the rule cuts at a ×2.37 break at 17.7% lit and selects
**Tataouine, Kebili and Tozeur** — *exactly* the three governorates that were
hand-picked as `narrow`. That agreement is the evidence the rule is finding
real geography rather than an artefact of sorting. Because the two sets are
identical, Tunisia's derived `dark` is dropped rather than emitted as a
duplicate series.

### Where it does not find a desert

The rule finds a **discontinuity in observed light**, which is not the same
thing as a desert, and the gap shows in three places. These are stated in each
scope's `rationale` in the code, not hidden:

| Country | Scope | What it actually selects |
|---|---|---|
| TUN | `dark_wide` | adds Médenine, Gabès and **Siliana** — Siliana is a northwestern interior governorate, not desert. The hand-picked `wide` takes Gafsa instead. |
| DZA | `dark` | only 4 of 48 wilayas. Under-inclusive: Illizi, Ghardaïa, Ouargla and El Oued are Saharan but carry oil-town and oasis light. |
| LBY | `dark` | Al Kufrah alone. Murzuq, Ghat and Al Jufrah are equally Saharan but sit above the break. |
| LBY | `dark_wide` | nine districts, but includes **Al Jabal al Gharbi** and **Nalut** — populated Nafusa Mountain districts. |
| MRT | `dark_wide` | the guard binds. Mauritania has 13 regions and Nouakchott alone is 79% lit against a national median of 0.9%, so no deeper cut can leave enough units to measure. |

Morocco is the cleanest case: a ×4.01 break — the sharpest of the five —
separates Laâyoune-Boujdour-Sakia El Hamra and Guelmim-Es-Semara from the rest.

**Practical guidance:** treat `dark`/`dark_wide` as *low-light exclusions*,
which is what they are named and what they measure. For Tunisia specifically,
`narrow` and `wide` remain available as the geographic definitions.

---

## What the five countries show

Theil T over all land pixels, scope `all`, decomposed against each country's
admin-1 units:

| | Theil T 1992 | 2022 | between-admin-1 share 1992 | 2022 |
|---|---:|---:|---:|---:|
| Morocco | 3.492 | 1.618 | 0.156 | **0.205** |
| Algeria | 3.570 | 2.713 | 0.337 | **0.416** |
| Tunisia | 2.439 | 1.231 | 0.292 | **0.341** |
| Libya | 3.627 | 3.440 | 0.327 | **0.341** |
| Mauritania | 7.998 | 6.031 | 0.468 | 0.444 |

**The Tunisian pattern is regional, not Tunisian.** In four of the five, total
inequality falls while the share of it that lies *between* admin-1 units
**rises**. Light spread out within regions faster than it spread between them,
so reading the falling total as regional convergence gets the sign of the
interesting part backwards.

Mauritania is the exception on both counts: its between share edges down, and
its total is more than twice anyone else's. Both come from the same fact — one
region, Nouakchott, holds essentially all of the country's light, so the
distribution is dominated by a single unit rather than by a gradient across
units. It is the country where these indices should be read most cautiously.

Libya's total barely moves (3.627 → 3.440) against Morocco's near-halving. Note
that the source series cannot represent decline, so a country whose light
actually contracted over this period would look flat here rather than falling;
Libya's flatness is a floor effect as much as a finding.

Per-country series, decompositions and per-unit contributions are in
[`../results/`](../results/), with a generated data dictionary for every column.

---

## Reproducing

```bash
pip install -e ".[dev]"
satimg lrcc-dvnl download
satimg boundaries fetch
for ISO in MAR DZA TUN LBY MRT; do
  satimg lrcc-dvnl extract    --country "$ISO" --levels 0,1,2
  satimg lrcc-dvnl choropleth --country "$ISO" --levels 1,2
  satimg lrcc-dvnl inequality --country "$ISO"
done
satimg figures build
satimg results build
```

Outputs land under gitignored `data/regions/<ISO3>/`; the committed subsets are
[`figures/`](../figures/) and [`results/`](../results/).

---

## Licensing

Unchanged from the rest of the project: boundaries are GADM 4.1, which is
non-commercial with no redistribution, so the figures and tables are carved out
of the repository's MIT licence by [`../figures/NOTICE.md`](../figures/NOTICE.md).
