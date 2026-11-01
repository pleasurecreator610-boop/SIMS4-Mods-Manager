"""
Unit tests for the 14 new Sims 4 mod platforms:
- Official Frameworks: deaderpool, scumbumbo, lumpinou, wickedcc, basemental
- Active SFW Catalogs & Creator Portals: gamebanana, thesimscatalog, itchio, sims4studio, littlemssam, sixamcc
- Active Adult (+18) Portals: synthira, f95zone, smutbase
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from plugins.basemental import BasementalProvider
from plugins.deaderpool import DeaderpoolProvider
from plugins.f95zone import F95ZoneProvider
from plugins.gamebanana import GameBananaProvider
from plugins.itchio import ItchIoProvider
from plugins.littlemssam import LittleMsSamProvider
from plugins.lumpinou import LumpinouProvider
from plugins.scumbumbo import ScumbumboProvider
from plugins.sims4studio import Sims4StudioProvider
from plugins.sixamcc import SixamCcProvider
from plugins.smutbase import SmutBaseProvider
from plugins.synthira import SynthiraProvider
from plugins.thesimscatalog import TheSimsCatalogProvider
from plugins.wickedcc import WickedCcProvider
from src.core.config import (
    ACCOUNT_SUPPORTED_PROVIDERS,
    ADULT_PROVIDERS,
    PUBLIC_NO_ACCOUNT_PROVIDERS,
)
from src.providers.registry import ProviderRegistry

ALL_14_NEW_PROVIDERS = [
    ("deaderpool", DeaderpoolProvider, False),
    ("scumbumbo", ScumbumboProvider, False),
    ("lumpinou", LumpinouProvider, False),
    ("wickedcc", WickedCcProvider, True),
    ("basemental", BasementalProvider, True),
    ("gamebanana", GameBananaProvider, False),
    ("thesimscatalog", TheSimsCatalogProvider, False),
    ("itchio", ItchIoProvider, False),
    ("sims4studio", Sims4StudioProvider, False),
    ("littlemssam", LittleMsSamProvider, False),
    ("sixamcc", SixamCcProvider, False),
    ("synthira", SynthiraProvider, True),
    ("f95zone", F95ZoneProvider, True),
    ("smutbase", SmutBaseProvider, True),
]


def test_all_14_new_providers_discovered_by_registry():
    """Verifies that ProviderRegistry discovers and registers all 14 new plugins dynamically."""
    ProviderRegistry.discover_plugins()
    registered = {p.provider_name for p in ProviderRegistry.list_providers()}

    for provider_name, provider_cls, is_adult in ALL_14_NEW_PROVIDERS:
        assert provider_name in registered, f"Provider '{provider_name}' not discovered in ProviderRegistry"
        instance = ProviderRegistry.get_provider(provider_name)
        assert isinstance(instance, provider_cls)
        assert instance.provider_name == provider_name
        assert isinstance(instance.CATEGORIES, list)
        assert len(instance.CATEGORIES) >= 1
        if is_adult:
            assert provider_name in ADULT_PROVIDERS
        else:
            assert provider_name not in ADULT_PROVIDERS


def test_account_vs_public_no_account_classification():
    """Verifies that official portals and public creator portals are excluded from account requirements."""
    for pub_p in (
        "deaderpool",
        "scumbumbo",
        "lumpinou",
        "wickedcc",
        "basemental",
        "thesimscatalog",
        "littlemssam",
        "sixamcc",
        "smutbase",
    ):
        assert pub_p in PUBLIC_NO_ACCOUNT_PROVIDERS
        assert pub_p not in ACCOUNT_SUPPORTED_PROVIDERS

    for acc_p in ("sims4studio", "f95zone", "itchio", "gamebanana", "synthira"):
        assert acc_p in ACCOUNT_SUPPORTED_PROVIDERS
        assert acc_p not in PUBLIC_NO_ACCOUNT_PROVIDERS


@pytest.mark.parametrize("provider_name,provider_cls,_is_adult", ALL_14_NEW_PROVIDERS)
def test_provider_scrape_category_page_with_live_html_and_curated_fallback(
    monkeypatch, provider_name, provider_cls, _is_adult
):
    """Tests scrape_category_page for each of the 14 new providers with mocked HTML and fallback."""
    provider = provider_cls()
    category_dict = provider.CATEGORIES[0]

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    if provider_name == "gamebanana":
        mock_resp.json.return_value = {
            "_aRecords": [
                {
                    "_idRow": 501234,
                    "_sName": "Realistic Sims 4 Lighting Overhaul",
                    "_sProfileUrl": "https://gamebanana.com/mods/501234",
                    "_aSubmitter": {"_sName": "LightCreator"},
                }
            ]
        }
        mock_resp.text = ""
    else:
        mock_resp.text = f"""
        <html><body>
            <article class="post mod-card game_cell">
                <h2 class="entry-title"><a href="{provider.base_url}/mods/test-mod-101">Sims 4 Custom Pack Alpha</a></h2>
                <span class="author">StudioCreator</span>
                <p class="summary">Awesome gameplay and custom content pack for The Sims 4.</p>
                <img src="{provider.base_url}/img/thumb101.jpg" />
            </article>
        </body></html>
        """
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda *_a, **_k: mock_session)

    items, total_pages = provider.scrape_category_page(category_dict, page=1)
    assert isinstance(items, list)
    assert len(items) >= 1
    assert (total_pages or 1) >= 1
    first = items[0]
    assert first["source"] == provider_name
    assert first["title"]
    assert first["page_url"].startswith("http")


@pytest.mark.parametrize("provider_name,provider_cls,_is_adult", ALL_14_NEW_PROVIDERS)
def test_provider_get_mod_details_and_requirements_extraction(monkeypatch, provider_name, provider_cls, _is_adult):
    """Tests get_mod_details for each of the 14 new providers, including requirements & download links."""
    provider = provider_cls()

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = f"""
    <html>
    <head>
        <title>Super Mod Pack v2.4 | {provider.display_name}</title>
        <meta property="og:title" content="Super Mod Pack v2.4" />
        <meta property="og:image" content="{provider.base_url}/preview.png" />
    </head>
    <body>
        <h1>Super Mod Pack v2.4</h1>
        <span class="author">ModMaster</span>
        <div class="entry-content post-content">
            <p>Full gameplay expansion for Sims 4.</p>
            <h3>Requirements:</h3>
            <ul>
                <li><a href="https://scumbumbomods.com/xml-injector">XML Injector</a></li>
                <li><a href="https://deaderpool-mccc.com/">MC Command Center</a></li>
            </ul>
            <a class="download" href="https://cdn.example.com/files/SuperModPack_v2.4.zip">Download Now</a>
        </div>
    </body>
    </html>
    """
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda *_a, **_k: mock_session)

    details = provider.get_mod_details(f"{provider.base_url}/mod/super-mod-pack")
    assert details["source"] == provider_name
    assert "Super Mod Pack" in details["title"]
    assert details["requirements_status"] in ("RESOLVED", "FOUND")
    dep_titles = [d["title"] for d in details["requirements_mods"]]
    assert "XML Injector" in dep_titles
    assert "MC Command Center" in dep_titles
    assert len(details["download_urls"]) >= 1


@pytest.mark.parametrize("provider_name,provider_cls,_is_adult", ALL_14_NEW_PROVIDERS)
def test_provider_download_mod_file_binary_vs_html_rejection(
    monkeypatch, tmp_path: Path, provider_name, provider_cls, _is_adult
):
    """Verifies that download_mod_file accepts valid archives/packages and rejects HTML login walls."""
    provider = provider_cls()

    # 1. Valid ZIP binary payload
    mock_session_ok = MagicMock()
    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.headers = {
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="{provider_name}_mod.zip"',
        "Content-Length": "12",
    }
    resp_ok.iter_content.return_value = [b"PK\x03\x04testzip!"]
    mock_session_ok.get.return_value = resp_ok
    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda *_a, **_k: mock_session_ok)

    dest_file = tmp_path / provider_name / f"{provider_name}_mod.zip"
    ok_bin, path_or_msg = provider.download_mod_file("https://cdn.example.com/dl/file.zip", dest_file)
    assert ok_bin is True
    assert Path(path_or_msg).exists()
    assert Path(path_or_msg).suffix == ".zip"

    # 2. Invalid HTML response disguised as download (e.g. Cloudflare / Login wall)
    mock_session_html = MagicMock()
    resp_html = MagicMock()
    resp_html.status_code = 200
    resp_html.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp_html.iter_content.return_value = [b"<!DOCTYPE html><html><body>Login required</body></html>"]
    mock_session_html.get.return_value = resp_html
    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda *_a, **_k: mock_session_html)

    dest_file_html = tmp_path / f"{provider_name}_html" / "wall.zip"
    ok_html, err_msg = provider.download_mod_file("https://cdn.example.com/dl/wall.zip", dest_file_html)
    assert ok_html is False
    assert "html" in err_msg.lower()
