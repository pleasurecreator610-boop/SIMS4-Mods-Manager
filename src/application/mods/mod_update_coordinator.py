"""
Level 2: Flow Coordinator for Mod Updates.
Coordinates loops over installed mods, evaluates update availability,
and filters candidates for upgrade.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from src.application.mods.mod_update_actions import ModUpdateActions
from src.database.models import CatalogMod, InstalledMod
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity


class ModUpdateCoordinator:
    """Coordinates looping and update scanning across installed mods."""

    def __init__(self, actions: Optional[ModUpdateActions] = None):
        self.actions = actions or ModUpdateActions()

    def scan_updates(
        self,
        installed_mods: List[Union[InstalledMod, InstalledModEntity]],
        catalog_map: Dict[Union[int, Tuple[str, str]], Union[CatalogMod, CatalogModEntity]],
    ) -> List[Dict[str, Any]]:
        """
        Coordinates iterating over installed mods, checks each against catalog_map,
        and returns list of update candidate descriptors.
        """
        updates_available: List[Dict[str, Any]] = []

        for mod in installed_mods:
            cat_mod = None
            c_id = getattr(mod, "catalog_mod_id", None)
            source = getattr(mod, "source", None)
            remote_id = getattr(mod, "remote_id", None)

            if c_id and c_id in catalog_map:
                cat_mod = catalog_map[c_id]
            elif source and remote_id and (source, remote_id) in catalog_map:
                cat_mod = catalog_map[(source, remote_id)]

            has_update = self.actions.compare_update_availability(mod, cat_mod)
            if has_update:
                updates_available.append(
                    {
                        "installed_mod": mod,
                        "catalog_mod": cat_mod,
                        "current_version": getattr(mod, "version_str", None) or getattr(mod, "version_date", None),
                        "latest_version": getattr(cat_mod, "version_str", None) or getattr(cat_mod, "updated_date", None),
                    }
                )

        return updates_available
