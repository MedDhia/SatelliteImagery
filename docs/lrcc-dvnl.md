# LRCC-DVNL — datasheet

Global annual nighttime lights (NTL), **1992–2022**, at 1 km resolution.
"LRCC-DVNL" expands to **L**inear trend **R**egistration **C**ontinuous
**C**alibrated **DVNL**, where DVNL is the residual-network calibrated
DMSP↔VIIRS product of Nechaev et al. (2021).

The dataset's stated motivation is coverage of **low-light and dark-sky
regions** — roughly 80% of the Earth's surface — which brightness-focused NTL
products handle poorly, biasing light-pollution estimates in protected areas.

Everything below was verified against the live deposit and against
`LACC_1992.tif` directly, not taken from the paper alone. Where the paper and
the archive disagree, both are noted.

---

## Provenance

| | |
|---|---|
| Paper | Tang, H., Zhong, Y., Deng, J., Xia, H., & Wei, J. (2025). *Global nighttime light dataset from 1992 to 2022 with focus on low-light areas.* Scientific Data 12, 971. |
| Paper DOI | [10.1038/s41597-025-05246-8](https://doi.org/10.1038/s41597-025-05246-8) |
| Data DOI | [10.7910/DVN/15IKI5](https://doi.org/10.7910/DVN/15IKI5) |
| Repository | Harvard Dataverse |
| Deposit version | 2.0, released 2025-04-25 |
| Deposit title | "Global nighttime light dataset from 1992 to 2022 with focus on low-light areas（updated）" |
| Contact | Tang, Hui — Central South University of Forestry and Technology |

### License — a discrepancy worth knowing

The Dataverse deposit is published under **CC0 1.0** (public domain
dedication), and that is what the API reports and what this repo records in the
manifest. The *paper's* Data Availability text instead states
**CC BY-NC-ND 4.0**, which is considerably more restrictive.

For anything beyond internal analysis — redistribution, derivative products,
commercial use — treat the licensing as ambiguous and confirm with the authors
rather than relying on the CC0 label alone. Cite the work either way.

### Source inputs

| Era | Input |
|---|---|
| 1992–2013 | DMSP/OLS stable-lights V4 |
| 2013–2019 | DVNL (Nechaev et al. 2021), DMSP-like VIIRS |
| 2013, 2020–2022 | Annual VNL V2 (VIIRS), calibrated to DVNL as C-DVNL |

The published pipeline pairs a residual neural network with a raster-function
model to restore high-latitude NTL, hold the series continuous, and align the
DMSP↔VIIRS sensor gap.

---

## Products in the deposit

The deposit holds three products, all indexed in the committed manifest:

| Product id | Files | Size | Contents |
|---|---|---|---|
| `lrcc-dvnl` | 31 GeoTIFFs | 940 MiB | **The headline series.** One raster per year, 1992–2022. |
| `c-dvnl` | 10 × `.7z` | 276 MiB | Intermediate calibrated DVNL, 2013–2022 (repaired 2013, extended 2020–2022). |
| `crf` | 1 × `.7z` | 642 MiB | Whole series as one Esri CRF multidimensional raster. ArcGIS-oriented. |

**Filename gotcha:** the annual rasters are named **`LACC_<year>.tif`**, not
`LRCC-DVNL_*`. The archive's directory label is `LRCC-DVNL data`. Nothing in
the filename identifies the product, so keep them in their own directory —
which is what `satimg` does by default.

---

## Raster properties

Verified by opening `LACC_1992.tif`:

| Property | Value |
|---|---|
| Format | GeoTIFF, LZW-compressed, tiled 128×128 |
| Grid | 34 488 × 15 315 px (528 183 720 px), single band |
| Resolution | 1000 m |
| Data type | **mixed across years** — see below |
| Valid values | DN 0–63 (DMSP-like scale) |
| NoData | **127** |
| CRS (nominal) | EPSG:8857 — WGS 84 / Equal Earth Greenwich |
| Bounds (m) | −17 243 958, −7 332 168 → 17 244 042, 7 982 832 |
| Latitude extent | **75°N to 65°S** — not pole to pole |
| Per-year size | 16–55 MiB on disk |

The grid is **not global in latitude**. Inverse-projecting the vertical bounds
gives 75.00°N and 65.01°S, so Antarctica and the high Arctic (northern
Greenland, Svalbard, much of the Canadian Arctic) are outside the data
altogether. Anything that overlays or joins against global boundaries has to
clip to this extent, or it will imply coverage that does not exist.

Values are **relative digital numbers, not radiances.** DN 0–63 is the DMSP
convention; there is no conversion to nW·cm⁻²·sr⁻¹ implied.

### The series is not dtype-homogeneous

Checked across all 31 files:

| Years | dtype | Values |
|---|---|---|
| 1992 | `int8` | integer DN |
| 1993–2013 | `int16` | integer DN |
| 2014–2022 | `float32` | **fractional** DN (47 280 distinct values in 2022) |

The grid, nodata (127) and 0–63 range are identical throughout — only the
storage type and value granularity change, and the switch lands exactly on the
DMSP→VIIRS boundary.

This bites in practice. Anything that assumes a single dtype across the series —
reading into a preallocated `int8` array, stacking years with `np.stack`,
writing a derived product with a hardcoded profile — will **silently truncate
2014–2022**, turning DN 1.95 into 1 and shaving a systematic bias into exactly
the half of the series where lit area is growing fastest. `satimg` reads each
year's dtype from the file and preserves it; a test pins all three cases.

For the same reason, an exact-value histogram is only meaningful for the integer
years. `satimg raster stats` bins the float years by floor and reports
`histogram_is_binned: true` rather than implying exact counts.

### The CRS defect

Every published raster declares its CRS as a **`LOCAL_CS`** WKT:

```
LOCAL_CS["WGS 84 / Equal Earth Greenwich",
         UNIT["metre",1,...], AXIS["Easting",EAST], AXIS["Northing",NORTH],
         AUTHORITY["EPSG","8857"]]
```

It names EPSG:8857 but is not a projected CRS, so `to_epsg()` returns `None`
and GDAL/QGIS/rasterio will refuse to reproject or overlay the raster with
anything else. The **georeferencing itself is correct** — only the declaration
is malformed — so the fix is a metadata rewrite with no resampling:

```bash
satimg raster fix-crs data/raw/lrcc-dvnl/lrcc-dvnl/*.tif
```

Run this before any reprojection, zonal statistics against vector boundaries,
or cross-dataset overlay. `satimg raster info --strict` exits non-zero while a
file still needs it, which makes it easy to gate a pipeline on.

Rewriting the headers changes the file's size and MD5, so a repaired raster no
longer matches the published checksum. `fix-crs` therefore writes a small
`<file>.satimg.json` sidecar recording the pre-repair digest, and `verify`
consults it — a repaired file reports `REPAIRED`, not `CORRUPT`, while genuine
corruption still fails. Keep the sidecars alongside the rasters, or re-download
before verifying.

---

## Caveats before you analyse

1. **Monotonicity is imposed.** The continuity calibration permits NTL values
   to stay flat or rise, never to fall. Genuine declines — urban shrinkage,
   war, disaster, energy shortage, sanctions, pandemic dips — are therefore
   **suppressed by construction**. This is the single most consequential
   limitation: do not use this series to study dimming, decline, or negative
   shocks. It biases any trend estimate upward.
2. **Sensor-era discontinuity.** 1992–2013 is DMSP-derived, 2014–2022
   VIIRS-derived. Per-year file sizes jump from ~27 MiB (2013) to ~41 MiB
   (2014), reflecting the change in the underlying information content.
   Treat the boundary as a candidate breakpoint and test robustness across it.
3. **Saturation.** The DN 0–63 scale inherits DMSP's top-coding: dense urban
   cores saturate at 63 and cannot be distinguished from one another. This
   dataset's design target is the dark end, not the bright end.
4. **Equal Earth is an equal-area projection.** Convenient for area and
   lit-fraction statistics; not conformal, so shapes and directions distort.
   Reproject deliberately for anything angle-sensitive.
5. **NoData is 127, not 0.** Zero means "observed, unlit" and is a real
   measurement. Conflating the two inflates dark-area counts by the ~51 M
   nodata pixels (≈9.6% of the grid in 1992).
6. **Authorship differs between paper and deposit.** The paper lists five
   authors; the Dataverse record lists three. Cite the paper for the method.

---

## Reproducing the data locally

Nothing in `data/` is committed — the deposit is ~1.8 GiB in total. The
manifest at `src/satimg/datasets/data/lrcc_dvnl_manifest.json` pins every file
id, byte size and MD5, so a local copy is reproducible and tamper-evident.

```bash
pip install -e ".[raster]"

satimg lrcc-dvnl list                      # what is in the deposit
satimg lrcc-dvnl download                  # the 31-year series, ~940 MiB
satimg lrcc-dvnl download --years 1992-2000
satimg lrcc-dvnl verify                    # re-check MD5s of local files
satimg lrcc-dvnl cite --format bibtex
```

Downloads resume after interruption and are only moved into place once their
MD5 matches. To confirm the manifest still matches upstream:

```bash
pytest -m network                          # or:
python scripts/refresh_manifest.py --check
```

### Two upstream quirks the client handles

* Harvard Dataverse's edge returns **403** to the default `Python-urllib/x.y`
  User-Agent. `satimg` always sends its own; a live test asserts the 403 still
  happens, so the workaround gets removed when it becomes unnecessary.
* `/api/access/datafile/{id}` 303-redirects to a presigned S3 URL where **HEAD
  is 403**. File sizes must come from the manifest, not a preflight request.
  Ranged GET works (206), which is what makes resume possible.

---

## Citation

```bibtex
@article{tang2025lrccdvnl,
  title   = {Global nighttime light dataset from 1992 to 2022 with focus on low-light areas},
  author  = {Tang, Hui and Zhong, Yongde and Deng, Jinyang and Xia, Hongling and Wei, Juan},
  journal = {Scientific Data},
  volume  = {12},
  pages   = {971},
  year    = {2025},
  doi     = {10.1038/s41597-025-05246-8}
}
```

## Boundary overlays

Country and subnational overlay sets are documented separately in
[`overlays.md`](overlays.md). Note that they are **GADM-encumbered** — the
boundary source is non-commercial and non-redistributable, a stricter condition
than anything attaching to the imagery itself.

## Related long-term NTL series

If the imposed monotonicity is disqualifying for your question, these cover
similar spans with different trade-offs:

* **Li et al. harmonized DMSP–VIIRS** (1992–2024, ~1 km) — the widely used
  baseline; permits declines.
* **SVNL / simulated VIIRS** (1992–2023, ~500 m) — Sci Data 2024,
  [10.1038/s41597-024-04228-6](https://doi.org/10.1038/s41597-024-04228-6).
* **Annual VNL V2** (2012–present) — VIIRS-native radiances, no DMSP splice.
