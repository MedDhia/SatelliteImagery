# Thailand: the extensive margin, almost alone

Thailand is the first country here that is not an Arab League member, and it is
analysed **outside the cross-country pool** rather than as a 23rd row in it.

That is not tidiness. `results/aridity_vs_light.csv` cuts its `dark_2022` column
at the **cross-country median** of mean DN, so widening the pool would move the
median and rewrite `dark_2022`, `cell` and the 6/13/23 nesting for all 317 units
already published — findings that are about the Arab world and should stay
answerable in those terms. So `regions.ARAB_LEAGUE` remains the thing being
compared, `regions.COUNTRIES` is everything analysed, and Thailand is in the
second only. Its own numbers below are complete; it simply does not appear in
[`arab-world.md`](arab-world.md)'s tables or in
[`aridity.md`](aridity.md)'s pooled join.

```bash
satimg lrcc-dvnl extract    --country THA --levels 0,1,2
satimg lrcc-dvnl choropleth --country THA --levels 1,2
satimg lrcc-dvnl inequality --country THA
satimg aridity units        --country THA
```

## The three levels

| Level | GADM layer | Units | Thai name |
|---|---|---|---|
| national | `ADM_0` | 1 | Thailand |
| provincial | `ADM_1` | 77 | *changwat* — province |
| district | `ADM_2` | 928 | *amphoe* — district |

Both level names come from GADM's own `ENGTYPE` fields, not from us: `ENGTYPE_1`
is uniformly "Province"; `ENGTYPE_2` is "District" for 845 of 928, which is what
the majority rule reports. The remainder is 81 "Minor district" and **2 "Water
body"** — see the caveats.

513 886 land pixels, between Egypt's and Morocco's in size.

## The headline: a falling total that is not convergence

| | 1992 | 2022 |
|---|---:|---:|
| Gini (all land pixels) | 0.9489 | 0.6592 |
| Theil T (all land pixels) | 2.7142 | 0.8052 |
| **Theil T (lit pixels only)** | **0.4479** | **0.4701** |
| lit share of land pixels | 10.37% | **71.52%** |
| sum of lights | 670 712 | 4 655 037 |
| between-province share of Theil T | 0.3827 | 0.2762 |

Total nighttime-light inequality falls by 70%. Almost none of it is
convergence.

Fitted log-linear rates over the full window, using the same method as
[`arab-world.md`](arab-world.md):

| measure | %/yr | R² |
|---|---:|---:|
| total (all land pixels) | **−3.05** | 0.746 |
| intensive (lit pixels only) | **+0.65** | 0.202 |
| extensive (lit share) | **+4.72** | 0.689 |

The lit share goes from a tenth of the country to nearly three quarters — a
sevenfold expansion of lit area — while inequality *among places that already
had light* **rises**. By the typology in `satimg.trends` Thailand is an
**extensive spreader**, and a far cleaner example than any Arab country: its
extensive margin moved further than Somalia's, and unlike Somalia its total
decline is steep enough (half-life 23 years) to look, on the total alone, like
dramatic convergence. It is not.

This is the clearest single case for why the lit-only series is published beside
the total rather than under it.

## The 2014 discontinuity is larger here than anywhere in the pool

| window | %/yr | R² |
|---|---:|---:|
| DMSP 1992–2013 | −1.79 | 0.358 |
| VIIRS 2014–2022 | **−6.47** | 0.947 |

The rate more than triples at exactly the sensor handover, and the fit quality
jumps from 0.36 to 0.95. Eighteen of the 22 Arab League countries accelerate at
the same boundary; Thailand accelerates harder than any of them. **Do not read
−6.47 as a fact about Thailand.** A country that was 10% lit in 1992 has the
most to gain from a sensor that can see low light at all, which is precisely why
this is the wrong number to quote and the two eras are fitted separately.

## Aridity: the control case

