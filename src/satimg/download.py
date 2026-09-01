"""Resumable, checksum-verified HTTP downloads.

Deliberately stdlib-only so the import pipeline runs on a bare Python install.

Two environment-specific details are baked in because they are easy to
rediscover the hard way:

* Harvard Dataverse's edge rejects the default ``Python-urllib/x.y``
  User-Agent with HTTP 403, so a descriptive User-Agent is always sent.
* ``/api/access/datafile/{id}`` answers with a 303 redirect to a presigned
  S3 URL. ``HEAD`` against that URL is 403, so file sizes must come from the
  manifest rather than a preflight request. Ranged ``GET`` works (206), which
  is what makes resume possible.
"""

from __future__ import annotations

import http.client
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import USER_AGENT
from .checksums import ChecksumMismatch, md5_file

CHUNK_SIZE = 1024 * 1024
DEFAULT_TIMEOUT = 120.0
DEFAULT_RETRIES = 4

ProgressCallback = Callable[[int, Optional[int]], None]
"""Called with (bytes_downloaded_so_far, total_bytes_or_None)."""


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    status: str  # "downloaded", "resumed" or "cached"
    bytes_transferred: int
    md5: Optional[str]

    @property
    def skipped(self) -> bool:
        return self.status == "cached"


def _open(url: str, offset: int, timeout: float):
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=timeout
    )


def _total_size(response, offset: int) -> Optional[int]:
    """Total size of the complete file, inferred from the response headers."""
    if response.status == 206:
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.rsplit("/", 1)[1].strip()
            if total.isdigit():
                return int(total)
    length = response.headers.get("Content-Length")
    if length and length.isdigit():
        return int(length) + offset
    return None


def download_file(
    url: str,
    dest: str | Path,
    *,
    expected_md5: Optional[str] = None,
    expected_size: Optional[int] = None,
    resume: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    chunk_size: int = CHUNK_SIZE,
    progress: Optional[ProgressCallback] = None,
) -> DownloadResult:
    """Download ``url`` to ``dest``, resuming and verifying where possible.

    An already-complete ``dest`` whose MD5 matches ``expected_md5`` is left
    untouched and reported as ``cached``. Bytes land in a sibling ``.part``
    file and are only moved into place after verification, so ``dest`` is
    never a partial file.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    if dest.exists():
        if expected_md5 is None or md5_file(dest) == expected_md5.lower():
            size = dest.stat().st_size
            if progress:
                progress(size, size)
            return DownloadResult(dest, "cached", 0, expected_md5)
        dest.unlink()

    if not resume and part.exists():
        part.unlink()

    transferred = 0
    resumed = False
    last_error: Optional[BaseException] = None

    for attempt in range(retries + 1):
        offset = part.stat().st_size if part.exists() else 0
        if expected_size is not None and offset > expected_size:
            part.unlink()
            offset = 0
        if expected_size is not None and offset == expected_size:
            break  # a previous attempt already fetched every byte

        try:
            with _open(url, offset, timeout) as response:
                # A server that ignores Range replies 200 and streams the whole
                # file; restart from byte zero rather than corrupting the .part.
                if offset and response.status != 206:
                    offset = 0
                else:
                    resumed = resumed or bool(offset)
                total = _total_size(response, offset)
                if progress and offset:
                    progress(offset, total)

                mode = "ab" if offset else "wb"
                written = offset
                with open(part, mode) as handle:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        handle.write(chunk)
                        written += len(chunk)
                        transferred += len(chunk)
                        if progress:
                            progress(written, total)
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            OSError,
            EOFError,
        ) as exc:
            # 4xx other than a rate limit will not fix themselves; stop early.
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (
                408,
                429,
                500,
                502,
                503,
                504,
            ):
                raise
            last_error = exc
            if attempt == retries:
                raise
            time.sleep(2 ** (attempt + 1))
            continue

        # A dropped transfer does not raise: http.client.read(amt) returns b""
        # rather than IncompleteRead when the body is short of Content-Length.
        # Detect it here and resume, instead of discarding good bytes.
        #
        # Only the server's own reported total proves truncation. If it sent
        # everything it promised and the size still disagrees with the manifest,
        # retrying cannot help - fall through to the size check below.
        target = total if total is not None else expected_size
        if target is None or written >= target:
            break
        last_error = OSError(
            f"transfer for {dest.name} ended at {written} of {target} bytes"
        )
        if attempt == retries:
            raise last_error
        time.sleep(2 ** (attempt + 1))

    actual_size = part.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        part.unlink()
        raise OSError(
            f"size mismatch for {dest.name}: expected {expected_size} bytes, "
            f"got {actual_size}"
        )

    digest: Optional[str] = None
    if expected_md5 is not None:
        digest = md5_file(part)
        if digest != expected_md5.lower():
            part.unlink()
            raise ChecksumMismatch(dest, expected_md5, digest)

    os.replace(part, dest)
    return DownloadResult(
        dest, "resumed" if resumed else "downloaded", transferred, digest
    )
