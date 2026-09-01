"""Live checks against Harvard Dataverse.

Excluded by default (see ``addopts`` in pyproject.toml). Run explicitly with::

    pytest -m network

These are the tests that catch upstream drift: a republished deposit, changed
file ids, or a new checksum. They download only a small byte range, not files.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from satimg import USER_AGENT
from satimg.datasets import lrcc_dvnl
from satimg.dataverse import fetch_dataset_metadata

pytestmark = pytest.mark.network


def _ranged_get(url: str, last_byte: int = 255):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{last_byte}"}
    )
    return urllib.request.urlopen(request, timeout=60)


def test_committed_manifest_matches_upstream():
    """Every id, size and MD5 in the manifest still matches the live deposit."""
    data = fetch_dataset_metadata(lrcc_dvnl.DOI)
    upstream = {
        entry["dataFile"]["id"]: entry["dataFile"]
        for entry in data["latestVersion"]["files"]
    }

    manifest = lrcc_dvnl.load_manifest()
    assert len(manifest.files) == len(upstream), "file count changed upstream"

    for data_file in manifest.files:
        live = upstream.get(data_file.dataverse_file_id)
        assert live is not None, f"{data_file.name} no longer exists upstream"
        assert live["filename"] == data_file.name
        assert live["filesize"] == data_file.size_bytes
        assert live["checksum"]["value"].lower() == data_file.md5


def test_access_api_serves_ranged_requests():
    """Resume depends on 206 responses; assert the archive still allows them."""
    data_file = lrcc_dvnl.annual_series([1992])[0]
    with _ranged_get(data_file.url) as response:
        assert response.status == 206
        assert len(response.read()) == 256


def test_default_urllib_user_agent_is_rejected():
    """Documents why satimg always sends its own User-Agent.

    Harvard Dataverse's edge answers ``Python-urllib/*`` with 403. If this ever
    starts passing, the workaround in satimg.download is no longer needed.
    """
    data_file = lrcc_dvnl.annual_series([1992])[0]
    request = urllib.request.Request(
        data_file.url, headers={"User-Agent": "Python-urllib/3.11"}
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=60)
    assert excinfo.value.code == 403


def test_downloaded_bytes_are_a_tiff():
    data_file = lrcc_dvnl.annual_series([1992])[0]
    with _ranged_get(data_file.url, last_byte=3) as response:
        magic = response.read()
    # Little-endian classic TIFF ("II" + 42) or BigTIFF ("II" + 43).
    assert magic[:2] == b"II"
    assert magic[2] in (42, 43)
