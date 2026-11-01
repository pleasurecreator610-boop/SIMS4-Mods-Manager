"""Tests unitaires pour le registre ProviderSpec, l'indexation O(1) des frameworks et la résilience HTTP."""

from unittest.mock import MagicMock

from src.application.dependencies.dependency_actions import DependencyActions
from src.application.dependencies.dependency_special_cases import find_special_dependency_case
from src.core.config import ACCOUNT_SUPPORTED_PROVIDERS, ADULT_PROVIDERS, PUBLIC_NO_ACCOUNT_PROVIDERS
from src.core.provider_metadata import (
    PROVIDER_SPECS,
    build_initial_providers_status,
    build_providers_login_urls,
    build_source_mapping,
)
from src.providers.base import BaseSourceProvider


def test_provider_specs_single_source_of_truth():
    """Vérifie la cohérence entre PROVIDER_SPECS et les constantes de classification."""
    assert len(PROVIDER_SPECS) >= 24
    for p in ADULT_PROVIDERS:
        assert p in PROVIDER_SPECS
        assert PROVIDER_SPECS[p].is_adult is True

    for p in ACCOUNT_SUPPORTED_PROVIDERS:
        assert p in PROVIDER_SPECS
        assert PROVIDER_SPECS[p].account_supported is True

    for p in PUBLIC_NO_ACCOUNT_PROVIDERS:
        assert p in PROVIDER_SPECS
        assert PROVIDER_SPECS[p].account_supported is False

    # Aucun chevauchement entre avec-compte et sans-compte
    assert not (set(ACCOUNT_SUPPORTED_PROVIDERS) & set(PUBLIC_NO_ACCOUNT_PROVIDERS))

    # Mapping de filtre insensible à la casse
    mapping = build_source_mapping()
    assert mapping["deaderpool (mccc)"] == "deaderpool"
    assert mapping["wicked.cc (official ww)"] == "wickedcc"
    assert mapping["the sims resource"] == "thesimsresource"
    assert mapping["tsr"] == "thesimsresource"

    # Login URLs
    login_urls = build_providers_login_urls()
    assert login_urls["loverslab"] == "https://www.loverslab.com/login/"
    assert login_urls["sims4studio"] == "https://sims4studio.com/login"
    assert login_urls["f95zone"] == "https://f95zone.to/login/"
    assert "deaderpool" not in login_urls

    # SyncTracker initial status
    initial_status = build_initial_providers_status()
    assert initial_status["deaderpool"] == "OK"
    assert initial_status["wickedcc"] == "OK"
    assert "simfileshare" not in initial_status


def test_special_dependency_case_o1_index_and_lru_cache():
    """Vérifie la résolution O(1) et le cache LRU de find_special_dependency_case."""
    find_special_dependency_case.cache_clear()

    res1 = find_special_dependency_case("MC Command Center (v2026.2)")
    assert res1 is not None
    assert res1["source"] == "deaderpool"
    assert res1["remote_id"] == "deaderpool_mccc"

    res2 = find_special_dependency_case("XML Injector v4", url="https://www.loverslab.com/files/file/99901/")
    assert res2 is not None
    assert res2["source"] == "scumbumbo"
    assert res2["remote_id"] == "scumbumbo_xml_injector"

    # Deuxième appel servi depuis le cache LRU
    res1_cached = find_special_dependency_case("MC Command Center (v2026.2)")
    assert res1_cached is res1
    info = find_special_dependency_case.cache_info()
    assert info.hits >= 1


def test_build_installed_index_batch_lookup():
    """Vérifie le pré-calcul par lot des empreintes de mods installés."""
    mod_a = MagicMock()
    mod_a.title = "The XML Injector v4.2"
    mod_b = MagicMock()
    mod_b.title = "MC Command Center 2026.2.0"

    installed_by_remote = {("scumbumbo", "scumbumbo_xml_injector"): mod_a}
    installed_by_title = {"xml injector": mod_a, "mc command center": mod_b}

    actions = DependencyActions()
    precomputed = actions.build_installed_index(installed_by_remote, installed_by_title)
    installed_list, fp_set = precomputed

    # mod_a présent dans les deux dicts mais dédupliqué par identité
    assert len(installed_list) == 2
    assert len(fp_set) == 2

    assert (
        actions.check_installed(
            source="loverslab",
            remote_id="99999",
            title="XML Injector",
            installed_by_remote=installed_by_remote,
            installed_by_title=installed_by_title,
            precomputed_index=precomputed,
        )
        is True
    )


def test_base_provider_fetch_with_retry_on_429(monkeypatch):
    """Vérifie le retry automatique sur HTTP 429 avec en-tête Retry-After."""
    monkeypatch.setattr("time.sleep", lambda _s: None)

    resp_429 = MagicMock(status_code=429, headers={"Retry-After": "0.1"})
    resp_200 = MagicMock(status_code=200, text="<html>OK</html>", headers={})

    class DummySession:
        _is_mock = False

        def __init__(self):
            self.calls = 0

        def get(self, url, timeout=15.0, **kwargs):
            self.calls += 1
            return resp_429 if self.calls == 1 else resp_200

    sess = DummySession()
    result = BaseSourceProvider._fetch_with_retry(sess, "https://example.com/mods", timeout=5.0, max_retries=2)
    assert result.status_code == 200
    assert sess.calls == 2
