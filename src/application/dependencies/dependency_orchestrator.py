"""
Level 1: Orchestrator for Dependency Resolution.
Declares and orchestrates dependency resolution workflows across catalog,
installed mods, and official game DLCs.
"""

import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from src.api.schemas.catalog import DependencyItem
from src.application.dependencies.dependency_actions import DependencyActions
from src.application.dependencies.dependency_coordinator import DependencyCoordinator


class DependencyOrchestrator:
    """High-level orchestrator for dependency evaluation and categorization."""

    _resolution_cache: Dict[Tuple[str, bool, str], List[DependencyItem]] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        coordinator: Optional[DependencyCoordinator] = None,
        actions: Optional[DependencyActions] = None,
    ):
        self.actions = actions or DependencyActions()
        self.coordinator = coordinator or DependencyCoordinator(self.actions)

    def resolve(
        self,
        raw_deps: List[Any],
        session: Session,
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
        is_syncing: Optional[bool] = None,
        catalog_remote_ids: Optional[Set[Tuple[str, str]]] = None,
        requirements_overrides: Optional[Dict[str, str]] = None,
        deduplicate: bool = True,
    ) -> List[DependencyItem]:
        """
        Orchestrates full dependency resolution:
        1. Determines background sync liveness if not specified.
        2. Delegates to DependencyCoordinator for iteration, action execution, and deduplication.
        """
        if not raw_deps:
            return []

        if is_syncing is None:
            from src.application.catalog.sync_tracker import SyncTracker

            is_syncing = SyncTracker.is_running

        cache_key = (
            str(sorted([str(d) for d in raw_deps])),
            bool(is_syncing),
            str(sorted((requirements_overrides or {}).items())),
            bool(deduplicate),
            tuple(sorted(installed_by_remote.keys())),
            tuple(sorted(installed_by_title.keys())),
        )

        with self._cache_lock:
            if cache_key in self._resolution_cache:
                return list(self._resolution_cache[cache_key])

        res = self.coordinator.resolve_all_dependencies(
            raw_deps=raw_deps,
            session=session,
            installed_by_remote=installed_by_remote,
            installed_by_title=installed_by_title,
            is_syncing=bool(is_syncing),
            catalog_remote_ids=catalog_remote_ids,
            requirements_overrides=requirements_overrides,
            deduplicate=deduplicate,
        )

        with self._cache_lock:
            if len(self._resolution_cache) > 500:
                self._resolution_cache.clear()
            self._resolution_cache[cache_key] = res

        return res

    def find_dependent_installed_mods(self, installed_mod_id: int, session: Session) -> List[Dict[str, Any]]:
        """Orchestrates lookup of installed mods that depend on target mod."""
        return self.coordinator.find_dependent_installed_mods(installed_mod_id, session)
