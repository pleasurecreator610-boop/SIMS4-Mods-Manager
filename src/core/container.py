"""Conteneur d'injection de dépendances (DI) léger et découplé pour SIMS 4 Mods Manager.

Fournit la résolution centralisée des services, orchestrateurs, dépôts et clients,
tout en facilitant la substitution de mocks lors des tests unitaires et d'intégration.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class AppContainer:
    """Conteneur central d'injection de dépendances applicatif."""

    _instance: Optional[AppContainer] = None

    def __init__(self) -> None:
        self._overrides: Dict[Any, Any] = {}
        self._singletons: Dict[Any, Any] = {}

    @classmethod
    def get_instance(cls) -> AppContainer:
        """Retourne l'instance unique du conteneur (Singleton)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance du conteneur (utile pour nettoyer entre les tests)."""
        cls._instance = None

    def override(self, target: Any, override_instance: Any) -> None:
        """Substitue une dépendance par une implémentation mock pour les tests."""
        self._overrides[target] = override_instance

    def reset_overrides(self) -> None:
        """Supprime l'ensemble des surcharges appliquées."""
        self._overrides.clear()

    def resolve(self, target: Type[T]) -> T:
        """Résout une dépendance avec prise en compte des surcharges actives."""
        if target in self._overrides:
            return self._overrides[target]
        if target in self._singletons:
            return self._singletons[target]
        # Instanciation par défaut
        instance = target()
        return instance

    # Propriétés de commodité typées pour les composants clés
    @property
    def database_manager(self) -> Any:
        from src.database import DatabaseManager

        if DatabaseManager in self._overrides:
            return self._overrides[DatabaseManager]
        return DatabaseManager.get_instance()

    @property
    def session_manager(self) -> Any:
        from src.core.session_manager import SessionManager

        if SessionManager in self._overrides:
            return self._overrides[SessionManager]
        return SessionManager

    @property
    def provider_registry(self) -> Any:
        from src.providers.registry import ProviderRegistry

        if ProviderRegistry in self._overrides:
            return self._overrides[ProviderRegistry]
        return ProviderRegistry

    @property
    def conflict_detector(self) -> Any:
        from src.application.mods.conflict_detector_service import ConflictDetectorService

        if ConflictDetectorService in self._overrides:
            return self._overrides[ConflictDetectorService]
        if ConflictDetectorService not in self._singletons:
            self._singletons[ConflictDetectorService] = ConflictDetectorService()
        return self._singletons[ConflictDetectorService]

    @property
    def catalog_orchestrator(self) -> Any:
        from src.application.catalog.catalog_sync_orchestrator import CatalogSyncOrchestrator

        if CatalogSyncOrchestrator in self._overrides:
            return self._overrides[CatalogSyncOrchestrator]
        if CatalogSyncOrchestrator not in self._singletons:
            self._singletons[CatalogSyncOrchestrator] = CatalogSyncOrchestrator()
        return self._singletons[CatalogSyncOrchestrator]

    @property
    def mod_orchestrator(self) -> Any:
        from src.application.mods.mod_install_orchestrator import ModInstallOrchestrator

        if ModInstallOrchestrator in self._overrides:
            return self._overrides[ModInstallOrchestrator]
        if ModInstallOrchestrator not in self._singletons:
            self._singletons[ModInstallOrchestrator] = ModInstallOrchestrator()
        return self._singletons[ModInstallOrchestrator]

    @property
    def dependency_orchestrator(self) -> Any:
        from src.application.dependencies.dependency_orchestrator import DependencyOrchestrator

        if DependencyOrchestrator in self._overrides:
            return self._overrides[DependencyOrchestrator]
        if DependencyOrchestrator not in self._singletons:
            self._singletons[DependencyOrchestrator] = DependencyOrchestrator()
        return self._singletons[DependencyOrchestrator]

    @property
    def game_service(self) -> Any:
        from src.application.game.game_service import GameService

        if GameService in self._overrides:
            return self._overrides[GameService]
        if GameService not in self._singletons:
            self._singletons[GameService] = GameService()
        return self._singletons[GameService]


def get_container() -> AppContainer:
    """Accesseur fonctionnel au conteneur pour l'injection dans FastAPI via Depends()."""
    return AppContainer.get_instance()
