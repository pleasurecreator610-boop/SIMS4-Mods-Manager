"""Tests unitaires pour le conteneur d'injection de dépendances (AppContainer)."""

from src.core.container import AppContainer, get_container
from src.infrastructure.database import DatabaseManager


def test_app_container_singleton():
    """Vérifie que AppContainer fonctionne en singleton via get_instance et get_container."""
    c1 = AppContainer.get_instance()
    c2 = get_container()
    assert c1 is c2


def test_app_container_resolves_services():
    """Vérifie la résolution des dépendances de base."""
    container = get_container()

    assert container.database_manager is not None
    assert container.session_manager is not None
    assert container.provider_registry is not None
    assert container.conflict_detector is not None


def test_app_container_override_and_reset():
    """Vérifie le mécanisme de substitution de dépendance (mock) pour les tests."""
    container = get_container()

    class FakeDatabaseManager:
        is_fake = True

    fake_db = FakeDatabaseManager()
    container.override(DatabaseManager, fake_db)

    assert container.database_manager is fake_db
    assert container.database_manager.is_fake is True

    container.reset_overrides()
    assert container.database_manager is not fake_db
