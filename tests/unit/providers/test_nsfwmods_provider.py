"""Tests unitaires complets pour le plugin NSFWModsProvider (plugins/nsfwmods/)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.nsfwmods import NSFWModsProvider
from src.providers.registry import ProviderRegistry
from src.ui.views.catalog.filter_adapter import build_catalog_api_params


SAMPLE_NSFWMODS_CATEGORY_HTML = """
<html>
<body>
<div data-pages="2"></div>
<ul>
  <li class="ipsDataItem">
    <div class="ipsDataItem_generic">
      <a class="ipsThumb" href="https://nsfwmods.com/files/file/424-sim-snatcher/">
        <img src="https://nsfwmods.com/uploads/monthly_2021_06/Snatcher.thumb.png" />
      </a>
    </div>
    <div class="ipsDataItem_main">
      <h4 class="ipsDataItem_title">
        <a href="https://nsfwmods.com/files/file/424-sim-snatcher/" title='View the file "Sim Snatcher"'>Sim Snatcher</a>
      </h4>
      <p>By <a data-ipshover="" href="https://nsfwmods.com/profile/27880-colonolnutty/">ColonolNutty</a></p>
      <time datetime="2026-02-04T20:14:05Z"></time>
      <span class="ipsTag">sims4</span>
    </div>
  </li>
</ul>
</body>
</html>
"""

SAMPLE_NSFWMODS_DETAIL_HTML = """
<html>
<body>
<span class="cFileInfo_version">3.11</span>
<a href="https://nsfwmods.com/files/file/424-sim-snatcher/?do=download&amp;csrfKey=e89daefac9bbac8b5701363aab1e525a"
   class="ipsButton ipsButton_fullWidth ipsButton_large ipsButton_important">Download this file</a>
<article>
  <div class="ipsType_richText">
    <p>Sim Snatcher mod for The Sims 4.</p>
  </div>
  <ul class="ipsDataList">
    <li class="ipsDataItem">
      <span class="ipsDataItem_size3"><strong>Requirements</strong></span>
      <div class="cFileInfoData">
        <a href="https://nsfwmods.com/files/file/420-sims-4-community-library/">Sims 4 Community Library</a>
      </div>
    </li>
  </ul>
</article>
</body>
</html>
"""


def test_nsfwmods_registered_and_categories_configured():
    """Vérifie que NSFWModsProvider est enregistré dans ProviderRegistry avec ses 11 catégories Sims."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("nsfwmods")
    assert prov is not None
    assert isinstance(prov, NSFWModsProvider)
    assert prov.provider_name == "nsfwmods"
    assert prov.base_url == "https://nsfwmods.com"
    assert prov.category_url == "https://nsfwmods.com/files/category/287-sims-mods/"
    assert len(prov.CATEGORIES) == 11
    slugs = [c["slug"] for c in prov.CATEGORIES]
    assert "287-sims-mods" in slugs
    assert "364-adult" in slugs
    assert "289-clothing" in slugs
    assert "296-shoes" in slugs
    assert prov.get_total_pages() >= 11


def test_nsfwmods_scrape_category_page():
    """Vérifie le scraping d'une page de catégorie NSFWMods avec source='nsfwmods'."""
    prov = NSFWModsProvider()
    mock_session = MagicMock()

    cat_resp = MagicMock()
    cat_resp.status_code = 200
    cat_resp.text = SAMPLE_NSFWMODS_CATEGORY_HTML

    dl_chk_resp = MagicMock()
    dl_chk_resp.status_code = 301
    dl_chk_resp.headers = {"Location": "https://nsfwmods.com/files/file/424-sim-snatcher/"}

    def side_effect(url, **kwargs):
        if "?do=download" in url:
            return dl_chk_resp
        return cat_resp

    mock_session.get.side_effect = side_effect

    with patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):
        mods, detected_pages = prov.scrape_category_page(prov.CATEGORIES[0], page=1)

    assert detected_pages == 2
    assert len(mods) == 1
    mod = mods[0]
    assert mod["source"] == "nsfwmods"
    assert mod["remote_id"] == "424"
    assert mod["title"] == "Sim Snatcher"
    assert mod["author"] == "ColonolNutty"
    assert mod["page_url"] == "https://nsfwmods.com/files/file/424-sim-snatcher/"


def test_nsfwmods_get_mod_details_and_download(tmp_path: Path):
    """Vérifie l'extraction des détails (bouton csrfKey + requirements) et le téléchargement binaire."""
    prov = NSFWModsProvider()
    mock_session = MagicMock()

    det_resp = MagicMock()
    det_resp.status_code = 200
    det_resp.text = SAMPLE_NSFWMODS_DETAIL_HTML
    det_resp.headers = {"Content-Type": "text/html"}

    bin_resp = MagicMock()
    bin_resp.status_code = 200
    bin_resp.headers = {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="SimSnatcher_v3.11.zip"',
    }
    bin_resp.content = b"PK\x03\x04dummyzipcontent"
    bin_resp.iter_content.return_value = [b"PK\x03\x04dummyzipcontent"]

    def get_side_effect(url, **kwargs):
        if "csrfKey=" in url:
            return bin_resp
        return det_resp

    mock_session.get.side_effect = get_side_effect

    with patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):
        details = prov.get_mod_details("https://nsfwmods.com/files/file/424-sim-snatcher/")
        assert details["version_str"] == "3.11"
        assert len(details["download_urls"]) >= 1
        assert "csrfKey=e89daefac9bbac8b5701363aab1e525a" in details["download_urls"][0]["url"]
        assert len(details["requirements_mods"]) >= 1

        dest_file = tmp_path / "SimSnatcher.zip"
        ok, path_or_msg = prov.download_mod_file(
            download_url="https://nsfwmods.com/files/file/424-sim-snatcher/",
            dest_path=dest_file,
        )
        assert ok is True
        assert dest_file.exists()
        assert dest_file.read_bytes().startswith(b"PK\x03\x04")


def test_nsfwmods_filter_adapter():
    """Vérifie que l'adaptateur de filtre UI traduit 'NSFWMods' en source='nsfwmods'."""
    params = build_catalog_api_params({"source": "NSFWMods"}, current_page=1, page_size=24)
    assert params["source"] == "nsfwmods"
