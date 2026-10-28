"""Tests unitaires complets pour le plugin TheSimsResourceProvider (plugins/thesimsresource/)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.thesimsresource import TheSimsResourceProvider, parse_tsr_browse_html
from src.providers.registry import ProviderRegistry
from src.ui.views.catalog.filter_adapter import build_catalog_api_params


SAMPLE_TSR_BROWSE_HTML = """
<html>
<body>
<div class="pagination">
  <a href="/downloads/browse/category/sims4-mods/skipsetitems/1/page/2/cnt/667/">2</a>
  <a href="/downloads/browse/category/sims4-mods/skipsetitems/1/page/34/cnt/667/">34</a>
</div>
<div class="item-wrapper" data-item='{
  "ID": "1736888",
  "title": "Modern Boho Living Room Set",
  "creator": "Syboulette",
  "publishDate": "1740000000",
  "lastUpdated": "1740500000",
  "description": "A complete Boho living room furniture set for The Sims 4.",
  "featuredImage": "1736888.jpg",
  "keywords": "boho, living room, furniture",
  "revision": 2,
  "RequiredItems": [{"id": "1654321", "title": "Base Mesh Sofa"}],
  "requiredDownloadIds": ["1654321"]
}'>
  <a class="item-title" href="/downloads/details/category/sims4-sets-objects-livingroom/title/modern-boho-living-room-set/id/1736888/">
    Modern Boho Living Room Set
  </a>
</div>
<div class="item-wrapper" data-item='{
  "ID": "1699111",
  "title": "XML Injector",
  "creator": "Scumbumbo",
  "publishDate": "1700000000",
  "lastUpdated": "1705000000",
  "description": "Script library for Sims 4 mods.",
  "featuredImage": "1699111.jpg",
  "keywords": "script, utility, injector",
  "revision": 4
}'>
  <a class="item-title" href="/downloads/details/category/sims4-mods/title/xml-injector/id/1699111/">
    XML Injector
  </a>
</div>
</body>
</html>
"""

SAMPLE_TSR_DETAIL_HTML = """
<html>
<body>
<div class="item-description">
  <p>A complete Boho living room furniture set for The Sims 4.</p>
  <p>Requires <a href="/downloads/details/id/1654321">Base Mesh Sofa</a> and
  <a href="https://www.curseforge.com/sims4/mods/xml-injector">XML Injector</a>.</p>
</div>
<img src="https://images.thesimsresource.com/scaled/3096/w-920/h-690/1736888.jpg" />
</body>
</html>
"""


def test_thesimsresource_registered_and_categories_configured():
    """Vérifie que TheSimsResourceProvider est enregistré dans ProviderRegistry avec ses 12 catégories Sims 4."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("thesimsresource")
    assert prov is not None
    assert isinstance(prov, TheSimsResourceProvider)
    assert prov.provider_name == "thesimsresource"
    assert prov.base_url == "https://www.thesimsresource.com"
    assert "/skipsetitems/1/" in prov.sims4_browse_url
    assert len(prov.CATEGORIES) == 12
    ids = [c["id"] for c in prov.CATEGORIES]
    assert "tsr_mods" in ids
    assert "tsr_clothing" in ids
    assert "tsr_hair" in ids
    assert "tsr_objects" in ids
    assert "tsr_sets" in ids
    assert prov.get_total_pages() >= 12


