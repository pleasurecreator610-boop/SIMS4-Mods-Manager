"""
Catalog Sync Service: Facade routing requests to CatalogSyncOrchestrator.
Maintains backward compatibility with all callers and tests.
"""

from typing import Optional, Union

from src.api.schemas.catalog import DependenciesCheckResponse
from src.application.catalog.catalog_sync_actions import CatalogSyncActions
from src.application.catalog.catalog_sync_coordinator import CatalogSyncCoordinator
from src.application.catalog.catalog_sync_orchestrator import CatalogSyncOrchestrator
from src.application.catalog.sync_tracker import SyncTracker
from src.database.models import CatalogMod
from src.domain.models.mod_entity import CatalogModEntity

__all__ = [
    "CatalogSyncService",
    "CatalogSyncOrchestrator",
    "CatalogSyncCoordinator",
    "CatalogSyncActions",
    "SyncTracker",
    "run_catalog_sync",
    "check_catalog_dependencies",
]


class CatalogSyncService:
    """Service applicatif pour la synchronisation et la gestion des dépendances du catalogue."""

    @classmethod
    def run_sync(cls, max_pages: int = -1) -> None:
        """Lance la synchronisation du catalogue."""
        run_catalog_sync(max_pages)

    @classmethod
    def check_dependencies(
        cls,
        mod_title: str,
        page_url: Optional[str] = None,
        source: str = "loverslab",
        cat_mod: Optional[Union[CatalogMod, CatalogModEntity]] = None,
    ) -> DependenciesCheckResponse:
        """Vérifie les dépendances d'un mod."""
        return check_catalog_dependencies(mod_title, page_url, source, cat_mod)


def run_catalog_sync(max_pages: int = -1) -> None:
    """Entry point executing catalog sync via CatalogSyncOrchestrator."""
    orchestrator = CatalogSyncOrchestrator()
    orchestrator.orchestrate_sync(max_pages=max_pages)


def check_catalog_dependencies(
    mod_title: str,
    page_url: Optional[str] = None,
    source: str = "loverslab",
    cat_mod: Optional[Union[CatalogMod, CatalogModEntity]] = None,
) -> DependenciesCheckResponse:
    """Entry point checking dependencies via CatalogSyncOrchestrator."""
    orchestrator = CatalogSyncOrchestrator()
    return orchestrator.check_dependencies(
        mod_title=mod_title, page_url=page_url, source=source, cat_mod=cat_mod
    )
