"""
Level 1: Orchestrator for Catalog Synchronization.
Declares and directs the high-level synchronization workflow,
analogous to a master orchestrator (main.tf), orchestrating coordinators and actions.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Optional, Union

from src.api.schemas.catalog import DependenciesCheckResponse
from src.application.catalog.catalog_sync_actions import CatalogSyncActions
from src.application.catalog.catalog_sync_coordinator import CatalogSyncCoordinator
from src.application.catalog.sync_tracker import SyncTracker
from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.core.shutdown_manager import ShutdownManager
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod, InstalledMod
from src.domain.models.mod_entity import CatalogModEntity
from src.providers import ProviderRegistry
from src.utils.logger import logger


class CatalogSyncOrchestrator:
    """High-level orchestrator for catalog scraping, sync, and dependency checking."""

    def __init__(
        self,
        coordinator: Optional[CatalogSyncCoordinator] = None,
        actions: Optional[CatalogSyncActions] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.actions = actions or CatalogSyncActions(self.db)
        self.coordinator = coordinator or CatalogSyncCoordinator(self.actions, self.db)

    def orchestrate_sync(self, max_pages: int = -1, is_background: bool = False) -> None:
        """
        Orchestrates full catalog sync:
        1. Identifies providers and categories (respecting adult_content_enabled setting).
        2. Configures SyncTracker per provider.
        3. Executes provider category scraping concurrently across active providers.
        4. Closes sync lifecycle gracefully.
        """
        from src.core.config import AppConfig, ADULT_PROVIDERS

        adult_enabled = AppConfig.load().adult_content_enabled
        providers = ProviderRegistry.list_providers()
        all_sync_providers = [p for p in providers if getattr(p, "CATEGORIES", None)]
        if not adult_enabled:
            filtered_providers = [
                p for p in all_sync_providers if getattr(p, "provider_name", "").lower() not in ADULT_PROVIDERS
            ]
            # Fallback to all_sync_providers only if a test registered solely a single mock provider
            sync_providers = filtered_providers if filtered_providers else all_sync_providers
        else:
            sync_providers = all_sync_providers

        if not sync_providers:
            SyncTracker.finish(0)
            return

        try:
            total_new = 0
            total_lock = threading.Lock()
            # Concurrence dynamique : 2 workers en tâche de fond (silencieux), jusqu'à 6 en manuel
            max_prov_workers = 2 if is_background else min(6, len(sync_providers))
            workers_per_provider = 2 if is_background else max(2, 6 // max(1, len(sync_providers)))

            def _sync_single_provider(prov: Any) -> int:
                nonlocal total_new
                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    return 0
                p_name = getattr(prov, "provider_name", "loverslab").lower()
                categories = getattr(prov, "CATEGORIES", [])
                if not categories:
                    return 0
                SyncTracker.set_provider_status(p_name, "RUNNING")
                prov_new = self.coordinator.sync_all_categories(
                    categories=categories,
                    provider=prov,
                    max_pages=max_pages,
                    tracker=SyncTracker,
                    max_workers=workers_per_provider,
                )
                with total_lock:
                    total_new += prov_new
                if not SyncTracker.stop_requested and not ShutdownManager.is_shutting_down():
                    SyncTracker.set_provider_status(p_name, "OK")
                return prov_new

            if len(sync_providers) == 1:
                _sync_single_provider(sync_providers[0])
            else:
                with ThreadPoolExecutor(max_workers=max_prov_workers) as prov_pool:
                    list(prov_pool.map(_sync_single_provider, sync_providers))

            if not SyncTracker.stop_requested and not ShutdownManager.is_shutting_down():
                SyncTracker.finish(total_new)
        except Exception as e:
            if not ShutdownManager.is_shutting_down() and "interpreter shutdown" not in str(e).lower():
                logger.error(f"Erreur globale de synchronisation: {e}", exc_info=True)
                SyncTracker.set_error(f"Erreur de synchronisation: {e}")
        finally:
            if SyncTracker.is_running:
                SyncTracker.stop()

    def check_dependencies(
        self,
        mod_title: str,
        page_url: Optional[str] = None,
        source: str = "loverslab",
        cat_mod: Optional[Union[CatalogMod, CatalogModEntity]] = None,
    ) -> DependenciesCheckResponse:
        """
        Orchestrates checking dependencies for a given catalog mod.
        """
        with self.db.get_session() as session:
            if not cat_mod and page_url:
                cat_mod = session.query(CatalogMod).filter_by(page_url=page_url).first()
            elif cat_mod and isinstance(cat_mod, CatalogMod) and cat_mod.id:
                # Merge into current session
                cat_mod = session.query(CatalogMod).filter_by(id=cat_mod.id).first() or cat_mod

            req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []
            req_status = cat_mod.requirements_status if cat_mod else "NONE"

            # If mod has not been scraped for requirements yet, do so now
            if cat_mod and (not cat_mod.requirements_status or cat_mod.requirements_status == "NONE") and page_url:
                try:
                    provider = ProviderRegistry.get_provider(source)
                    if provider:
                        logger.info(f"Vérification temps réel des dépendances pour {mod_title} ({page_url})...")
                        det = provider.get_mod_details(page_url)
                        det_dict: dict[str, Any] = (
                            det.model_dump() if hasattr(det, "model_dump") else (det if isinstance(det, dict) else {})
                        )
                        if isinstance(cat_mod, CatalogMod):
                            if det_dict.get("requirements_text") is not None or det_dict.get("requirements_status"):
                                cat_mod.requirements_text = det_dict.get("requirements_text")
                                cat_mod.requirements_status = det_dict.get("requirements_status", "NONE")
                                cat_mod.set_requirements_mods_list(det_dict.get("requirements_mods", []))
                            if det_dict.get("download_urls"):
                                cat_mod.set_download_urls_list(det_dict.get("download_urls", []))
                            if det_dict.get("external_links"):
                                cat_mod.set_external_links_list(det_dict.get("external_links", []))
                            session.commit()
                except Exception as e:
                    logger.debug(f"Erreur vérification requirements pour {mod_title}: {e}")

            req_status = cat_mod.requirements_status if cat_mod else "NONE"
            req_text = cat_mod.requirements_text if cat_mod else None
            req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []

            # Check installed dependencies & resolve statuses
            all_inst = session.query(InstalledMod).all()
            installed_by_remote = {(im.source or "unknown", im.remote_id): im for im in all_inst if im.remote_id}
            installed_by_title = {im.title.lower(): im for im in all_inst if im.title}

            overrides = cat_mod.get_requirements_overrides() if cat_mod else {}
            dep_items = resolve_mod_dependencies(
                req_mods,
                session,
                installed_by_remote,
                installed_by_title,
                is_syncing=SyncTracker.is_running,
                requirements_overrides=overrides,
            )

            game_dlcs = [d for d in dep_items if d.is_game_dlc or d.status == "GAME_DLC"]
            comment_deps = [d for d in dep_items if d.is_comment or d.status == "COMMENT_NOISE"]
            mod_deps = [
                d
                for d in dep_items
                if not (d.is_game_dlc or d.status == "GAME_DLC" or d.is_comment or d.status == "COMMENT_NOISE")
            ]

            already_installed = [d for d in mod_deps if d.is_installed or d.status == "INSTALLED"]
            missing = [d for d in mod_deps if not d.is_installed and d.status != "INSTALLED"]

            not_detected_finished = [d for d in missing if d.status == "NOT_DETECTED_FINISHED"]
            not_detected_scanning = [d for d in missing if d.status == "NOT_DETECTED_SCANNING"]
            unresolved_text_deps = [
                d
                for d in missing
                if not d.remote_id and d not in not_detected_finished and d not in not_detected_scanning
            ]

            unfound = list(not_detected_finished) + list(unresolved_text_deps)
            found_missing = [d for d in missing if d not in unfound and d.status != "NOT_DETECTED_SCANNING"]
            is_partial = bool(unfound or (req_status == "PENDING_VERIFICATION" and not mod_deps and not game_dlcs))

            if is_partial:
                unfound_names = [d.title for d in unfound]
                if not unfound_names and req_text:
                    unfound_names = [req_text]
                names_str = ", ".join(f"'{n}'" for n in unfound_names) if unfound_names else "non identifiées"
                warning_msg = (
                    f"Ce mod nécessite des dépendances non trouvées sur LoversLab ({names_str}). "
                    "L'installation partielle est autorisée, mais le mod risque de ne pas fonctionner correctement sans ces composants."
                )
                return DependenciesCheckResponse(
                    mod_title=mod_title,
                    requirements_status="PARTIAL" if found_missing else "PENDING_VERIFICATION",
                    requirements_text=req_text,
                    can_install=True,
                    is_partial=True,
                    unfound_dependencies=unfound,
                    blocking_reason=warning_msg,
                    already_installed_dependencies=already_installed,
                    missing_dependencies=found_missing,
                    game_dlc_dependencies=game_dlcs,
                    comment_dependencies=comment_deps,
                )

            if not_detected_scanning:
                names = ", ".join(f"'{d.title}'" for d in not_detected_scanning)
                return DependenciesCheckResponse(
                    mod_title=mod_title,
                    requirements_status="WAITING_SCAN",
                    requirements_text=req_text,
                    can_install=True,
                    is_partial=True,
                    unfound_dependencies=not_detected_scanning,
                    blocking_reason=f"La synchronisation du catalogue est en cours pour : {names}.",
                    already_installed_dependencies=already_installed,
                    missing_dependencies=found_missing,
                    game_dlc_dependencies=game_dlcs,
                    comment_dependencies=comment_deps,
                )

            final_status = "RESOLVED" if (req_mods or game_dlcs) else (req_status or "NONE")
            return DependenciesCheckResponse(
                mod_title=mod_title,
                requirements_status=final_status,
                requirements_text=req_text,
                can_install=True,
                is_partial=False,
                unfound_dependencies=[],
                blocking_reason=None,
                already_installed_dependencies=already_installed,
                missing_dependencies=missing,
                game_dlc_dependencies=game_dlcs,
                comment_dependencies=comment_deps,
            )
