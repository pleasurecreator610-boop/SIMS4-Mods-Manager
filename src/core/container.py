"""Conteneur d'inversion de contrôle (IoC / Dependency Injection) léger pour SIMS 4 Mods Manager.

Permet de résoudre et d'injecter les services applicatifs et d'infrastructure
sans couplage direct aux singletons globaux, facilitant le mocking et les tests unitaires.
"""

from typing import Any, Callable, Dict, Optional, TypeVar

from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.filesystem.archive_extractor import ArchiveExtractor
from src.infrastructure.network.download_pipeline import BaseFileDownloader

T = TypeVar("T")


class AppContainer:
    """Conteneur de services applicatif avec support d'instances et de factories remplaçables."""

    _instance: Optional["AppContainer"] = None

    def __init__(self) -> None:
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._register_defaults()

    @classmethod
    def get_instance(cls) -> "AppContainer":
        """Retourne l'instance unique du conteneur applicatif."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Réinitialise le conteneur applicatif (utile entre les suites de tests)."""
        cls._instance = None

    def _register_defaults(self) -> None:
        """Enregistre les services d'infrastructure par défaut."""
        self._factories["database_manager"] = lambda: DatabaseManager.get_instance()
        self._factories["archive_extractor"] = lambda: ArchiveExtractor()
        self._factories["file_downloader"] = lambda: BaseFileDownloader()

    def register_singleton(self, key: str, instance: Any) -> None:
        """Enregistre une instance singleton pour une clé donnée."""
        self._singletons[key] = instance

    def register_factory(self, key: str, factory: Callable[[], Any]) -> None:
        """Enregistre une factory créant une nouvelle instance à chaque appel."""
        self._factories[key] = factory

    def resolve(self, key: str) -> Any:
        """Résout un service par son identifiant textuel."""
        if key in self._singletons:
            return self._singletons[key]
        if key in self._factories:
            return self._factories[key]()
        raise KeyError(f"Service non enregistré dans AppContainer: '{key}'")

    def get_database_manager(self) -> DatabaseManager:
        """Résout le gestionnaire de base de données."""
        res = self.resolve("database_manager")
        assert isinstance(res, DatabaseManager)
        return res

    def get_archive_extractor(self) -> ArchiveExtractor:
        """Résout l'extracteur d'archives sécurisé."""
        res = self.resolve("archive_extractor")
        assert isinstance(res, ArchiveExtractor)
        return res

    def get_file_downloader(self) -> BaseFileDownloader:
        """Résout le gestionnaire de téléchargement streaming."""
        res = self.resolve("file_downloader")
        assert isinstance(res, BaseFileDownloader)
        return res


def get_container() -> AppContainer:
    """Raccourci pour obtenir le conteneur d'injection de dépendances applicatif."""
    return AppContainer.get_instance()
