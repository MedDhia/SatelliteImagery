# Tunisia: NTL extraction and inequality series, 1992–2022

Extracts Tunisia from the LRCC-DVNL series at three administrative levels and
computes nighttime-light Gini series from them.

```bash
pip install -e ".[overlay]"
satimg lrcc-dvnl extract --country TUN --levels 0,1,2   # maps
satimg lrcc-dvnl inequality --country TUN               # tables + Gini/Theil + decomposition
```

Runtime: ~60 s for the 127 map files, ~6 s for the whole inequality computation.

## The three levels

| Level | GADM layer | Units | Tunisian name |
|---|---|---|---|
| national | `ADM_0` | 1 | Tunisia |
| subnational 1 | `ADM_1` | 24 | governorates (*wilayat*) |
| subnational 2 | `ADM_2` | 268 | delegations (*mutamadiyat*) |

Tunisia occupies a 368 × 856 window of the global grid; **154,885 pixels** fall
inside the country (≈154,870 km², matching its land area), and **none of them
are nodata**.

## Outputs

```
data/regions/TUN/
├── raster/LACC_<year>_TUN.tif             31 clipped GeoTIFFs, masked to the country
├── png/adm{0,1,2}/LACC_<year>_TUN_adm*.png    93 maps
├── panel/TUN_adm{0,1,2}_1992-2022.png     3 small-multiple panels
├── zonal/TUN_adm1_zonal.csv               744 rows (24 units × 31 years)
├── zonal/TUN_adm2_zonal.csv               8,308 rows (268 × 31)
├── inequality/TUN_inequality_series.csv       372 rows (12 series × 31 years)
├── inequality/TUN_theil_decomposition.csv    1,116 rows (year × scope × zeros × measure × grouping)
├── inequality/TUN_theil_by_unit.csv          49,690 rows (per-unit index and contribution)
└── inequality/TUN_inequality_series.png      faceted Gini/Theil chart
    inequality/TUN_theil_decomposition.png    nested decomposition chart
```

The clipped GeoTIFFs are **masked to the national outline**, not merely cropped
to its bounding box — otherwise a "Tunisia extract" still carries Algerian and
Libyan light across half the frame. The mask uses the same `all_touched=False`
burn as the zonal statistics, so the retained pixel set is exactly the one the
Gini is computed over. Each year keeps its source dtype (`int8` / `int16` /
`float32`).

## Method

### Twelve series

| Level | Quantity | Scopes | Zero treatment |
|---|---|---|---|
| pixel | DN per 1 km pixel | all · excl-narrow · excl-wide | zeros-in **and** lit-only |
| admin-1 | light density (SOL/km²) | all · excl-narrow · excl-wide | — |
| admin-2 | light density (SOL/km²) | all · excl-narrow · excl-wide | — |

Subnational Gini is **unweighted over light density**, one observation per unit.
Density rather than total SOL, because a Gini of raw totals would score
Tataouine high merely for being 39,535 km²; unweighted, because each governorate
is one regional observation.

Each series carries **Gini, Theil T and Theil L**. Gini uses the exact
sorted-rank form, cross-checked in the tests against the mean-absolute-difference
definition; Theil T is checked against `ln(N)` at its one-holder maximum. An all-dark distribution returns `nan`, not
`0.0` — no light anywhere means inequality is undefined, and `0.0` would read as
"perfectly equal" in a results table.

### The desert exclusions

Both definitions are computed, keyed on stable `GID_1` codes rather than
diacritic-bearing names:

| Scope | Excludes | Rationale |
|---|---|---|
| `narrow` | Tataouine, Kébili, Tozeur | The Sahara/chott governorates. 67,570 km² — 44% of the land — at 9.8/11.3/17.7% lit in 2022 and 1.3–2.6 SOL/km², a clear break from the next governorate (Médenine: 42% lit, 6.2). |
| `wide` | + Médenine, Gabès, Gafsa | The conventional Tunisian "South". Note this also removes real coastal and mining light (Djerba, Zarzis, Gabès, the Gafsa basin), not only desert. |

## Results

Gini, 1992 → 2022:

| Level | Scope | 1992 | 2022 | Change |
|---|---|---|---|---|
| pixel, all land | all | 0.933 | 0.777 | −0.156 |
| pixel, all land | narrow | 0.892 | 0.644 | −0.249 |
| pixel, all land | wide | 0.877 | 0.593 | −0.283 |
| pixel, lit only | all | 0.510 | 0.500 | −0.010 |
| pixel, lit only | narrow | 0.511 | 0.495 | −0.015 |
| pixel, lit only | wide | 0.512 | 0.486 | −0.025 |
| governorate | all | 0.668 | 0.475 | −0.193 |
| governorate | narrow | 0.639 | 0.424 | −0.215 |
| governorate | wide | 0.631 | 0.404 | −0.226 |
| delegation | all | 0.703 | 0.510 | −0.193 |
| delegation | narrow | 0.688 | 0.489 | −0.198 |
| delegation | wide | 0.676 | 0.476 | −0.201 |

Three patterns worth noting, and one warning:

- **Delegation Gini exceeds governorate Gini at every year and scope.** Finer
  units resolve within-governorate disparity that aggregation hides.
