# Third-party terms for the figures in this directory

The repository's MIT licence covers the **code**. It does not cover the images
in this directory, which combine two sources with different, stricter terms.

## Boundaries — GADM 4.1

Every figure here draws administrative boundaries from
[GADM](https://gadm.org) version 4.1, whose licence states:

> The data are freely available for academic use and other non-commercial use.
> Redistribution or commercial use is not allowed without prior permission.

What that means in practice:

* **Permitted** — reproducing these figures in academic or other
  non-commercial work, with attribution to GADM.
* **Not permitted** — commercial use, or redistributing them as boundary data.

Attribute as: *administrative boundaries from GADM 4.1 (gadm.org)*.

## Imagery — LRCC-DVNL

The pixel values are LRCC-DVNL, 1992–2022:

> Tang, H., Zhong, Y., Deng, J., Xia, H., & Wei, J. (2025). Global nighttime
> light dataset from 1992 to 2022 with focus on low-light areas.
> *Scientific Data*, 12, 971. https://doi.org/10.1038/s41597-025-05246-8

The Harvard Dataverse deposit is labelled **CC0 1.0** while the paper states
**CC BY-NC-ND 4.0**. That contradiction is unresolved upstream; the
non-commercial reading is the safe one, and it agrees with GADM's terms anyway.
See [`../docs/lrcc-dvnl.md`](../docs/lrcc-dvnl.md).

## What is *not* in this directory

No GADM data is committed. The vector layers, the prepared GeoPackage caches,
the boundary-mask GeoTIFF bands and the `GID`-keyed zonal tables all stay under
`data/`, which is gitignored. What is committed is rendered raster imagery at
gallery resolution, from which the source geometry cannot be recovered.

If you need a redistributable version of these figures, re-render them against
[Natural Earth](https://www.naturalearthdata.com) (public domain) instead: the
pipeline is source-agnostic apart from the GADM constants and layer names in
`src/satimg/boundaries.py`.
