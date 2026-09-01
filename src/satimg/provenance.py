"""Sidecar records tracking local modifications to downloaded files.

Repairing a raster's CRS rewrites its GeoTIFF headers, so the file no longer
matches the MD5 published in the manifest even though every pixel is
unchanged. Without a record of that, ``satimg lrcc-dvnl verify`` cannot tell a
deliberate repair from real corruption.

Each repair therefore drops a small JSON sidecar next to the file holding the
pre-repair digest, which keeps the chain back to the published checksum intact.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__

SIDECAR_SUFFIX = ".satimg.json"


def sidecar_path(path: str | Path) -> Path:
    """Path of the provenance sidecar belonging to ``path``."""
    path = Path(path)
    return path.with_name(path.name + SIDECAR_SUFFIX)


def write_repair_record(
    path: str | Path,
    *,
    original_md5: str,
    original_size: int,
    operation: str,
    details: Optional[Dict[str, Any]] = None,
) -> Path:
    """Record that ``path`` was modified locally, preserving its former digest.

    If the file was already repaired once, the original digest from the first
    record is carried forward so it always refers to the downloaded bytes.
    """
    target = sidecar_path(path)
    existing = read_record(path)
    if existing and existing.get("original_md5"):
        original_md5 = existing["original_md5"]
        original_size = existing.get("original_size", original_size)

    operation_entry = {
        "operation": operation,
        "details": details or {},
        "tool": f"satimg {__version__}",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    record = {
        "file": Path(path).name,
        "original_md5": original_md5,
        "original_size": original_size,
        "operations": [*(existing or {}).get("operations", []), operation_entry],
    }
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return target


def read_record(path: str | Path) -> Optional[Dict[str, Any]]:
    """Read the provenance sidecar for ``path``, or None if there isn't one."""
    target = sidecar_path(path)
    if not target.exists():
        return None
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return record if isinstance(record, dict) else None


def original_md5(path: str | Path) -> Optional[str]:
    """The file's MD5 as downloaded, if it has been locally modified."""
    record = read_record(path)
    if not record:
        return None
    digest = record.get("original_md5")
    return digest.lower() if isinstance(digest, str) else None
