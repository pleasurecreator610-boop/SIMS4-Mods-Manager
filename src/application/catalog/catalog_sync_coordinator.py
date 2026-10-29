"""
Level 2: Flow Coordinator for Catalog Synchronization.
Handles iteration loops, pagination, retry/backoff policies,
threading concurrency, and progress tracking updates.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from src.application.catalog.catalog_sync_actions import CatalogSyncActions
from src.application.catalog.sync_tracker import SyncTracker
from src.core.shutdown_manager import ShutdownManager
from src.infrastructure.database.manager import DatabaseManager
from src.utils.logger import logger


class CatalogSyncCoordinator:
    """Coordinates looping, retries, and concurrency for catalog scraping."""

    def __init__(
        self,
        actions: Optional[CatalogSyncActions] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.actions = actions or CatalogSyncActions(db_manager)
        self.db = db_manager or DatabaseManager.get_instance()
        self._db_lock = threading.Lock()

    def sync_category(
        self,
        category: Dict[str, Any],
        provider: Any,
        max_pages: int,
        tracker: type[SyncTracker],
    ) -> Tuple[int, int]:
        """
        Coordinates the pagination loop for a single category, applying backoff
        and calling atomic actions. Returns (cat_mods_count, cat_new_mods).
        """
        cat_id = category["id"]
        cat_name = category["name"]
        default_p = category.get("default_pages", 1)
        baseline_p = default_p if max_pages <= 0 else min(max_pages, default_p)
        target_cat_pages = baseline_p

        tracker.update_category(cat_id, 0, target_cat_pages, 0, "IN_PROGRESS")
        cat_mods_count = 0
        cat_new_mods = 0

        p = 1
        while p <= target_cat_pages:
            tracker.wait_if_paused()
            if tracker.stop_requested or ShutdownManager.is_shutting_down():
                break

            max_retries = 3
            base_delay = 2.0
            mods: List[Dict[str, Any]] = []
            scrape_success = False

            # Retry loop with exponential backoff
            for attempt in range(max_retries):
                tracker.wait_if_paused()
                if tracker.stop_requested or ShutdownManager.is_shutting_down():
                    break
                try:
                    mods, detected_pages = self.actions.scrape_category_page(provider, category, page_num=p)
                    scrape_success = True
                    if p == 1 and detected_pages and detected_pages > 0:
                        if max_pages <= 0:
                            target_cat_pages = detected_pages
                        else:
                            target_cat_pages = min(max_pages, detected_pages)
                        with tracker._lock:
                            diff = target_cat_pages - baseline_p
                            tracker.total_pages = max(1, tracker.total_pages + diff)
                        tracker.update_category(cat_id, 0, target_cat_pages, cat_mods_count, "IN_PROGRESS")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Échec worker LoversLab [{cat_name}] page {p} "
                            f"(tentative {attempt + 1}/{max_retries}). Réessai dans {delay:.1f}s... Erreur: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"Erreur définitive worker LoversLab [{cat_name}] page {p}: {e}", exc_info=True)

            tracker.wait_if_paused()
            if tracker.stop_requested or ShutdownManager.is_shutting_down():
                break

            if not scrape_success and not mods:
                p += 1
                continue

            cat_mods_count += len(mods)
            new_on_page = 0
            try:
                with self._db_lock:
                    with self.db.get_session() as session:
                        new_on_page, _ = self.actions.upsert_mods_batch(
                            session=session, mods_data=mods, default_category=cat_name
                        )

                cat_new_mods += new_on_page
                tracker.record_page(new_on_page, is_first_page=(p == 1))
                tracker.update_category(cat_id, p, target_cat_pages, cat_mods_count, "IN_PROGRESS")
                tracker.update_progress(
                    tracker.progress_percent,
                    f"Scraping en cours ({tracker.pages_completed}/{tracker.total_pages} pages)",
                    current_category=f"{cat_name} (p. {p}/{target_cat_pages})",
                )
            except Exception as e:
                logger.error(f"Erreur enregistrement BDD [{cat_name}] page {p}: {e}", exc_info=True)

            p += 1
            tracker.wait_if_paused()
            if tracker.stop_requested or ShutdownManager.is_shutting_down():
                break
            time.sleep(0.3)

        if tracker.stop_requested or ShutdownManager.is_shutting_down():
            tracker.update_category(cat_id, min(p, target_cat_pages), target_cat_pages, cat_mods_count, "STOPPED")
        else:
            tracker.update_category(cat_id, target_cat_pages, target_cat_pages, cat_mods_count, "COMPLETED")

        return cat_mods_count, cat_new_mods

    def sync_all_categories(
        self,
        categories: List[Dict[str, Any]],
        provider: Any,
        max_pages: int,
        tracker: type[SyncTracker],
        max_workers: int = 8,
    ) -> int:
        """
        Coordinates worker thread execution across all categories. Returns total_new.
        """
        num_workers = min(len(categories), max_workers)
        logger.info(
            f"Démarrage du scraping parallèle sur {len(categories)} sous-catégories avec {num_workers} workers."
        )

        total_new = 0
        lock = threading.Lock()

        def _worker(cat: Dict[str, Any]) -> None:
            nonlocal total_new
            _, new_count = self.sync_category(cat, provider, max_pages, tracker)
            with lock:
                total_new += new_count

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            try:
                list(executor.map(_worker, categories))
            except (RuntimeError, KeyboardInterrupt) as e:
                if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                    logger.info("Arrêt de la synchronisation suite à la fermeture.")
                    return total_new
                raise

        return total_new
