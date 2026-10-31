"""Tests unitaires complets pour le plugin NexusModsProvider (plugins/nexusmods/)."""

from unittest.mock import MagicMock, patch

from plugins.nexusmods import NexusModsProvider
from plugins.nexusmods.parsers import (
    extract_nexusmods_requirements,
    parse_nexusmods_graphql_mods,
)
from plugins.nexusmods.downloader import download_nexusmods_file
from src.domain.models.category_mapping import CategoryMappingService
from src.providers.registry import ProviderRegistry


SAMPLE_GRAPHQL_MODS = [
    {
        "modId": 223,
        "name": "WickedWhims",
        "summary": "Complete overhaul adding complex relationships and adult mechanics.",
        "author": "TURBODRIVER",
        "downloads": 2750000,
        "endorsements": 54000,
        "pictureUrl": "https://staticdelivery.nexusmods.com/mods/641/images/223.jpg",
        "version": "v180",
        "category": "Gameplay",
        "modRequirements": {"nexusRequirements": {"nodes": []}},
    },
    {
        "modId": 923,
        "name": "The Sims 4 Lupobianco Animations for WickedWhims",
        "summary": "Custom animation pack designed for WickedWhims.",
        "author": "Lupobianco",
        "downloads": 520000,
        "endorsements": 14000,
        "pictureUrl": "https://staticdelivery.nexusmods.com/mods/641/images/923.jpg",
        "version": "2.4",
        "category": "Gameplay",
        "modRequirements": {
            "nexusRequirements": {
                "nodes": [
                    {
                        "modName": "WickedWhims",
                        "notes": "Without it my animations are useless.",
                        "url": "https://www.nexusmods.com/thesims4/mods/223",
                    }
                ]
            }
        },
    },
]


def test_nexusmods_registered_and_categories_configured():
    """Vérifie que NexusModsProvider est correctement enregistré dans ProviderRegistry."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("nexusmods")
    assert prov is not None
    assert isinstance(prov, NexusModsProvider)
    assert prov.provider_name == "nexusmods"
    assert prov.base_url == "https://www.nexusmods.com"
    assert len(prov.CATEGORIES) == 10
    cat_ids = [c["id"] for c in prov.CATEGORIES]
    assert "nexus_gameplay" in cat_ids
    assert "nexus_utilities" in cat_ids
    assert "nexus_user_interface" in cat_ids
    assert "nexus_clothing" in cat_ids


def test_parse_nexusmods_graphql_mods():
    """Vérifie la normalisation des nœuds GraphQL en modèles universels de mods."""
    cat = {"id": "nexus_gameplay", "slug": "gameplay"}
    mods = parse_nexusmods_graphql_mods(SAMPLE_GRAPHQL_MODS, cat)
    assert len(mods) == 2

    assert mods[0]["remote_id"] == "nexusmods_223"
    assert mods[0]["title"] == "WickedWhims"
    assert mods[0]["author"] == "TURBODRIVER"
    assert mods[0]["category"] == "gameplay"
    assert mods[0]["source"] == "nexusmods"
    assert mods[0]["requirements"] == []

    assert mods[1]["remote_id"] == "nexusmods_923"
    assert mods[1]["title"] == "The Sims 4 Lupobianco Animations for WickedWhims"
    assert len(mods[1]["requirements"]) == 2


def test_extract_nexusmods_requirements_distinction_mod_vs_comment():
    """
    Vérifie la distinction formelle et stricte entre :
    - MOD : dépendance binaire essentielle requise (ex: WickedWhims).
    - COMMENT : consigne ou avertissement de l'auteur (ex: 'Without it my animations are useless').
    """
    node = SAMPLE_GRAPHQL_MODS[1]
    reqs = extract_nexusmods_requirements(node)
    assert len(reqs) == 2

    mod_dep = next((r for r in reqs if r["type"] == "MOD"), None)
    comment_dep = next((r for r in reqs if r["type"] == "COMMENT"), None)

    assert mod_dep is not None
    assert mod_dep["name"] == "WickedWhims"
    assert mod_dep["url"] == "https://www.nexusmods.com/thesims4/mods/223"
    assert mod_dep["resolved"] is False

    assert comment_dep is not None
    assert "Without it my animations are useless" in comment_dep["name"]
    assert comment_dep["resolved"] is False


def test_extract_nexusmods_textual_requirements_fallback():
    """Vérifie l'analyse de secours dans le texte descriptif quand aucun prérequis structuré n'existe."""
    mod_text = {
        "name": "Custom Gameplay Mod",
        "description": "<p>Requires: XML Injector v4 library</p><p>Important: Delete old version before updating</p>",
    }
    reqs = extract_nexusmods_requirements(mod_text)
    assert len(reqs) >= 2

    assert any(r["type"] == "MOD" and "Injector" in r["name"] for r in reqs)
    assert any(r["type"] == "COMMENT" and "Delete old version" in r["name"] for r in reqs)


def test_nexusmods_category_mapping():
    """Vérifie la cohérence du mappage de catégories universelles pour Nexus Mods."""
    assert CategoryMappingService.get_unified_category("nexusmods", "nexus_gameplay") == "gameplay"
    assert CategoryMappingService.get_unified_category("nexusmods", "nexus_utilities") == "tools_utilities"
    assert CategoryMappingService.get_unified_category("nexusmods", "nexus_clothing") == "clothing"
    assert CategoryMappingService.get_unified_category("nexusmods", "nexus_build_mode") == "build_buy"
    assert CategoryMappingService.get_unified_category("nexusmods", "nexus_unknown") == "miscellaneous"


def test_nexusmods_download_with_api_key(tmp_path):
    """Vérifie le flux de téléchargement avec résolution via clé API Nexus Mods v1."""
    dest = tmp_path / "mod_file.zip"

    with (
        patch("src.core.session_manager.SessionManager.get_saved_cookies") as mock_cookies,
        patch("httpx.get") as mock_httpx_get,
        patch("src.core.session_manager.SessionManager.get_http_session") as mock_session,
    ):
        mock_cookies.return_value = {"nexusmods_api_key": "test_api_key_12345"}

        # Réponse API Nexus Mods v1 pour download_link.json
        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = [{"URI": "https://files.nexusmods.com/thesims4/mod.zip"}]
        mock_httpx_get.return_value = mock_api_resp

        # Réponse stream de téléchargement
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.headers = {"content-length": "12"}
        mock_stream_resp.iter_content.return_value = [b"SIMS4_MOD_DATA"]
        mock_stream_resp.__enter__.return_value = mock_stream_resp

        mock_http = MagicMock()
        mock_http.get.return_value = mock_stream_resp
        mock_session.return_value = mock_http

        ok, msg = download_nexusmods_file(
            file_id=123,
            mod_id=456,
            target_path=dest,
        )

        assert ok is True
        assert dest.exists()
        assert dest.read_bytes() == b"SIMS4_MOD_DATA"
