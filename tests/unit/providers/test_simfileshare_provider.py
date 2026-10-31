"""Tests unitaires pour le plugin SimFileShareProvider (plugins/simfileshare/)."""

from pathlib import Path
from unittest.mock import patch

from plugins.simfileshare import SimFileShareProvider
from src.providers.registry import ProviderRegistry


def test_simfileshare_provider_registered():
    """Vérifie que SimFileShareProvider est enregistré dans ProviderRegistry."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("simfileshare")
    assert prov is not None
    assert isinstance(prov, SimFileShareProvider)
    assert prov.provider_name == "simfileshare"
    assert prov.base_url == "https://simfileshare.net"


def test_simfileshare_capabilities_per_faq():
    """Vérifie les capacités conformes à la FAQ officielle de SimFileShare."""
    prov = SimFileShareProvider()
    # 1. Pas de catalogue public explorable
    assert prov.scrape_catalog() == []
    # 2. Accès public sans compte
    assert prov.check_access({}) == "PUBLIC"
    # 3. Pas d'espace commentaires ni d'interpellation
    can_comment, _ = prov.check_user_already_commented("https://simfileshare.net/download/123/", [])
    assert not can_comment
    ok_post, msg_post = prov.post_mod_comment("https://simfileshare.net/download/123/", "Test comment")
    assert not ok_post
    assert "ne disposant pas d'espace commentaires" in msg_post
    ok_del, _ = prov.delete_mod_comment("123")
    assert not ok_del


def test_simfileshare_get_mod_details():
    """Vérifie la résolution des détails d'un mod hébergé sur SFS."""
    prov = SimFileShareProvider()
    with patch.object(
        prov.resolver,
        "resolve_direct_download",
        return_value=("https://simfileshare.net/download/999/?dl", "AwesomeHair.package", 2048),
    ):
        details = prov.get_mod_details("https://simfileshare.net/download/999/")
        assert details["title"] == "AwesomeHair.package"
        assert len(details["download_urls"]) == 1
        assert details["download_urls"][0]["url"] == "https://simfileshare.net/download/999/?dl"
        assert details["download_urls"][0]["name"] == "AwesomeHair.package"
        assert details["author"] == "SimFileShare Creator"


def test_simfileshare_download_mod_file(tmp_path: Path):
    """Vérifie le téléchargement de fichier via le provider."""
    prov = SimFileShareProvider()
    target = tmp_path / "test.package"
    with patch.object(prov.resolver, "download_mod_file", return_value=(True, str(target))):
        ok, res = prov.download_mod_file("https://simfileshare.net/download/999/", target)
        assert ok
        assert res == str(target)
