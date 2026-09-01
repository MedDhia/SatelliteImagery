#!/usr/bin/env python3
"""Regenerate the committed LRCC-DVNL manifest from the Harvard Dataverse API.

The manifest is the actual "import": it pins every file id, size and MD5 so
downloads are reproducible and tamper-evident without storing ~2 GiB of rasters
in git. Re-run this if the deposit publishes a new version, then commit the
diff so the change in upstream data is reviewable.

    python scripts/refresh_manifest.py            # write the manifest
    python scripts/refresh_manifest.py --check    # CI: fail if out of date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from satimg.datasets import lrcc_dvnl  # noqa: E402
from satimg.dataverse import fetch_dataset_metadata  # noqa: E402

# Dataverse directory labels -> our product ids. Curated, because the labels
# are free text upstream and the filenames do not match the product names
# used in the paper (the annual LRCC-DVNL rasters are named "LACC_<year>.tif").
PRODUCTS: Dict[str, Dict[str, Any]] = {
    "LRCC-DVNL data": {
        "id": "lrcc-dvnl",
        "title": "LRCC-DVNL annual nighttime lights (1992-2022)",
        "description": (
            "Headline product: DMSP-like annual NTL composites, continuity- "
            "and trend-calibrated across the DMSP/OLS and VIIRS eras. One "
            "GeoTIFF per year, DN 0-63, nodata 127."
        ),
        "file_format": "GeoTIFF",
        "filename_pattern": "LACC_{year}.tif",
    },
    "Calibrated DVNL files": {
        "id": "c-dvnl",
        "title": "Calibrated DVNL (C-DVNL, 2013-2022)",
        "description": (
            "Intermediate product: the repaired (2013) and extended "
            "(2020-2022) calibrated DVNL composites, before continuity "
            "calibration. 7z-compressed GeoTIFFs."
        ),
        "file_format": "GeoTIFF (7z archive)",
        "filename_pattern": "C_DVNL {year}.tif.7z",
    },
    "Cloud Raster File": {
        "id": "crf",
        "title": "LRCC-DVNL multidimensional Cloud Raster Format (1992-2022)",
        "description": (
            "The whole 1992-2022 series as a single Esri CRF multidimensional "
            "raster (~673 MiB compressed). Convenient in ArcGIS Pro; the "
            "annual GeoTIFFs are the portable option."
        ),
        "file_format": "Esri CRF (7z archive)",
        "filename_pattern": "LRCC_DVNL_1992_2022.crf.7z",
    },
}

YEAR_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-4]\d)(?!\d)")


def extract_year(filename: str) -> Optional[int]:
    """Single 4-digit year in a filename, or None if it is not year-specific."""
    matches = YEAR_RE.findall(filename)
    unique = {int(m) for m in matches}
    return unique.pop() if len(unique) == 1 else None


def citation_field(blocks: Dict[str, Any], name: str) -> Any:
    for block in blocks.values():
        for field in block.get("fields", []):
            if field.get("typeName") == name:
                return field.get("value")
    return None


def build_manifest() -> Dict[str, Any]:
    data = fetch_dataset_metadata(lrcc_dvnl.DOI)
    version = data["latestVersion"]
    blocks = version.get("metadataBlocks", {})

    authors = [
        {
            "name": entry.get("authorName", {}).get("value"),
            "affiliation": entry.get("authorAffiliation", {}).get("value"),
            "orcid": entry.get("authorIdentifier", {}).get("value"),
        }
        for entry in (citation_field(blocks, "author") or [])
    ]
    title = citation_field(blocks, "title")
    license_info = version.get("license") or {}

    files = []
    seen_products = set()
    for entry in version["files"]:
        data_file = entry["dataFile"]
        label = entry.get("directoryLabel")
        if label not in PRODUCTS:
            raise SystemExit(
                f"unmapped directory label {label!r} for file "
                f"{data_file.get('filename')!r}; update PRODUCTS in this script"
            )
        product_id = PRODUCTS[label]["id"]
        seen_products.add(product_id)
        checksum = data_file.get("checksum") or {}
        if checksum.get("type") != "MD5":
            raise SystemExit(
                f"expected an MD5 checksum for {data_file.get('filename')!r}, "
                f"got {checksum.get('type')!r}"
            )
        files.append(
            {
                "product": product_id,
                "name": data_file["filename"],
                "year": extract_year(data_file["filename"]),
                "dataverse_file_id": data_file["id"],
                "size_bytes": data_file["filesize"],
                "md5": checksum["value"].lower(),
                "content_type": data_file.get("contentType", ""),
                "directory_label": label,
            }
        )

    files.sort(key=lambda f: (f["product"], f["year"] or 0, f["name"]))

    products = {}
    for spec in PRODUCTS.values():
        product_id = spec["id"]
        if product_id not in seen_products:
            continue
        years = sorted(
            {f["year"] for f in files if f["product"] == product_id} - {None}
        )
        products[product_id] = {
            "title": spec["title"],
            "description": spec["description"],
            "file_format": spec["file_format"],
            "filename_pattern": spec["filename_pattern"],
            "years": years or None,
        }

    return {
        "schema_version": 1,
        "dataset": {
            "id": lrcc_dvnl.DATASET_ID,
            "title": title,
            "doi": lrcc_dvnl.DOI,
            "landing_page": lrcc_dvnl.LANDING_PAGE,
            "repository": "Harvard Dataverse",
            "dataverse_version": (
                f"{version.get('versionNumber')}.{version.get('versionMinorNumber')}"
            ),
            "release_time": version.get("releaseTime"),
            "license": {
                "name": license_info.get("name"),
                "uri": license_info.get("uri"),
                "spdx_id": license_info.get("rightsIdentifier"),
            },
            "authors": authors,
            "paper_doi": lrcc_dvnl.PAPER_DOI,
            "grid": {
                "crs_epsg": lrcc_dvnl.CRS_EPSG,
                "crs_name": "WGS 84 / Equal Earth Greenwich",
                "resolution_m": lrcc_dvnl.RESOLUTION_M,
                "width": lrcc_dvnl.GRID_WIDTH,
                "height": lrcc_dvnl.GRID_HEIGHT,
                "dtype": lrcc_dvnl.DTYPE,
                "nodata": lrcc_dvnl.NODATA,
                "valid_dn_range": [lrcc_dvnl.DN_MIN, lrcc_dvnl.DN_MAX],
            },
        },
        "products": products,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed manifest differs from upstream",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=lrcc_dvnl.MANIFEST_PATH,
        help="manifest path to write (default: the packaged manifest)",
    )
    args = parser.parse_args()

    rendered = json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not args.output.exists():
            print(f"manifest missing: {args.output}", file=sys.stderr)
            return 1
        if args.output.read_text(encoding="utf-8") != rendered:
            print(
                f"manifest is out of date: {args.output}\n"
                "run: python scripts/refresh_manifest.py",
                file=sys.stderr,
            )
            return 1
        print(f"manifest is up to date: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    manifest = json.loads(rendered)
    total = sum(f["size_bytes"] for f in manifest["files"])
    print(
        f"wrote {args.output} "
        f"({len(manifest['files'])} files, {len(manifest['products'])} products, "
        f"{total / 1024**3:.2f} GiB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
