"""
Level 1: Orchestrator for Mod Updates.
Declares and orchestrates detection, resolution, and batch updating of installed mods.
"""

from typing import Optional, Union

from src.application.mods.mod_update_actions import ModUpdateActions
from src.application.mods.mod_update_coordinator import ModUpdateCoordinator
from src.database.models import CatalogMod, InstalledMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity


class ModUpdateOrchestrator:
    """High-level orchestrator for version comparison and update detection."""

    def __init__(
        self,
        coordinator: Optional[ModUpdateCoordinator] = None,
        actions: Optional[ModUpdateActions] = None,
        installed_repo: Optional[IInstalledModRepository] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
    ):
        self.actions = actions or ModUpdateActions(installed_repo, catalog_repo)
        self.coordinator = coordinator or ModUpdateCoordinator(self.actions)

    def check_update_available(
        self,
        installed_mod: Union[InstalledMod, InstalledModEntity],
        catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
    ) -> bool:
        """Checks if a newer version exists in catalog."""
        return self.actions.compare_update_availability(installed_mod, catalog_mod)

    def resolve_catalog_entry(
        self, installed_mod: InstalledModEntity
    ) -> Optional[CatalogModEntity]:
        """Resolves catalog entity via repository interfaces."""
        return self.actions.resolve_catalog_entry(installed_mod)

    def resolve_catalog_mod_session(
        self, session, installed_mod: InstalledMod
    ) -> Optional[CatalogMod]:
        """Resolves catalog mod using active SQLAlchemy session."""
        return self.actions.resolve_catalog_mod_session(session, installed_mod)
