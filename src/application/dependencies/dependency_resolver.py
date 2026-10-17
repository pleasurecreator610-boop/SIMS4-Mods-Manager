"""
Dependency Resolver: Facade routing requests to DependencyOrchestrator.
Maintains backward compatibility with all callers and tests.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from src.api.schemas.catalog import DependencyItem
from src.application.dependencies.dependency_actions import DependencyActions
from src.application.dependencies.dependency_coordinator import DependencyCoordinator
from src.application.dependencies.dependency_normalizer import (
    clean_dependency_title,
    detect_game_dlc_or_base_game,
)
from src.application.dependencies.dependency_orchestrator import DependencyOrchestrator
from src.application.dependencies.dependency_special_cases import (
    SPECIAL_DEPENDENCY_CASES,
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
)

__all__ = [
    "SPECIAL_DEPENDENCY_CASES",
    "SPECIAL_DEPENDENCY_REMOTE_IDS",
    "find_special_dependency_case",
    "resolve_mod_dependencies",
    "find_dependent_installed_mods",
    "clean_dependency_title",
    "detect_game_dlc_or_base_game",
    "DependencyOrchestrator",
    "DependencyCoordinator",
    "DependencyActions",
]


def resolve_mod_dependencies(
    raw_deps: List[Any],
    session,
    installed_by_remote: Dict[Tuple[str, str], Any],
    installed_by_title: Dict[str, Any],
    is_syncing: Optional[bool] = None,
    catalog_remote_ids: Optional[Set[str]] = None,
    requirements_overrides: Optional[Dict[str, str]] = None,
    deduplicate: bool = True,
) -> List[DependencyItem]:
    """Resolves dependency items against database catalog, installed mods, and official game DLCs."""
    orchestrator = DependencyOrchestrator()
    return orchestrator.resolve(
        raw_deps=raw_deps,
        session=session,
        installed_by_remote=installed_by_remote,
        installed_by_title=installed_by_title,
        is_syncing=is_syncing,
        catalog_remote_ids=catalog_remote_ids,
        requirements_overrides=requirements_overrides,
        deduplicate=deduplicate,
    )


def find_dependent_installed_mods(installed_mod_id: int, session) -> List[Dict[str, Any]]:
    """Identifies all installed mods that depend on target mod."""
    orchestrator = DependencyOrchestrator()
    return orchestrator.find_dependent_installed_mods(installed_mod_id, session)
