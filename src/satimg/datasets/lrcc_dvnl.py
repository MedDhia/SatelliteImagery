"""LRCC-DVNL: global annual nighttime lights, 1992-2022.

"Linear trend Registration Continuous Calibrated DVNL" - a DMSP-like global
nighttime light (NTL) time series built to stay usable in low-light and dark-sky
regions, not just bright urban cores.

Published as Tang et al. (2025), *Scientific Data*, with the data deposited in
Harvard Dataverse under doi:10.7910/DVN/15IKI5. See ``docs/lrcc-dvnl.md`` for
the full datasheet, including the caveats that matter before analysis.

The rasters themselves are not committed to this repository (the annual series
alone is ~1.0 GiB). What *is* committed is :data:`MANIFEST_PATH` - the file
index with sizes and MD5 digests - which makes every download reproducible and
verifiable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..dataverse import datafile_url

DATASET_ID = "lrcc-dvnl"
MANIFEST_PATH = Path(__file__).with_name("data") / "lrcc_dvnl_manifest.json"

DOI = "10.7910/DVN/15IKI5"
LANDING_PAGE = f"https://doi.org/{DOI}"
PAPER_DOI = "10.1038/s41597-025-05246-8"
PAPER_URL = f"https://doi.org/{PAPER_DOI}"

#: Nominal CRS of every raster: WGS 84 / Equal Earth Greenwich.
CRS_EPSG = 8857
RESOLUTION_M = 1000
NODATA = 127
DN_MIN = 0
DN_MAX = 63
DTYPE = "int8"

#: Shared grid of the annual GeoTIFFs (verified against LACC_1992.tif).
GRID_WIDTH = 34488
GRID_HEIGHT = 15315
GRID_ORIGIN = (-17243957.96437956, 7982831.5440233825)  # upper-left, metres

FIRST_YEAR = 1992
LAST_YEAR = 2022

CITATION = (
    "Tang, H., Zhong, Y., Deng, J., Xia, H., & Wei, J. (2025). Global nighttime "
    "light dataset from 1992 to 2022 with focus on low-light areas. "
    "Scientific Data, 12, 971. https://doi.org/10.1038/s41597-025-05246-8"
)

DATA_CITATION = (
    "Tang, H., Zhong, Y., & Xia, H. (2025). Global nighttime light dataset from "
    "1992 to 2022 with focus on low-light areas (updated) [Data set]. "
    "Harvard Dataverse. https://doi.org/10.7910/DVN/15IKI5"
)

BIBTEX = """\
@article{tang2025lrccdvnl,
  title   = {Global nighttime light dataset from 1992 to 2022 with focus on
             low-light areas},
  author  = {Tang, Hui and Zhong, Yongde and Deng, Jinyang and Xia, Hongling
             and Wei, Juan},
  journal = {Scientific Data},
  volume  = {12},
  pages   = {971},
  year    = {2025},
  doi     = {10.1038/s41597-025-05246-8}
}

@misc{tang2025lrccdvnldata,
  title     = {Global nighttime light dataset from 1992 to 2022 with focus on
               low-light areas (updated)},
  author    = {Tang, Hui and Zhong, Yongde and Xia, Hongling},
  year      = {2025},
  publisher = {Harvard Dataverse},
  doi       = {10.7910/DVN/15IKI5},
  note      = {Dataset}
}
"""


class ManifestError(Exception):
    """Raised when the committed manifest is missing or malformed."""


@dataclass(frozen=True)
class DataFile:
    """One downloadable file, as indexed in the committed manifest."""

    product: str
    name: str
    dataverse_file_id: int
    size_bytes: int
    md5: str
    content_type: str
    directory_label: str
    year: Optional[int] = None

    @property
    def url(self) -> str:
        return datafile_url(self.dataverse_file_id)

    @property
    def is_archive(self) -> bool:
        return self.name.endswith(".7z")

    def local_path(self, root: str | Path) -> Path:
        """Where this file lives under a download root."""
        return Path(root) / self.product / self.name


@dataclass(frozen=True)
class Product:
    """A coherent group of files within the deposit."""

    id: str
    title: str
    description: str
    file_format: str
    filename_pattern: str
    years: Optional[Sequence[int]] = None


@dataclass(frozen=True)
class Manifest:
    dataset: Dict[str, object]
    products: Dict[str, Product]
    files: List[DataFile]

    def select(
        self,
        product: Optional[str] = None,
        years: Optional[Iterable[int]] = None,
    ) -> List[DataFile]:
        """Files matching a product id and/or a set of years."""
        if product is not None and product not in self.products:
            known = ", ".join(sorted(self.products))
            raise KeyError(f"unknown product {product!r} (known: {known})")
        wanted = set(years) if years is not None else None
        chosen = [
            f
            for f in self.files
            if (product is None or f.product == product)
            and (wanted is None or (f.year is not None and f.year in wanted))
        ]
        return sorted(chosen, key=lambda f: (f.product, f.year or 0, f.name))

    def years(self, product: str) -> List[int]:
        return sorted(
            {f.year for f in self.files if f.product == product and f.year is not None}
        )

    @property
    def total_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files)


@lru_cache(maxsize=1)
def load_manifest(path: Optional[str] = None) -> Manifest:
    """Load and validate the committed file manifest."""
    manifest_path = Path(path) if path else MANIFEST_PATH
    if not manifest_path.exists():
        raise ManifestError(
            f"manifest not found at {manifest_path}; "
            "regenerate it with scripts/refresh_manifest.py"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"manifest at {manifest_path} is not valid JSON: {exc}"
        ) from exc

    try:
        products = {
            pid: Product(id=pid, **spec) for pid, spec in raw["products"].items()
        }
        files = [DataFile(**entry) for entry in raw["files"]]
    except (KeyError, TypeError) as exc:
        raise ManifestError(f"manifest at {manifest_path} is malformed: {exc}") from exc

    if not files:
        raise ManifestError(f"manifest at {manifest_path} indexes no files")

    unknown = {f.product for f in files} - set(products)
    if unknown:
        raise ManifestError(f"files reference undeclared products: {sorted(unknown)}")

    return Manifest(dataset=raw.get("dataset", {}), products=products, files=files)


def annual_series(years: Optional[Iterable[int]] = None) -> List[DataFile]:
    """The 1992-2022 LRCC-DVNL annual rasters - the dataset's headline product."""
    return load_manifest().select(product=DATASET_ID, years=years)
