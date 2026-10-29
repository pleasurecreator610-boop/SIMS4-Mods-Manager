"""Tests unitaires pour BaseFileDownloader."""

import pytest
import httpx
from src.infrastructure.network.download_pipeline import (
    BaseFileDownloader,
    DownloadSecurityError,
)


def test_download_pipeline_security_rejection(tmp_path):
    dest = tmp_path / "mod.zip"
    downloader = BaseFileDownloader()

    # SSRF URL targeting metadata
    with pytest.raises(DownloadSecurityError):
        downloader.download_file("http://169.254.169.254/secret", dest)

    # Localhost SSRF
    with pytest.raises(DownloadSecurityError):
        downloader.download_file("http://127.0.0.1:8080/exploit", dest)


def test_download_pipeline_mock_stream(tmp_path):
    dest = tmp_path / "downloaded_mod.zip"

    # Mock client with custom transport
    content = b"Sims4 Mod File Content - PK\x03\x04"

    def handler(request):
        return httpx.Response(200, content=content, headers={"Content-Length": str(len(content))})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = BaseFileDownloader(client=client, allow_local=True)

    progress_calls = []

    def on_prog(percent, name):
        progress_calls.append(percent)

    saved_path, sha256_hex = downloader.download_file(
        "http://localhost/test.zip",
        dest,
        progress_cb=on_prog,
    )

    assert saved_path == dest
    assert dest.exists()
    assert dest.read_bytes() == content
    assert len(sha256_hex) == 64
    assert 100 in progress_calls