Thailand has **no desert at all** — `desert_share` is 0.0000 for all 77
provinces, and 54 are wholly humid. The remaining 23 are dry sub-humid in part,
which is what makes Thailand a useful control on the aridity work: it is the
one country here where "dark" cannot mean "desert", so any darkness has to be
explained some other way.

Provincial light density in 2022 runs from **Bangkok Metropolis at 58.5
SOL/km²** to **Mae Hong Son at 1.09** — a 54-fold spread, in a country with no
arid land whatsoever. Mountainous, forested and thinly populated is enough.

Thailand's per-province aridity table is published at
[`../results/THA/THA_adm1_aridity.csv`](../results/THA/THA_adm1_aridity.csv)
but is deliberately **not** in the pooled `aridity_vs_light.csv`, for the reason
at the top of this page.

## No exclusion scope, deliberately

The 22 Arab countries carry low-light exclusion scopes derived from the largest
discontinuity in provincial lit share. Thailand has none, and that is an
abstention rather than an oversight: the rule finds a break in *light*, and
every rationale published for it reads that break as desert or as conflict.
Neither transfers. Eight Arab League members are already in the same
scope-`all`-only state, so nothing downstream needs a special case.

If a Thailand-appropriate scope is ever wanted, the honest version would be cut
on terrain or forest cover and named for that — not borrowed from a vocabulary
built for the Sahara.

## Caveats

Everything in [`lrcc-dvnl.md`](lrcc-dvnl.md) applies, and two things bite
harder here than in the Arab set.

**928 admin-2 units, and the smallest are two pixels.** Bangkok's inner
districts are smaller than the 1 km grid: Pom Pram Sattru and Samphantawong
cover **2 pixels each**, both saturated at DN 63, and their light *densities*
come out at 52.1 and 71.4 SOL/km² purely because polygon area and pixel count
disagree at that scale. Ratchathewi and Bang Rak are 4 pixels each and land at
36.2 and 61.1. Check `pixels` before quoting any admin-2 density; the column is
emitted for exactly this.

**GADM types two admin-2 units as "Water body".** Both are Songkhla Lake, split
across Phatthalung (`THA.40.11_1`, 450 pixels, mean DN 3.81) and Songkhla
(`THA.64.16_1`, 384 pixels, mean DN 2.31). They are not empty and they do not
break anything, but a *light density over a lake* is not a quantity about human
settlement, and they are large enough to matter at admin-2. Drop them by GID if
the district series is doing work.

**There is a second discontinuity, and it is not 2014.** The largest
year-on-year move in Thailand's zeros-included Gini is **2009 → 2010**, which
drops it 0.9294 → 0.7765 in a single step. The lit share behind that step goes
**12.8% → 39.4%** and then falls back to 33.9% in 2011; 2007 → 2008 moves the
other way, 21.9% → 12.2%. A country does not triple its lit area in a year and
give a third of it back the next. These are DMSP inter-satellite steps, and
they are far more visible in a country that was mostly unlit than in an
already-bright one — which is why the caveat surfaced here rather than in the
Arab set. The charts mark 2014 with a dashed line because that is the
documented handover; **treat the 2008 and 2010 steps as candidate artefacts
too**, and prefer the fitted era rates over any single year-pair.

**The nested decomposition is exact.** Residuals on the pixel → district →
province split sit at machine precision (3.3e-16 in 2022, 8.9e-15 in 1992), so
the three-way identity holds as it does elsewhere.

## Verification

- Reading Thailand's committed rasters and summing non-nodata pixels reproduces
  its committed tables for all 31 years, the check already applied to the 22.
- Class shares sum to exactly 1 for all 77 provinces.
- `satimg results build --check` passes with Thailand included.
- Adding Thailand left `results/trends_by_country.csv` **byte-identical** and
  changed nothing in `results/aridity_vs_light.csv` except a separately-fixed
  `dryland_share` bug; `dark_2022` and `cell` are byte-identical across both
  changes.