def test_thesimsresource_parse_browse_html_and_scrape_category():
    """Vérifie le parsing JSON/HTML des cartes div.item-wrapper[data-item] de TSR et scrape_category_page."""
    mods, pages = parse_tsr_browse_html(
        SAMPLE_TSR_BROWSE_HTML,
        category_name="Mods (TSR)",
        base_url="https://www.thesimsresource.com",
        source="thesimsresource",
    )
    assert pages == 34
    assert len(mods) == 2
    assert mods[0]["source"] == "thesimsresource"
    assert mods[0]["remote_id"] == "1736888"
    assert mods[0]["title"] == "Modern Boho Living Room Set"
    assert mods[0]["author"] == "Syboulette"
    assert mods[0]["version"] == "v2"
    assert "1736888" in mods[0]["page_url"]
    assert mods[0]["thumbnail_url"].endswith("/1736888.jpg")
    assert "Base Mesh Sofa" in mods[0]["requirements_text"]

    assert mods[1]["remote_id"] == "1699111"
    assert mods[1]["title"] == "XML Injector"
    assert mods[1]["version"] == "v4"

    prov = TheSimsResourceProvider()
    mock_session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = SAMPLE_TSR_BROWSE_HTML
    mock_session.get.return_value = resp

    with patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):
        cat_mods, detected_pages = prov.scrape_category_page(prov.CATEGORIES[0], page=1)
    assert len(cat_mods) == 2
    assert detected_pages == 34


def test_thesimsresource_get_mod_details_and_ticket_download(tmp_path: Path):
    """Vérifie l'extraction des détails TSR et le flux de téléchargement par ticket (initDownload -> wait -> getdownloadurl)."""
    prov = TheSimsResourceProvider()
    mock_session = MagicMock()

    det_resp = MagicMock()
    det_resp.status_code = 200
    det_resp.text = SAMPLE_TSR_DETAIL_HTML

    init_resp = MagicMock()
    init_resp.status_code = 200
    init_resp.json.return_value = {
        "error": "",
        "ticket": "tsr69f0d8a712345",
        "url": "/downloads/download/itemId/1736888/ticket/tsr69f0d8a712345",
    }

    wait_resp = MagicMock()
    wait_resp.status_code = 200
    wait_resp.text = "<html>Downloading...</html>"

    geturl_resp = MagicMock()
    geturl_resp.status_code = 200
    geturl_resp.json.return_value = {
        "error": "",
        "url": "https://downloads.thesimsresource.com/verify/downloads/1736888/Syboulette_BohoSet.package?mac=abc",
    }

    bin_resp = MagicMock()
    bin_resp.status_code = 200
    bin_resp.url = "https://downloads.thesimsresource.com/verify/downloads/1736888/Syboulette_BohoSet.package?mac=abc"
    bin_resp.headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="Syboulette_BohoSet.package"',
        "Content-Length": "24",
    }
    bin_resp.iter_content.return_value = [b"DBPF\x02\x00\x00\x00\x01\x00\x00\x00dummytsrpkg!"]

    def get_side_effect(url, **kwargs):
        if "a=initDownload" in url:
            return init_resp
        if "/downloads/download/itemId/" in url:
            return wait_resp
        if "a=getdownloadurl" in url:
            return geturl_resp
        if "downloads.thesimsresource.com" in url:
            return bin_resp
        return det_resp

    mock_session.get.side_effect = get_side_effect

    with (
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
        patch("plugins.thesimsresource.scraper.time.sleep"),
    ):
        details = prov.get_mod_details("https://www.thesimsresource.com/downloads/details/id/1736888")
        assert len(details["download_urls"]) == 1
        assert "itemid=1736888" in details["download_urls"][0]["url"]
        assert details["requirements_status"] == "FOUND"
        req_titles = {r["title"] for r in details["requirements_mods"]}
        assert "Base Mesh Sofa" in req_titles
        assert "XML Injector" in req_titles

        dest_file = tmp_path / "1736888_download.zip"
        ok, final_path_str = prov.download_mod_file(
            download_url="https://www.thesimsresource.com/downloads/details/id/1736888",
            dest_path=dest_file,
        )
        assert ok is True
        final_path = Path(final_path_str)
        assert final_path.exists()
        assert final_path.name == "Syboulette_BohoSet.package"
        assert final_path.read_bytes().startswith(b"DBPF")


def test_thesimsresource_filter_adapter():
    """Vérifie que l'adaptateur de filtre UI traduit 'The Sims Resource' en source='thesimsresource'."""
    params = build_catalog_api_params({"source": "The Sims Resource"}, current_page=1, page_size=24)
    assert params["source"] == "thesimsresource"

