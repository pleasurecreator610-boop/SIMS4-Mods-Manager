"""Tests unitaires pour le registre et le système de découverte de plugins."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry


class MockCustomPlugin(BaseSourceProvider):
    provider_name = "mock_plugin"
    display_name = "Mock Plugin Provider"
    base_url = "https://mock.com"

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        return [{"title": "Mock Mod", "remote_id": "123"}]

    def get_mod_details(self, mod_url: str):
        return {}

    def download_mod_file(self, download_url: str, dest_path: Path, progress_callback=None) -> Tuple[bool, str]:
        return True, "Downloaded"

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        return True, "Posted"


def test_provider_registry_builtins():
    """Vérifie que les plugins natifs LoversLab et Patreon sont bien enregistrés."""
    ll = ProviderRegistry.get_provider("loverslab")
    patreon = ProviderRegistry.get_provider("patreon")

    assert ll is not None
    assert ll.provider_name == "loverslab"

    assert patreon is not None
    assert patreon.provider_name == "patreon"

    all_providers = ProviderRegistry.list_providers()
    names = [p.provider_name for p in all_providers]
    assert "loverslab" in names
    assert "patreon" in names


def test_provider_registry_decorator_registration():
    """Vérifie l'enregistrement dynamique d'un plugin via décorateur."""

    @ProviderRegistry.register_provider("custom_test")
    class DecoratedPlugin(MockCustomPlugin):
        provider_name = "custom_test"

    prov = ProviderRegistry.get_provider("custom_test")
    assert prov is not None
    assert prov.provider_name == "custom_test"
    assert prov.scrape_catalog()[0]["title"] == "Mock Mod"


def test_provider_registry_discover_plugins_from_directory(tmp_path: Path):
    """Vérifie la découverte automatique de fichiers .py dans un dossier plugins/."""
    plugin_file = tmp_path / "nexus_plugin.py"
    plugin_code = """
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry

@ProviderRegistry.register_provider("nexus_mods")
class NexusProvider(BaseSourceProvider):
    provider_name = "nexus_mods"
    display_name = "Nexus Mods"
    base_url = "https://www.nexusmods.com"

    def scrape_catalog(self, page=1, limit=25):
        return []

    def get_mod_details(self, mod_url):
        return {}

    def download_mod_file(self, download_url, dest_path, progress_callback=None):
        return True, "OK"

    def check_access(self, mod_data):
        return "PUBLIC"

    def check_user_already_commented(self, page_url, required_keywords):
        return False, None

    def post_mod_comment(self, page_url, message):
        return False, "Not supported"
"""
    plugin_file.write_text(plugin_code, encoding="utf-8")

    discovered = ProviderRegistry.discover_plugins(plugins_dir=tmp_path)
    assert "nexus_plugin" in discovered

    nexus = ProviderRegistry.get_provider("nexus_mods")
    assert nexus is not None
    assert nexus.provider_name == "nexus_mods"
