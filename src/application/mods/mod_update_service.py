"""
Service de détection et résolution des mises à jour des mods.
Facade routing requests to ModUpdateOrchestrator and ModUpdateActions.
"""

from __future__ import annotations

from typing import Optional, Union

from src.application.mods.mod_update_actions import ModUpdateActions
from src.application.mods.mod_update_orchestrator import ModUpdateOrchestrator
from src.infrastructure.database.models import CatalogMod, InstalledMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity


class ModUpdateService:
    """Service gérant la détection de versions obsolètes et la résolution de catalogue."""

    def __init__(
        self,
        installed_repo: Optional[IInstalledModRepository] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
    ) -> None:
        self._orchestrator = ModUpdateOrchestrator(
            installed_repo=installed_repo,
            catalog_repo=catalog_repo,
        )

    def check_update_available(
        self,
        installed_mod: Union[InstalledMod, InstalledModEntity],
        catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
    ) -> bool:
        """Détermine si une version plus récente d'un mod est disponible dans le catalogue."""
        return self._orchestrator.check_update_available(installed_mod, catalog_mod)

    def resolve_catalog_entry(self, installed_mod: InstalledModEntity) -> Optional[CatalogModEntity]:
        """Résout l'entrée catalogue associée à un mod installé via l'API interne des Repositories."""
        return self._orchestrator.resolve_catalog_entry(installed_mod)


_default_update_service = ModUpdateService()


def check_has_update(
    installed_mod: Union[InstalledMod, InstalledModEntity],
    catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
) -> bool:
    """Fonction globale conservée pour compatibilité ascendante."""
    return _default_update_service.check_update_available(installed_mod, catalog_mod)


def resolve_catalog_mod(session, installed_mod: InstalledMod) -> Optional[CatalogMod]:
    """Résout le CatalogMod (compatibilité SQLAlchemy session existante)."""
    actions = ModUpdateActions()
    return actions.resolve_catalog_mod_session(session, installed_mod)
