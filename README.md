# SatelliteImagery

Reproducible importers for global satellite imagery datasets.

First dataset: **LRCC-DVNL** — a long-term global nighttime light series
covering **1992–2022** at 1 km, built to stay usable in low-light and dark-sky
regions rather than only in bright urban cores
([paper](https://doi.org/10.1038/s41597-025-05246-8) ·
[data](https://doi.org/10.7910/DVN/15IKI5)).

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

## Install

```bash
pip install -e .            # import pipeline only, zero dependencies
pip install -e ".[raster]"  # adds rasterio + numpy for the raster commands
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

## Before you use this dataset

Read [`docs/lrcc-dvnl.md`](docs/lrcc-dvnl.md). The one caveat to know up front:
the continuity calibration **allows values to rise or stay flat, never to
fall**, so genuine declines — urban shrinkage, conflict, disaster, energy
shortage — are suppressed by construction. This series cannot be used to study
dimming, and it biases trend estimates upward.

Note also that the Dataverse deposit is labelled **CC0 1.0** while the paper
states **CC BY-NC-ND 4.0**. Confirm with the authors before redistributing.

## Development

```bash
pip install -e ".[dev]"
pytest                 # 75 offline tests, no network
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
