# SatelliteImagery

Reproducible importers for global satellite imagery datasets.

First dataset: **LRCC-DVNL** — a long-term global nighttime light series
covering **1992–2022** at 1 km, built to stay usable in low-light and dark-sky
regions rather than only in bright urban cores
([paper](https://doi.org/10.1038/s41597-025-05246-8) ·
[data](https://doi.org/10.7910/DVN/15IKI5)).

## Figures

**[→ Browse all 73 030 figures in `figures/`](figures/)** — global overlays, and
for each of the 146 countries analysed the map series in three palettes, the
choropleths in two, the small-multiple panels and the inequality charts, plus
the cross-country pace chart.

[![Nighttime lights 2022 with subnational boundaries](figures/global/adm1/LACC_2022_adm1.png)](figures/global/adm1/LACC_2022_adm1.png)

Tunisia's nighttime-light Theil T halves between 1992 and 2022 — yet the share
of it that lies *between* governorates **rises**. Convergence happened inside
regions, not between them, which is the opposite of what the falling Gini alone
would suggest:

[![Nested Theil decomposition](figures/TUN/charts/TUN_theil_decomposition.png)](figures/TUN/charts/TUN_theil_decomposition.png)

The renderers write full-resolution output under gitignored `data/`;
`figures/` is the same 11 497 images re-encoded for the web (726 MB) and is
regenerated, index and all, by one command:

```bash
satimg figures build              # --max-px 0 to keep native pixels
```

⚠️ The figures are **not** covered by this repository's MIT licence — they
depict GADM boundaries, which are non-commercial and non-redistributable. See
[`figures/NOTICE.md`](figures/NOTICE.md).

## Results

**[→ The numbers behind the figures, in `results/`](results/)** — 856 tables and
4 526 clipped GeoTIFFs across 146 countries, with a generated data dictionary
for every column: the per-country inequality outputs, the per-unit aridity
tables, and the ten cross-country tables, two per pool.

Per country: the inequality series (Gini, Theil T, Theil L), the Theil
decomposition, per-unit contributions, zonal tables at each admin level, and
the 31 annual rasters everything is computed from — masked to the national
boundary, `EPSG:8857`, source dtype preserved.

Reading a country's rasters and summing non-nodata pixels reproduces its
committed tables for all 31 years; that check runs against `results/` alone and
passes for all 22.

The 8.3 GB behind it is **not** committed — `data/` holds only a `.gitkeep` —
so none of this needs the LRCC-DVNL deposit or the GADM world layer first.
`satimg results build --check` fails if the committed outputs drift from a
fresh run, and the build refuses to publish a raster whose dtype disagrees with
the documented era or a table column it cannot explain.

## What "imported" means here

The rasters are **not** committed — the deposit is ~1.8 GiB, and the annual
series alone is ~940 MiB. What is committed is everything needed to reproduce
a byte-identical local copy:

* **`src/satimg/datasets/data/lrcc_dvnl_manifest.json`** — the file index. All
  42 files across 3 products, each with its Dataverse file id, byte size and
  MD5. This is the import: a pinned, reviewable, tamper-evident description of
  the dataset.
* **A downloader** that materializes those files, resumes after interruption,
  and refuses to install a file whose MD5 does not match.
* **[`docs/lrcc-dvnl.md`](docs/lrcc-dvnl.md)** — the datasheet: provenance,
  grid, units, licensing, and the caveats that decide whether this dataset can
  answer your question.

### `data/` is empty in a clone, on purpose

It holds only a `.gitkeep`. A full local run fills it with **9.7 GB** that this
repository deliberately does not carry:

| Path | Size | Why it is not committed |
|---|---:|---|
| `data/boundaries/gadm` | 4.7 GB | GADM forbids redistribution |
| `data/overlays/lrcc-dvnl` | 2.3 GB | 62 two-band GeoTIFFs; GADM-encumbered |
| `data/raw/lrcc-dvnl` | 940 MB | reproducible byte-identically from the manifest |
| `data/regions/*` | pruned per batch | 146 countries; published instead as [`figures/`](figures/) (5.0 GB) and [`results/`](results/) (1.1 GB, rasters included) |

The commands under [Use](#use) rebuild all of it. What is committed is the
part you cannot regenerate by yourself: the pinned manifest, the code, the
figures and the numbers.

## Install

```bash
pip install -e .            # import pipeline only, zero dependencies
pip install -e ".[raster]"  # adds rasterio + numpy for the raster commands
pip install -e ".[figures]" # adds pillow, for assembling figures/
pip install -e ".[overlay]" # adds geopandas/rasterio for boundaries and aridity
```

## Use

```bash
satimg lrcc-dvnl list                       # inspect the deposit
satimg lrcc-dvnl download                   # 31 annual rasters, ~940 MiB
satimg lrcc-dvnl download --years 1992-2000 # or a subset
satimg lrcc-dvnl verify                     # re-check local files' MD5s
satimg lrcc-dvnl cite --format bibtex
```

```
$ satimg lrcc-dvnl list
Global nighttime light dataset from 1992 to 2022 with focus on low-light areas（updated）
  DOI      https://doi.org/10.7910/DVN/15IKI5
  Version  2.0 released 2025-04-25T13:49:02Z
  License  CC0 1.0 (http://creativecommons.org/publicdomain/zero/1.0)
  Total    1.8 GiB across 42 files

PRODUCT    YEARS      FILES  SIZE       FORMAT
---------  ---------  -----  ---------  ---------------------
lrcc-dvnl  1992-2022  31     939.8 MiB  GeoTIFF
c-dvnl     2013-2022  10     275.6 MiB  GeoTIFF (7z archive)
crf        n/a        1      641.7 MiB  Esri CRF (7z archive)
```

Files land under `data/raw/lrcc-dvnl/<product>/` (gitignored) as
`LACC_<year>.tif` — the published names, which do not mention LRCC-DVNL.

### Fix the CRS before analysis

The published rasters carry Equal Earth georeferencing in a `LOCAL_CS` WKT, so
`to_epsg()` returns `None` and most tools will not reproject or overlay them.
The pixels and transform are fine; only the declaration is malformed.

```bash
satimg raster info    data/raw/lrcc-dvnl/lrcc-dvnl/LACC_1992.tif
satimg raster fix-crs data/raw/lrcc-dvnl/lrcc-dvnl/*.tif   # metadata-only rewrite
satimg raster stats   data/raw/lrcc-dvnl/lrcc-dvnl/LACC_1992.tif
```

```
$ satimg raster stats data/raw/lrcc-dvnl/lrcc-dvnl/LACC_1992.tif
  total pixels     528,183,720
  nodata pixels    50,939,108
  valid pixels     477,244,612
  lit pixels DN>0  11,712,912 (2.4543% of valid)
  DN range         0 - 63
  sum of lights    171,402,585
  mean DN (lit)    14.634
```

`stats` streams the raster in horizontal strips, so a full global grid
summarizes in seconds without loading all 528 M pixels at once.

`fix-crs` rewrites headers, which changes the file's MD5. It records the
pre-repair digest in a `<file>.satimg.json` sidecar, so `verify` still
recognises a repaired raster (`REPAIRED`) while real corruption still fails.

## Boundary overlays

Superposing administrative boundaries produces **two additional sets** beside
the original imagery — country (GADM adm0, 263 units) and subnational
(GADM adm1, 3 662 units) — each as viewable PNG maps *and* georeferenced
two-band GeoTIFFs.

```bash
pip install -e ".[overlay]"
satimg boundaries fetch                # GADM 4.1 world GeoPackage (2.5 GiB)
satimg boundaries prepare --level 0,1  # reproject + simplify, cached
satimg lrcc-dvnl overlay               # both levels, both formats, all 31 years
```

```
data/overlays/lrcc-dvnl/
├── adm0/{png,tif}/LACC_<year>_adm0.{png,tif}
└── adm1/{png,tif}/LACC_<year>_adm1.{png,tif}
```

The GeoTIFFs are **non-destructive**: band 1 is the published DN copied through
byte-for-byte, band 2 is the boundary mask. They also carry a real `EPSG:8857`,
so unlike the source files they need no CRS repair.

⚠️ **The boundaries are GADM, which is non-commercial and non-redistributable.**
The overlay products inherit that restriction — fine for academic publication,
not for redistribution. See [`docs/overlays.md`](docs/overlays.md).

## Country analysis: the Arab world

Extract a country at three admin levels and compute nighttime-light inequality
series from it. **All 22 Arab League members** are done, from Algeria's
2.3 million land pixels to Bahrain's 717.

```bash
satimg lrcc-dvnl extract --country DZA --levels 0,1,2   # clipped maps + panels
satimg lrcc-dvnl inequality --country DZA               # Gini + Theil + decomposition
```

Colour the units themselves instead of overlaying boundaries:

```bash
satimg lrcc-dvnl choropleth --country DZA --levels 1,2   # 124 maps + 4 panels
```

`absolute` maps mean DN on a scale shared across years (growth); `relative`
divides by the national mean of the same year (standing) — the latter being the
quantity the Theil between-group component is built from.

Each country produces series over 1992–2022 — pixel (with and without unlit
pixels) plus both subnational levels, for the whole country and for the
low-light exclusion variants — reporting **Gini, Theil T and Theil L**, plus the
additive **between/within decomposition** of Theil over the nested
pixel → admin-2 → admin-1 hierarchy.

The exclusion scopes are **derived from the light**, not hand-picked: cut each
country's admin-1 units at the largest discontinuity in their lit share. On
Tunisia that reproduces the three hand-picked Saharan governorates exactly,
which is the check that the rule finds real geography — but it is a break in
*light*, not a definition of desert, and
[`docs/arab-world.md`](docs/arab-world.md) records where the two part company
— in Syria and Iraq it selects war damage, not desert.

⚠️ **GADM 4.1 has no admin-2 layer for Libya, Bahrain, Comoros, Kuwait or
Qatar**, so those analyses stop at admin-1 and have no nested three-way split.
Nothing downstream invents one.

The scopes are cut from observed darkness, which is not the same as climate.
[`docs/aridity.md`](docs/aridity.md) measures the difference against the Global
Aridity Index — and **refutes most of what this repository previously asserted
about it**: Aleppo is 70% arid, Mosul 58%, not the non-desert cities the earlier
prose claimed. The light rule turns out to track climate better than its own
documentation did (94% of the units it excludes are majority-arid, against a 73%
base rate), and the genuinely non-arid dark regions are Darfur and southern
Somalia.

```bash
satimg aridity vs-light     # the 317-unit join, from the committed tables
satimg aridity chart        # the figure below
```

[![Aridity against darkness](figures/aridity/arid_vs_lit.png)](figures/aridity/arid_vs_lit.png)

Aridity turns out to be a weak predictor of light, and not as a gentle slope:
median 2022 mean DN is **3.70** where a unit is entirely desert, **3.78** where
it is partly desert, and **14.09** where it is not desert at all. The two arid
bands are indistinguishable — the whole relationship is one step. And the
"dark for human reasons" set has no crisp boundary: 6 units at the 10th
percentile of darkness, 13 at the 25th, 23 at the median, strictly nested.

### Pace: a falling total is not the same as convergence

Comparing *levels* across countries is partly mechanical — Theil T is bounded by
ln(N), and land pixels run from Bahrain's 717 to Algeria's 2.3 million
(Spearman = +0.68). Comparing *pace* is not: N is fixed over time within a
country, so it cancels out of any fitted rate.

```bash
satimg trends --country all     # results/trends_by_country.csv + the figure
```

[![Pace of change across the Arab world](figures/trends/pace_total_vs_intensive.png)](figures/trends/pace_total_vs_intensive.png)

Nine countries' total inequality falls **while inequality among their
already-lit places rises**. Somalia is the clearest — total −0.96 %/yr, lit-only
**+1.11 %/yr**, lit area **+7.10 %/yr**: nothing converged, light simply arrived
somewhere new. Bahrain is the opposite and the reason to measure both — already
fully lit, so its −4.09 %/yr is real convergence. Reporting only the total files
these under the same headline.

⚠️ **18 of 22 countries decline faster after 2014** — exactly the DMSP→VIIRS
handover. That is an instrument signature, so the two eras are fitted separately
and must not be compared with each other.

See [`docs/arab-world.md`](docs/arab-world.md) for the cross-country method and
[`docs/tunisia.md`](docs/tunisia.md) for the original single-country detail.

## All of Africa

[`docs/africa.md`](docs/africa.md) covers all **54 African states plus Western
Sahara** — 854 admin-1 and 6 475 admin-2 units — as a comparison pool of its
own. Africa and the Arab League overlap by ten countries, so they are separate
pools rather than one list, and each owns its own tables.

⚠️ **`dark_2022` is not comparable between pools.** Each aridity join cuts at
the median of *its own* pool: 6.26 for the Arab League, 0.49 for Africa.

Two findings the continent forces:

**Falling inequality is almost never convergence here.** 42 of 55 African
countries are extensive spreaders — the total falls only because light reaches
new ground, while inequality among already-lit places rises. The same rule puts
9 of 22 Arab League countries in that class, and Africa has exactly **one**
intensive converger (Mauritius) against the Arab League's six.

**Aridity predicts African light essentially not at all** —
Spearman(`desert_share`, 2022 mean DN) = **+0.024**, against −0.146 in the Arab
world, and the *fully arid* band is the **brightest** of the three. Africa's
arid north holds its more urbanised economies and its humid centre its poorest,
so climate and income confound each other in the opposite direction and roughly
cancel. Yet the light-derived exclusion rule still lands on arid ground 90% of
the time against a 24% base rate — a lift of 3.75, where the Arab League gives
1.29. That the rule survives a continent where the underlying correlation is
zero is the strongest evidence yet that it finds climate rather than darkness.

## The Americas, in two pools

[`docs/americas.md`](docs/americas.md) covers all **35 states of North and
South America**, as **two pools rather than one**. A single Americas pool would
have put Saint Kitts and Nevis in the same median as the United States; the
measured cuts are **6.3990** north against **1.8081** south, so a pooled median
would have sat between them and misclassified both ends.

⚠️ `dark_2022` is now incomparable across **four** pools — `arab-league`,
`africa`, `north-america`, `south-america` — each cut at the median of its own
members: 6.26, 0.49, 6.40 and 1.81.

**North and South are near-opposites.** South America is **11 of 12 extensive
spreaders** and contains no intensive converger at all. North America is the
only pool where genuine convergence among lit places is the largest class — 7
intensive convergers against 4 extensive spreaders. The extensive margin
explains it, and orders the pools cleanly: Africa **+4.92 %/yr**, South America
**+3.81**, the Arab League **+2.25**, North America **+1.31**. North America was
already lit in 1992, so its falling inequality has to come from convergence
rather than expansion.

**The strongest aridity signal in the repository is in its least arid pool.**
North America's Spearman(`desert_share`, `mean_dn_2022`) is **−0.2032** with
only **2%** of units majority-arid, against the Arab world's −0.1456 at 73% and
Africa's +0.0237 at 24%. Every one of North America's 7 majority-arid units is
dark and **not one is a lit desert** — the cleanest version of the pattern
anywhere here, and too small a cell to carry a claim about climate. South
America is the only pool whose aridity gradient is **monotone** in the expected
direction (0.97 → 1.79 → 1.99 across fully arid, partly arid, humid), yet its
correlation is −0.0329: the ordering is right and the effect is negligible.

**Two countries needed engineering rather than analysis.** GADM's `USA` has
Alaskan vertices on both sides of the antimeridian, so its bounding box spanned
the globe — a 159-megapixel frame, an out-of-memory crash rather than a slow
render, and one that reached the statistics as well as the pictures. It is
analysed over **two non-wrapping windows** instead, 52.8 Mpx together, and the
statistics span both so nothing is dropped. An earlier crop to the western
hemisphere reached the same cost by discarding 2 121.9 km² of Aleutians;
restoring them added 2 127 pixels and **338 DN of light** to Alaska, which is
why "near-unlit" was never treated as "unlit". **Brazil** stops at the state:
its 5 572 municipalities are the largest ADM_2 set here, and the cost was
refused. That is recorded in `regions.LEVELS_NOT_ANALYSED`, kept apart from
`LEVELS_AVAILABLE` because the latter would have claimed GADM has no Brazilian
municipalities, which is false.

**Canada has no name for its own admin-2 level.** Its most common GADM
`ENGTYPE_2` is Quebec's "Regional County Municipality" at 93 of 293 units —
32%, a plurality and not a word the country uses for itself — so it takes the
generic title while keeping all 293 units. That is what forced the level-name
rule to require a true majority rather than a mode.

## All of Europe

[`docs/europe.md`](docs/europe.md) covers **43 European countries** as a single
`europe` pool — 688 admin-1 units, 5 978 analysed admin-2. It is the first pool
that **overlaps no other**: Africa and the Arab League share ten members, and
the two American pools were split precisely so they would not share one.

Three states are absent, for two different reasons. **Monaco and the Vatican
have no GADM 4.1 feature at any level** — a gap in the source, not a choice.
**Russia is excluded deliberately**: about three quarters of its area is Asian,
and it wraps the antimeridian like the USA, but the American remedy does not
transfer — cropping at 180° costs the USA 2 122 km² of Aleutian rock and would
cost Russia **114 686 km² of Chukotka**, larger than Iceland.

**The brightest pool, and the only one where light is going out.** Europe's
darkness cut is **9.5926**, well above North America's 6.40 and Africa's 0.49.
Everywhere else in this repository lit area grows; in Europe five countries are
losing it — Ukraine **−1.32 %/yr**, Slovakia −0.43, Moldova −0.22, the UK −0.09,
the Netherlands −0.04 — and four of them are the only European countries whose
total inequality rises.

⚠️ **That finding is where this dataset is weakest, and the document says so.**
A falling radiance in a rich, fully-electrified country is more plausibly the
**LED transition** than a blackout: LEDs emit far less in the day/night band
than the sodium lamps they replaced, so the same street records as less light.
The series cannot separate "fewer lit places" from "the same places, lit
differently", and Europe is where that conversion went furthest. The United
Kingdom's classification is weaker still — +0.045 %/yr at **R² 0.009**, which
the direction column itself calls `flat`. The rule fired on a sign, not a
magnitude.

**Aridity has nothing to work with here.** One European admin-1 unit out of 688
is majority-arid and the pool's median `dryland_share` is **0.0000**. The eight
partly-arid units are *twice as bright* as the other 680 (19.13 against 9.31),
which inverts the Arab result exactly as Africa's did — but on eight units that
is not a climate finding. Europe's only desert is **Spain's Islas Canarias**, an
Atlantic archipelago off the African coast, and it is the pool's only lit
desert; there are no dark ones at all.

**The slowest extensive margin anywhere** at **+0.91 %/yr** — a fifth of
Africa's +4.92 — because Europe had almost no unlit ground left in 1992. Its
median intensive margin is −0.01 %/yr: across the continent as a whole,
inequality among lit places neither converges nor diverges.

## One country outside the pool: Thailand

[`docs/thailand.md`](docs/thailand.md) analyses Thailand on the same terms —
77 provinces, 928 districts, the full series and decomposition — but
**deliberately outside the cross-country comparisons**. `aridity_vs_light.csv`
cuts its darkness column at the *pooled median*, so widening the country set
would rewrite findings that are about the Arab world. `regions.ARAB_LEAGUE` is
what gets compared; `regions.COUNTRIES` is everything analysed.

Thailand is the clearest extensive spreader in the whole collection: total
Theil T falls **−3.05 %/yr**, yet inequality among already-lit pixels **rises**
(+0.65 %/yr) while the lit share goes from **10% of the country to 72%**. On
the total alone it looks like dramatic convergence. It is light arriving,
almost nothing else.

## Before you use this dataset

Read [`docs/lrcc-dvnl.md`](docs/lrcc-dvnl.md). The one caveat to know up front:
**a lit pixel's DN never steps down while it stays lit — every decrease in this
series is a pixel going out entirely.** Measured across five countries and all
30 year-steps, the number of decreasing pixel-years exactly equals the number
of lit → unlit transitions, every time.

So catastrophic loss *is* visible — Syria's national sum of lights falls 54%
between 2010 and 2016 — but *gradual* dimming is not: a city that halves its
brightness while staying lit looks flat. Trend estimates are biased upward for
slow decline.

A second trap, found by checking all 31 files rather than one: **the series is
not dtype-homogeneous.** 1992 is `int8`, 1993–2013 `int16`, and 2014–2022
`float32` carrying *fractional* DN. Code that assumes a single dtype silently
truncates the VIIRS-era years — a systematic downward bias in exactly the half
of the series where lit area grows fastest.

Note also that the Dataverse deposit is labelled **CC0 1.0** while the paper
states **CC BY-NC-ND 4.0**. Confirm with the authors before redistributing.

## Development

```bash
pip install -e ".[dev]"
pytest                 # 449 offline tests, no network
pytest -m network      # live checks: manifest still matches upstream
```

Refresh the manifest when the deposit publishes a new version, then commit the
diff so the upstream change is reviewable:

```bash
python scripts/refresh_manifest.py          # rewrite
python scripts/refresh_manifest.py --check  # CI: fail if stale
```

## Citation

Tang, H., Zhong, Y., Deng, J., Xia, H., & Wei, J. (2025). Global nighttime
light dataset from 1992 to 2022 with focus on low-light areas. *Scientific
Data*, 12, 971. https://doi.org/10.1038/s41597-025-05246-8
