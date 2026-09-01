"""Download tests: run against a local HTTP server, never the live archive."""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from satimg.checksums import ChecksumMismatch, md5_file
from satimg.download import download_file

PAYLOAD = bytes((i * 7 + 11) % 256 for i in range(200_000))
PAYLOAD_MD5 = hashlib.md5(PAYLOAD).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    """Serves PAYLOAD, honouring Range unless the server says otherwise."""

    protocol_version = "HTTP/1.0"

    def do_GET(self):
        if self.path == "/missing":
            self.send_error(404)
            return

        server = self.server
        server.request_count += 1

        start = 0
        range_header = self.headers.get("Range")
        honour_range = range_header and not server.ignore_range
        if honour_range:
            start = int(range_header.split("=", 1)[1].split("-", 1)[0])

        body = PAYLOAD[start:]
        declared_length = len(body)
        # Send fewer bytes than advertised to simulate a dropped transfer, which
        # surfaces client-side as http.client.IncompleteRead.
        if server.truncate_after is not None:
            body = body[: server.truncate_after]

        if honour_range:
            self.send_response(206)
            self.send_header(
                "Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"
            )
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(declared_length))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep pytest output clean
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.ignore_range = False
    httpd.truncate_after = None
    httpd.request_count = 0
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    httpd.url = f"http://127.0.0.1:{httpd.server_address[1]}/data.bin"
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def test_downloads_and_verifies(server, tmp_path):
    dest = tmp_path / "data.bin"
    result = download_file(
        server.url, dest, expected_md5=PAYLOAD_MD5, expected_size=len(PAYLOAD)
    )
    assert result.status == "downloaded"
    assert dest.read_bytes() == PAYLOAD
    assert md5_file(dest) == PAYLOAD_MD5
    assert not dest.with_name("data.bin.part").exists()


def test_existing_verified_file_is_not_redownloaded(server, tmp_path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(PAYLOAD)
    result = download_file(server.url, dest, expected_md5=PAYLOAD_MD5)
    assert result.status == "cached"
    assert result.bytes_transferred == 0
    assert server.request_count == 0


def test_existing_corrupt_file_is_replaced(server, tmp_path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"stale contents")
    result = download_file(server.url, dest, expected_md5=PAYLOAD_MD5)
    assert result.status == "downloaded"
    assert dest.read_bytes() == PAYLOAD


def test_resumes_from_a_partial_file(server, tmp_path):
    dest = tmp_path / "data.bin"
    part = tmp_path / "data.bin.part"
    part.write_bytes(PAYLOAD[:50_000])

    result = download_file(server.url, dest, expected_md5=PAYLOAD_MD5)

    assert result.status == "resumed"
    # Only the remaining bytes crossed the wire.
    assert result.bytes_transferred == len(PAYLOAD) - 50_000
    assert dest.read_bytes() == PAYLOAD


def test_no_resume_discards_partial_file(server, tmp_path):
    dest = tmp_path / "data.bin"
    (tmp_path / "data.bin.part").write_bytes(PAYLOAD[:50_000])

    result = download_file(server.url, dest, expected_md5=PAYLOAD_MD5, resume=False)

    assert result.status == "downloaded"
    assert result.bytes_transferred == len(PAYLOAD)
    assert dest.read_bytes() == PAYLOAD


def test_server_ignoring_range_restarts_cleanly(server, tmp_path):
    """A 200 response to a ranged request must not be appended to the .part."""
    server.ignore_range = True
    dest = tmp_path / "data.bin"
    (tmp_path / "data.bin.part").write_bytes(PAYLOAD[:50_000])

    result = download_file(server.url, dest, expected_md5=PAYLOAD_MD5)

    assert dest.read_bytes() == PAYLOAD
    assert result.status == "downloaded"


def test_checksum_mismatch_raises_and_removes_partial(server, tmp_path):
    dest = tmp_path / "data.bin"
    with pytest.raises(ChecksumMismatch):
        download_file(server.url, dest, expected_md5="0" * 32)
    assert not dest.exists()
    assert not dest.with_name("data.bin.part").exists()


def test_size_mismatch_raises(server, tmp_path):
    dest = tmp_path / "data.bin"
    with pytest.raises(OSError, match="size mismatch"):
        download_file(server.url, dest, expected_size=len(PAYLOAD) + 1)
    assert not dest.exists()


def test_truncated_transfer_is_retried_and_completed(server, tmp_path):
    """A short read leaves a .part behind; the retry resumes and finishes it."""
    server.truncate_after = 40_000
    dest = tmp_path / "data.bin"

    def stop_truncating(done, total):
        server.truncate_after = None

    result = download_file(
        server.url,
        dest,
        expected_md5=PAYLOAD_MD5,
        expected_size=len(PAYLOAD),
        retries=1,
        progress=stop_truncating,
    )
    assert dest.read_bytes() == PAYLOAD
    assert result.status == "resumed"


def test_http_error_propagates(server, tmp_path):
    url = server.url.replace("/data.bin", "/missing")
    with pytest.raises(OSError):
        download_file(url, tmp_path / "x.bin", retries=0)


def test_progress_callback_reports_totals(server, tmp_path):
    seen = []
    download_file(
        server.url,
        tmp_path / "data.bin",
        expected_md5=PAYLOAD_MD5,
        progress=lambda done, total: seen.append((done, total)),
    )
    assert seen
    assert seen[-1][0] == len(PAYLOAD)
    assert seen[-1][1] == len(PAYLOAD)
