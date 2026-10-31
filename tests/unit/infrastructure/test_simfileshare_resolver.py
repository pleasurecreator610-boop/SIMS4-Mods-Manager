"""Tests unitaires pour SimFileShareResolver (src/infrastructure/network/simfileshare_resolver.py)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.infrastructure.network.simfileshare_resolver import SimFileShareResolver


SAMPLE_SFS_DOWNLOAD_PAGE = """
<html>
<body>
<div class="file-info">
  <h2>LumpinousToolbox.ts4script</h2>
  <p>File size: 1.2 MB</p>
  <a class="download-btn" href="https://simfileshare.net/download/123456/?dl">Download (1.2 MB)</a>
</div>
</body>
</html>
"""


def test_is_simfileshare_url():
    """Vérifie la détection d'URLs SimFileShare."""
    assert SimFileShareResolver.is_simfileshare_url("https://simfileshare.net/download/123456/")
    assert SimFileShareResolver.is_simfileshare_url("http://www.simfileshare.net/download/7890/")
    assert SimFileShareResolver.is_simfileshare_url("https://simfileshare.net/folder/54321/")
    assert not SimFileShareResolver.is_simfileshare_url("https://curseforge.com/sims4/mods/xml-injector")
    assert not SimFileShareResolver.is_simfileshare_url("")


def test_extract_ids():
    """Vérifie l'extraction des IDs de fichiers et de dossiers."""
    assert SimFileShareResolver.extract_file_id("https://simfileshare.net/download/999888/") == "999888"
    assert SimFileShareResolver.extract_file_id("https://simfileshare.net/filedetails/112233/") == "112233"
    assert SimFileShareResolver.extract_file_id("https://simfileshare.net/?file=445566") == "445566"
    assert SimFileShareResolver.extract_folder_id("https://simfileshare.net/folder/778899/") == "778899"


def test_resolve_direct_download_html_parsing():
    """Vérifie la résolution à partir du HTML de SimFileShare."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.text = SAMPLE_SFS_DOWNLOAD_PAGE
    mock_resp.url = "https://simfileshare.net/download/123456/"

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    with patch("src.infrastructure.network.simfileshare_resolver.SessionManager.get_http_session", return_value=mock_session):
        direct_url, filename, _ = SimFileShareResolver.resolve_direct_download("https://simfileshare.net/download/123456/")
        assert direct_url is not None
        assert "123456" in direct_url
        assert filename == "LumpinousToolbox.ts4script"


def test_download_mod_file_mock(tmp_path: Path):
    """Vérifie le téléchargement en streaming via SimFileShareResolver."""
    resolver = SimFileShareResolver()
    dest = tmp_path / "LumpinousToolbox.ts4script"

    mock_stream_resp = MagicMock()
    mock_stream_resp.status_code = 200
    mock_stream_resp.headers = {"Content-Length": "12", "Content-Type": "application/octet-stream"}
    mock_stream_resp.iter_content.return_value = [b"Sims4Script!"]
    mock_stream_resp.__enter__.return_value = mock_stream_resp
    mock_stream_resp.__exit__.return_value = False

    mock_session = MagicMock()
    mock_session.get.return_value = mock_stream_resp

    with patch("src.infrastructure.network.simfileshare_resolver.SessionManager.get_http_session", return_value=mock_session):
        with patch.object(SimFileShareResolver, "resolve_direct_download", return_value=("https://simfileshare.net/download/123456/?dl", "LumpinousToolbox.ts4script", 12)):
            ok, res_path = resolver.download_mod_file("https://simfileshare.net/download/123456/", dest)
            assert ok
            assert Path(res_path).exists()
            assert Path(res_path).read_bytes() == b"Sims4Script!"