- **Excluding the desert lowers measured inequality at every level**, and the
  wide definition lowers it more than the narrow one. Much of Tunisia's
  measured light inequality is the Sahara being dark.
- **The two pixel series tell different stories, and that is the point.** With
  zeros in, Gini falls steeply (0.933 → 0.777) — but lit share rises from 13.8%
  to 44.6% over the same window, so that series largely restates "more of
  Tunisia is lit". Among lit pixels only, Gini is nearly flat (0.510 → 0.500)
  with a U-shape bottoming around 2011. Light spread out; it did not
  meaningfully even out where it already existed.

## Theil and the between/within decomposition

Gini cannot be split cleanly into group components — its group decomposition
leaves an overlap residual. Theil can, exactly, which is the reason to compute
it here: pixels nest inside delegations, which nest inside governorates, so
total inequality divides into three additive parts.

Zeros are the practical dividing line between the two Theil variants:

| | Zeros | Status here |
|---|---|---|
| **Theil T** (GE(1)) | `0·ln 0 → 0` in the limit | Defined everywhere, including all-land-pixel series |
| **Theil L** (GE(0)) | `ln(μ/0)` diverges | **Undefined** for all-land pixels (55–86% unlit); reported as `nan`, not silently computed on a filtered sample |

Theil L is therefore only meaningful on the lit-only pass, and that is exactly
where it is reported.

### Nested decomposition, scope `all`

`between(delegation) = between(governorate) + between-delegation-within-governorate`,
because delegations nest exactly inside governorates. Verified rather than
assumed: the two zone rasters agree on **all 154,885** pixels, and the
governorate label is derived from each delegation's `GID_1`, so the hierarchy is
exact by construction.

Theil T, share of total:

| Pixels | Component | 1992 | 2022 |
|---|---|---|---|
| all land | between governorates | 0.292 | 0.341 |
| all land | between delegations, within governorate | 0.187 | 0.135 |
| all land | within delegations | 0.521 | 0.524 |
| lit only | between governorates | 0.149 | 0.183 |
| lit only | between delegations, within governorate | 0.275 | 0.164 |
| lit only | within delegations | 0.576 | 0.653 |

Totals: Theil T falls 2.439 → 1.231 on all land pixels, but only 0.456 → 0.424
among lit pixels.

Two readings worth stating:

- **Convergence did not happen between governorates.** Total inequality halved,
  yet the between-governorate *share* rose (0.292 → 0.341 on all land; 0.149 →
  0.183 lit-only). What fell was inequality *within* regions, not the gap
  between them. A regional-policy reading of the falling Gini would be wrong.
- **Among lit pixels, the middle term collapsed** (0.275 → 0.164): differences
  between delegations of the same governorate shrank markedly, while
  within-delegation inequality grew to two-thirds of the total. Light became
  more evenly distributed across a governorate's delegations, but more unequal
  inside each one.

The additive identity is checked on every row of the output: the maximum
residual across the 837 defined rows is 5.3 × 10⁻¹⁴, and the decomposition
totals reproduce the independently computed pixel Theil T exactly.

## Caveats

1. **The falling Gini is partly imposed, not observed.** LRCC-DVNL's continuity
   calibration permits values only to rise or stay flat, never to fall. Lit area
   can therefore only grow, which mechanically pushes the zeros-included Gini
   down. Treat the *direction* of these series as partly an artifact of the
   source and the *cross-sectional* comparisons (adm2 vs adm1, desert vs not) as
   the more defensible readings.
2. **2014 is a candidate discontinuity.** The DMSP→VIIRS handover falls there,
   and the source dtype changes to `float32` at the same year. The chart marks
   it. A 2013→2014 step is visible in the lit-only series; do not read it as
   real convergence.
3. **11 of 268 delegations hold fewer than 5 pixels** (the smallest, 0.83 km²,
   holds one). Their density values are extremely noisy. They are reported with
   their pixel counts in the zonal CSV rather than dropped silently; use
   `--min-pixels 5` for a sensitivity run.
4. **Zonal statistics use exact, unsimplified geometry.** The 500 m
   simplification used for global rendering runs per polygon, so neighbouring
   units stop tiling: measured on Tunisia, it leaked 1,940 of 253,365 SOL at
   admin-2 and starved one delegation to zero pixels. Country layers are
   prepared at zero tolerance, and the per-unit sums are verified to add back to
   the national total for all 31 years.
5. **DN is a relative index, not radiance.** A Gini of DN describes concentration
   of observed brightness. It is not a Gini of income, output or welfare, and
   should not be reported as one.
6. **GADM licensing carries over.** The boundaries are non-commercial and
   non-redistributable; the zonal tables, Gini series and maps all derive from
   that geometry and inherit the restriction.

## Verification

Every run is checked against values measured independently from the raw rasters:

- sum of lights **253,065** (1992) and **923,122** (2022);
- **154,885** pixels, **154,870 km²**;
- admin-1 totals == admin-2 totals == the masked raster total, for all 31 years
  (each pixel belongs to exactly one unit at every level);
- all 372 Gini values inside (0, 1);
- pixel Gini falls as lit share triples; admin-2 Gini exceeds admin-1.

```bash
pytest tests/test_inequality.py tests/test_zonal.py tests/test_regions.py \
       tests/test_analysis.py tests/test_clip.py
```
