from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.infrastructure.database import DatabaseManager


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_accounts_endpoints(client):
    # List
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data
    assert len(data["accounts"]) >= 2
    providers = [a["provider_name"] for a in data["accounts"]]
    assert "loverslab" in providers
    assert "patreon" in providers

    # Clear (mocked to protect user session during tests)
    with patch("src.core.session_manager.SessionManager.clear_session", return_value=True):
        resp = client.delete("/api/accounts/loverslab")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_accounts_dynamic_providers(client):
    from src.providers.base import BaseSourceProvider
    from src.providers.registry import ProviderRegistry

    class DummyCustomProvider(BaseSourceProvider):
        provider_name = "customplugin"
        base_url = "https://custom.example.com"
        login_url = "https://custom.example.com/login"

        def scrape_catalog(self, page: int = 1, limit: int = 25):
            return []

        def get_mod_details(self, mod_url: str):
            return {}

        def download_mod_file(self, download_url: str, dest_path, progress_callback=None):
            return True, "Downloaded"

        def check_access(self, mod_data):
            return "PUBLIC"

        def check_user_already_commented(self, page_url: str, required_keywords):
            return False, None

        def post_mod_comment(self, page_url: str, message: str):
            return True, "Success"

    p = DummyCustomProvider()
    ProviderRegistry.register(p, name="customplugin")

    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    providers = [a["provider_name"] for a in resp.json()["accounts"]]
    assert "customplugin" in providers
