"""Minimal Harvard Dataverse access helpers."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict

from . import USER_AGENT

DEFAULT_HOST = "https://dataverse.harvard.edu"


def datafile_url(file_id: int, host: str = DEFAULT_HOST) -> str:
    """Direct download URL for a Dataverse file id (303-redirects to S3)."""
    return f"{host.rstrip('/')}/api/access/datafile/{int(file_id)}"


def dataset_metadata_url(doi: str, host: str = DEFAULT_HOST) -> str:
    """Native-API URL returning the full metadata record for a dataset DOI."""
    persistent_id = doi if doi.startswith("doi:") else f"doi:{doi}"
    return (
        f"{host.rstrip('/')}/api/datasets/:persistentId/?persistentId={persistent_id}"
    )


def fetch_dataset_metadata(
    doi: str, host: str = DEFAULT_HOST, timeout: float = 60.0
) -> Dict[str, Any]:
    """Fetch and parse a dataset's Dataverse metadata record."""
    request = urllib.request.Request(
        dataset_metadata_url(doi, host),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "OK":
        raise RuntimeError(f"Dataverse returned status {payload.get('status')!r}")
    return payload["data"]
