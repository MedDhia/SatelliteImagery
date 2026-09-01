# Boundary overlays

Superposing administrative boundaries on the LRCC-DVNL rasters produces **two
additional sets** alongside the original imagery:

| Set | Boundaries | Units | Output |
|---|---|---|---|
| Original | none | – | 31 GeoTIFFs, as published |
| **adm0** | country | 263 | 31 PNG renders + 31 two-band GeoTIFFs |
| **adm1** | subnational (states/provinces/regions) | 3 662 | 31 PNG renders + 31 two-band GeoTIFFs |

```bash
pip install -e ".[overlay]"

satimg boundaries fetch                # GADM 4.1 world GeoPackage, 2.5 GiB
satimg boundaries prepare --level 0,1  # reproject + simplify, cached
satimg lrcc-dvnl overlay               # both levels, both formats, all years
```

Narrow it with the usual selectors:

```bash
satimg lrcc-dvnl overlay --years 1992,2022 --admin 0 --format png
satimg lrcc-dvnl overlay --admin 1 --format tif --overwrite
```

Output layout:

```
data/overlays/lrcc-dvnl/
├── adm0/
│   ├── png/LACC_1992_adm0.png … LACC_2022_adm0.png
│   └── tif/LACC_1992_adm0.tif … LACC_2022_adm0.tif
└── adm1/
    ├── png/LACC_1992_adm1.png … LACC_2022_adm1.png
    └── tif/LACC_1992_adm1.tif … LACC_2022_adm1.tif
```

---

## Licensing — read this before sharing anything

The boundaries are **GADM 4.1**, whose license states:

> The data are freely available for academic use and other non-commercial use.
> Redistribution or commercial use is not allowed without prior permission.

Consequences, which the tooling enforces or flags rather than assumes:

* The GADM download and everything derived from it lives under `data/`, which is
  gitignored. **None of it is committed**, and it must not be.
* `satimg boundaries fetch` writes `LICENSE-GADM.txt` next to the data and
  prints the notice.
* **The overlay products inherit the restriction.** Maps for academic
  publication are explicitly permitted; redistributing the PNGs or the
  mask-band GeoTIFFs as data, or using them commercially, is not — the boundary
  geometry is embedded in both.
* This is stricter than the underlying imagery. LRCC-DVNL itself is deposited
  under CC0 1.0 (with the paper claiming CC BY-NC-ND 4.0 — see
  [the datasheet](lrcc-dvnl.md)); the *overlays* are GADM-encumbered regardless.

If you need redistributable overlays, swap the source for Natural Earth
(public domain) — the pipeline is source-agnostic apart from
`satimg/boundaries.py`'s GADM constants and layer names.

---

## The two output kinds

### PNG map renders

A viewable global map per year: the NTL grid as a dark-surface basemap with
boundary lines over it, plus a colorbar and the disclosures needed to read it
honestly.

Defaults, and why:

| Choice | Default | Reason |
|---|---|---|
| Colour | single-hue amber ramp, dark→light | Magnitude is a sequential encoding, so it takes one hue with monotone lightness. Anchored dark because the surface is dark. Country extracts instead default to `inferno` — at country scale a single hue cannot resolve the dynamic range (see [`tunisia.md`](tunisia.md#colour)); `--cmap` overrides either way. |
| Stretch | `--gamma 0.45` | 88% of valid pixels are DN 0 and lit pixels average ~15. Linear DN renders a nearly black map. The stretch is **printed on the colorbar**, because it changes what the reader perceives. |
| Downsampling | `--resampling max` | At ~9 km/px a global render averages cities into nothing. `max` keeps isolated settlements visible. Also disclosed on the figure. |
| Width | `--width 4000` | ~1 780 px tall at the grid's 2.25:1 aspect. |
| Line weight | 0.45 pt adm0 / 0.22 pt adm1 | Boundaries are reference geometry, so they stay recessive rather than competing with the data. adm1 is finer because 3 662 units is a lot of ink. |

`max` downsampling is a *display* choice and it is not radiometrically neutral:
it biases the rendered field upward. Use `--resampling average` if you need a
figure whose brightness is comparable across pixels, and accept that small
towns disappear.

### Two-band GeoTIFFs

Georeferenced and **non-destructive**:

* **Band 1** — the published NTL DN, copied through byte-for-byte. A test
  asserts `band1 == source` and that no value under the boundary was touched.
* **Band 2** — the boundary mask, `1` on a boundary pixel and `0` elsewhere
  (1 753 401 px for adm0, 2 935 042 px for adm1 — 0.33% / 0.56% of the grid).

Band 1 keeps **whatever dtype the source year used** — `int8` for 1992, `int16`
for 1993–2013, `float32` for 2014–2022. Writing a single fixed dtype would
truncate the fractional DN of the VIIRS era, which is exactly the bug the first
implementation had. Nodata is 127, LZW-compressed and tiled, with predictor 2
for the integer years and 3 for the float ones.

All 124 outputs were checked after generation: every GeoTIFF matches its source
in dtype, grid and band-1 values; every mask is strictly 0/1 with a per-level
pixel count identical across all 31 years (confirming the single rasterization
is correctly reused); no PNG is malformed.

These carry a **real `EPSG:8857`**, not the `LOCAL_CS` defect of the published
files — so the overlay products are usable in QGIS/GDAL without the separate
`satimg raster fix-crs` step.

```python
import rasterio
with rasterio.open("data/overlays/lrcc-dvnl/adm0/tif/LACC_2022_adm0.tif") as src:
    ntl, boundary = src.read(1), src.read(2)
    ntl_without_borders = ntl[boundary == 0]   # nothing was overwritten
```

---

## How the boundaries are prepared

`satimg boundaries prepare` runs once per level and caches the result
(`data/boundaries/cache/`), because the reprojection is the slow step —
about 8 minutes for both levels.

1. **Read** `ADM_0` / `ADM_1` from the world GeoPackage (EPSG:4326).
2. **Segmentize** at 0.5°. Long straight lon/lat spans — Antarctica's polar
   edge, ruler-straight desert borders — would otherwise reproject to chords
   that visibly cut across the true boundary.
3. **Reproject** to EPSG:8857 to match the rasters.
4. **Simplify** at 500 m, half a pixel. Invisible at 1 km, and it takes GADM
   ADM_0 from ~36 M vertices to ~1.2 M — a 30× cut that makes rendering
   interactive rather than minute-scale.

Two things worth knowing about the geometry:

* **The antimeridian needs no special handling here.** Exactly one part in
  ADM_0 spans 360° (Antarctica, which legitimately wraps the pole) and none in
  ADM_1, because GADM already splits its multipolygons at ±180.
* **The grid is not global in latitude.** It runs **75°N to 65°S**, so
  Antarctica and the high Arctic sit outside the data entirely. Renders clip
  the boundary layer to the raster extent; the GeoTIFF mask is clipped by
  construction.

### Performance notes

The batch path exploits two facts about this dataset:

* Every year shares one grid, so the boundary mask is **rasterized once per
  level** and reused across all 31 years (`grid_signature` guards this, and
  recomputes if a raster ever turns up on a different grid).
* Both admin levels render from **one downsample per year**, since the raster
  read dominates.

Boundary geometry is flattened into a single `LineCollection` rather than
~124 000 individual `plot` calls, which took one render from ~60 s to ~2 s.

Whole series, both levels, both formats: roughly 15 minutes.
