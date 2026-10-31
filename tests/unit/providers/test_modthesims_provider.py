"""Tests unitaires complets pour le plugin ModTheSimsProvider (plugins/modthesims/)."""

from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from plugins.modthesims import ModTheSimsProvider
from plugins.modthesims.parsers import (
    extract_item_id,
    parse_mts_browse_html,
    extract_mts_download_links,
    extract_mts_requirements,
)
from src.core.session_manager import SessionManager
from src.domain.models.category_mapping import CategoryMappingService
from src.providers.registry import ProviderRegistry


SAMPLE_MTS_BROWSE_HTML = """
<div id="content">
    <ul class="download-list">
        <li class="smol-card-component">
            <div class="downloadtitle">
                <a href="/d/701054/realistic-cooking-mod.html">Realistic Cooking Mod</a>
            </div>
            <div class="downloadcreator">
                by <span class="downloadcreatorname"><a href="/m/102554">SrslySims</a></span> on 15th October 2026
            </div>
            <a href="/d/701054/realistic-cooking-mod.html">
                <img class="featuredimage" src="//thumbs.modthesims.info/thumb/701054.jpg" />
            </a>
            <div class="downloadPreview">
                A complete overhaul of cooking recipes and groceries in The Sims 4. more...
            </div>
        </li>
        <li class="smol-card-component">
            <div class="downloadtitle">
                <a href="/d/685412/xml-injector-v4.html">XML Injector v4</a>
            </div>
            <div class="downloadcreator">
                by <span class="downloadcreatorname"><a href="/m/55412">Scumbumbo</a></span> on 20th January 2026
            </div>
            <a href="/d/685412/xml-injector-v4.html">
                <img class="featuredimage" src="https://modthesims.info/images/xml.jpg" />
            </a>
            <div class="downloadPreview">
                Allows modders to inject custom snippets without overwriting tuning.
            </div>
        </li>
    </ul>
    <div class="pagination">
        <a href="?p=1">1</a>
        <a href="?p=2">2</a>
        <a href="?p=5">5</a>
    </div>
</div>
"""

SAMPLE_MTS_DETAIL_HTML = """
<div id="content">
    <div id="descriptionbox">
        <p>This mod overhauls all cooking recipes in The Sims 4.</p>
        <p><strong>Requirements:</strong></p>
        <ul>
            <li>Scumbumbo XML Injector</li>
            <li>Custom Food Interactions</li>
            <li>Base Game compatible - Game Options -> Script Mods Enabled</li>
        </ul>
        <p><strong>Features:</strong></p>
        <p>Over 100 recipes added.</p>
    </div>
    <div id="downloadbox">
        <a href="getfile.php?file=2045512">SrslySims_Cooking_Overhaul.zip</a>
        <a href="getfile.php?file=2045513">SrslySims_Recipe_Pack.zip</a>
    </div>
</div>
"""


def test_modthesims_registered_and_categories_configured():
    """Vérifie que ModTheSimsProvider est correctement enregistré dans ProviderRegistry."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("modthesims")
    assert prov is not None
    assert isinstance(prov, ModTheSimsProvider)
    assert prov.provider_name == "modthesims"
    assert prov.base_url == "https://modthesims.info"
    assert len(prov.CATEGORIES) == 11

    cat_ids = [c["id"] for c in prov.CATEGORIES]
    assert "mts_game_mods" in cat_ids
    assert "mts_traits" in cat_ids
    assert "mts_careers" in cat_ids
    assert "mts_build_mode" in cat_ids
    assert "mts_buy_mode" in cat_ids
    assert "mts_body_shop" in cat_ids
    assert "mts_lots_housing" in cat_ids
    assert "mts_sims" in cat_ids
    assert "mts_pets" in cat_ids
    assert "mts_programs_utilities" in cat_ids
    assert "mts_miscellaneous" in cat_ids


def test_extract_item_id_formats():
    """Vérifie l'extraction d'identifiant numérique depuis différents formats d'URL MTS."""
    assert extract_item_id("701054") == "701054"
    assert extract_item_id("/d/701054/realistic-cooking.html") == "701054"
    assert extract_item_id("https://modthesims.info/download.php?t=701054") == "701054"
    assert extract_item_id("https://modthesims.info/showthread.php?t=701054&chat=1") == "701054"
    assert extract_item_id("") is None


def test_parse_mts_browse_html():
    """Vérifie le parsing d'une page HTML de catégorie MTS et l'extraction des cartes."""
    category = {"id": "mts_game_mods", "name": "Game Mods", "slug": "game-mods"}
    mods, detected_pages = parse_mts_browse_html(SAMPLE_MTS_BROWSE_HTML, category)

    assert len(mods) == 2
    assert detected_pages == 5

    mod1 = mods[0]
    assert mod1["remote_id"] == "701054"
    assert mod1["title"] == "Realistic Cooking Mod"
    assert mod1["author"] == "SrslySims"
    assert mod1["source"] == "modthesims"
    assert mod1["category"] == "Game Mods"
    assert mod1["thumbnail_url"] == "https://thumbs.modthesims.info/thumb/701054.jpg"
    assert "overhaul of cooking" in mod1["short_description"]

    mod2 = mods[1]
    assert mod2["remote_id"] == "685412"
    assert mod2["title"] == "XML Injector v4"
    assert mod2["author"] == "Scumbumbo"


def test_extract_mts_download_links():
    """Vérifie l'extraction des liens de téléchargement directs depuis le HTML d'un mod."""
    soup = BeautifulSoup(SAMPLE_MTS_DETAIL_HTML, "html.parser")
    links = extract_mts_download_links(soup, "https://modthesims.info/d/701054")

    assert len(links) == 2
    assert links[0]["name"] == "SrslySims_Cooking_Overhaul.zip"
    assert "file=2045512" in links[0]["url"]
    assert links[1]["name"] == "SrslySims_Recipe_Pack.zip"
    assert "file=2045513" in links[1]["url"]


def test_extract_mts_requirements():
    """Vérifie l'extraction des prérequis depuis la description d'un mod MTS."""
    soup = BeautifulSoup(SAMPLE_MTS_DETAIL_HTML, "html.parser")
    item_id, raw_html, reqs = extract_mts_requirements(
        soup, page_text=soup.get_text(), own_id="701054"
    )

    assert len(reqs) >= 2
    titles = [r["title"] for r in reqs]
    assert any("XML Injector" in t for t in titles)
    assert any("Custom Food Interactions" in t for t in titles)


def test_modthesims_category_mapping():
    """Vérifie la correspondance des catégories ModTheSims vers la taxonomie unifiée."""
    assert CategoryMappingService.get_unified_category("modthesims", "mts_game_mods") == "gameplay"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_traits") == "traits_careers"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_careers") == "traits_careers"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_build_mode") == "build_buy"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_buy_mode") == "build_buy"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_body_shop") == "clothing"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_lots_housing") == "lots_housing"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_sims") == "sims_households"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_pets") == "sims_households"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_programs_utilities") == "tools_utilities"
    assert CategoryMappingService.get_unified_category("modthesims", "mts_miscellaneous") == "miscellaneous"


def test_modthesims_verify_session_success():
    """Vérifie la validation de session ModTheSims via SessionManager."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.object(SessionManager, "get_http_session") as mock_session_getter:
        mock_sess = MagicMock()
        mock_sess.get.return_value = mock_resp
        mock_session_getter.return_value = mock_sess

        ok, msg = SessionManager.verify_session("modthesims")
        assert ok is True
        assert "ModTheSims" in msg
