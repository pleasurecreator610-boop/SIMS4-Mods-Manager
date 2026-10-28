"""Tests unitaires complets pour le plugin CurseForgeProvider (plugins/curseforge/)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.curseforge import CurseForgeProvider, parse_curseforge_search_html
from src.providers.registry import ProviderRegistry
from src.ui.views.catalog.filter_adapter import build_catalog_api_params


SAMPLE_CURSEFORGE_SEARCH_HTML = """
<html>
<body>
<div class="pagination">
  <button>1</button>
  <button>2</button>
  <button>18</button>
</div>
<div class="project-card">
  <a class="name" href="/sims4/mods/xml-injector"><span>XML Injector</span></a>
  <a class="author-name" href="https://www.curseforge.com/members/scumbumbomods"><span>ScumbumboMods</span></a>
  <p class="description">A script library for mods that only need to add interactions.</p>
  <img class="row-image" src="https://media.forgecdn.net/avatars/thumbnails/618/926/64/64/638008568504271893.png" />
  <li class="detail-updated"><span>Oct 2, 2024</span></li>
  <a class="category-link" href="/sims4/search?category=mods-utilities">Utilities</a>
</div>
<div class="project-card">
  <a class="name" href="/sims4/mods/social-activities-visit-friends-family-and-more">
    <span>Social Activities (Visit Friends, Family and more)</span>
  </a>
  <a class="author-name" href="https://www.curseforge.com/members/lms"><span>LittleMsSam</span></a>
  <p class="description">Send your Sims to visit Friends and Family!</p>
  <img class="row-image" src="https://media.forgecdn.net/avatars/thumbnails/619/100/64/64/social.png" />
  <li class="detail-updated"><span>Feb 26, 2026</span></li>
</div>
</body>
</html>
"""

SAMPLE_CURSEFORGE_DETAIL_HTML = """
<html>
<body>
<section class="section-project-id">
  <span>Project ID</span>
  <span>694283</span>
</section>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"project":{"id":694283,"mainFile":{"id":7021809,"fileName":"XmlInjector_Script_v4.2.zip","displayName":"XmlInjector_Script_v4.2","fileLength":28199}}}}}
</script>
<div class="project-description">
  <p>XML Injector v4.2 for The Sims 4.</p>
  <p>Requires <a href="https://www.curseforge.com/sims4/mods/sims-4-community-library">Sims 4 Community Library</a>.</p>
</div>
</body>
</html>
"""

SAMPLE_CURSEFORGE_RELATIONS_HTML = """
<html>
<body>
<div class="project-card">
  <a class="name" href="/sims4/mods/xml-injector"><span>XML Injector</span></a>
</div>
</body>
</html>
"""


def test_curseforge_registered_and_categories_configured():
    """Vérifie que CurseForgeProvider est enregistré dans ProviderRegistry avec ses 9 catégories Sims 4."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("curseforge")
    assert prov is not None
    assert isinstance(prov, CurseForgeProvider)
    assert prov.provider_name == "curseforge"
    assert prov.base_url == "https://www.curseforge.com"
    assert prov.sims4_url == "https://www.curseforge.com/sims4"
    assert len(prov.CATEGORIES) == 9
    ids = [c["id"] for c in prov.CATEGORIES]
    assert "cf_mods_gameplay" in ids
    assert "cf_mods_utilities" in ids
    assert "cf_create_a_sim" in ids
    assert "cf_build_buy" in ids
    assert "cf_translations" in ids
    assert prov.get_total_pages() >= 9


def test_curseforge_parse_search_html_and_scrape_category():
    """Vérifie le parsing HTML des cartes .project-card CurseForge et scrape_category_page."""
    mods, pages = parse_curseforge_search_html(
        SAMPLE_CURSEFORGE_SEARCH_HTML,
        category_name="Mods - Utilities (CurseForge)",
        base_url="https://www.curseforge.com",
        source="curseforge",
    )
    assert pages == 18
    assert len(mods) == 2
    assert mods[0]["source"] == "curseforge"
    assert mods[0]["remote_id"] == "xml-injector"
    assert mods[0]["title"] == "XML Injector"
    assert mods[0]["author"] == "ScumbumboMods"
    assert mods[0]["page_url"] == "https://www.curseforge.com/sims4/mods/xml-injector"
    assert mods[1]["remote_id"] == "social-activities-visit-friends-family-and-more"

    prov = CurseForgeProvider()
    mock_session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = SAMPLE_CURSEFORGE_SEARCH_HTML
    mock_session.get.return_value = resp

    with patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):
        cat_mods, detected_pages = prov.scrape_category_page(prov.CATEGORIES[1], page=1)
    assert len(cat_mods) == 2
    assert detected_pages == 18


def test_curseforge_get_mod_details_and_download(tmp_path: Path):
    """Vérifie l'extraction du Project ID / File ID, des dépendances et le téléchargement binaire via /api/v1/mods."""
    prov = CurseForgeProvider()
    mock_session = MagicMock()

    det_resp = MagicMock()
    det_resp.status_code = 200
    det_resp.text = SAMPLE_CURSEFORGE_DETAIL_HTML

    rel_resp = MagicMock()
    rel_resp.status_code = 200
    rel_resp.text = SAMPLE_CURSEFORGE_RELATIONS_HTML

    bin_resp = MagicMock()
    bin_resp.status_code = 200
    bin_resp.url = "https://edge.forgecdn.net/files/7021/809/XmlInjector_Script_v4.2.zip"
    bin_resp.headers = {
        "Content-Type": "application/zip",
        "Content-Length": "23",
    }
    bin_resp.iter_content.return_value = [b"PK\x03\x04dummyxmlinjectorzip"]

    def get_side_effect(url, **kwargs):
        if "/api/v1/mods/" in url and "/download" in url:
            return bin_resp
        if "/relations/dependencies" in url:
            return rel_resp
        return det_resp

    mock_session.get.side_effect = get_side_effect

    with patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):
        details = prov.get_mod_details("https://www.curseforge.com/sims4/mods/social-activities")
        assert len(details["download_urls"]) == 1
        dl_entry = details["download_urls"][0]
        assert dl_entry["url"] == "https://www.curseforge.com/api/v1/mods/694283/files/7021809/download"
        assert "7021809" in dl_entry["name"]
        assert details["requirements_status"] == "FOUND"
        req_titles = {r["title"] for r in details["requirements_mods"]}
        assert "XML Injector" in req_titles
        assert "Sims 4 Community Library" in req_titles

        dest_file = tmp_path / "XmlInjector.zip"
        ok, path_or_msg = prov.download_mod_file(
            download_url="https://www.curseforge.com/sims4/mods/xml-injector",
            dest_path=dest_file,
        )
        assert ok is True
        assert dest_file.exists()
        assert dest_file.read_bytes().startswith(b"PK\x03\x04")


def test_curseforge_filter_adapter():
    """Vérifie que l'adaptateur de filtre UI traduit 'CurseForge' en source='curseforge'."""
    params = build_catalog_api_params({"source": "CurseForge"}, current_page=1, page_size=24)
    assert params["source"] == "curseforge"
