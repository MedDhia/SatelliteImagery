# SatelliteImagery

Reproducible importers for global satellite imagery datasets.

First dataset: **LRCC-DVNL** — a long-term global nighttime light series
covering **1992–2022** at 1 km, built to stay usable in low-light and dark-sky
regions rather than only in bright urban cores
([paper](https://doi.org/10.1038/s41597-025-05246-8) ·
[data](https://doi.org/10.7910/DVN/15IKI5)).

## Figures

**[→ Browse all 10 950 figures in `figures/`](figures/)** — global overlays, and
for each of the 22 Arab League countries the map series in three palettes, the
choropleths in two, the small-multiple panels and the inequality charts, plus
the cross-country pace chart.

[![Nighttime lights 2022 with subnational boundaries](figures/global/adm1/LACC_2022_adm1.png)](figures/global/adm1/LACC_2022_adm1.png)

Tunisia's nighttime-light Theil T halves between 1992 and 2022 — yet the share
of it that lies *between* governorates **rises**. Convergence happened inside
regions, not between them, which is the opposite of what the falling Gini alone
would suggest:

[![Nested Theil decomposition](figures/TUN/charts/TUN_theil_decomposition.png)](figures/TUN/charts/TUN_theil_decomposition.png)

The renderers write full-resolution output under gitignored `data/`;
`figures/` is the same 10 950 images re-encoded for the web (676 MB) and is
regenerated, index and all, by one command:

```bash
satimg figures build              # --max-px 0 to keep native pixels
```

⚠️ The figures are **not** covered by this repository's MIT licence — they
depict GADM boundaries, which are non-commercial and non-redistributable. See
[`figures/NOTICE.md`](figures/NOTICE.md).

## Results

**[→ The numbers behind the figures, in `results/`](results/)** — 129 tables and
682 clipped GeoTIFFs across 22 countries, with a generated data dictionary for
every column: the per-country inequality outputs, the per-unit aridity tables,
and the two cross-country tables.

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
| `data/regions/*` | 4.6 GB | 22 countries; published instead as [`figures/`](figures/) (676 MB) and [`results/`](results/) (186 MB, rasters included) |

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
pytest                 # 399 offline tests, no network
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
