"""
Level 3: Atomic Actions for Catalog Synchronization.
Contains single-responsibility, atomic functions and classes for scraping a page,
extracting details, and persisting records into the database.
"""

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod


class CatalogSyncActions:
    """Atomic actions executed during catalog synchronization."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def scrape_category_page(
        self, provider: Any, category: Dict[str, Any], page_num: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Atomic action: scrapes a single category page from a provider.
        Returns a tuple of (scraped_mods_list, detected_total_pages).
        """
        if not provider or not hasattr(provider, "scrape_category_page"):
            return [], 0
        return provider.scrape_category_page(category, page=page_num)

    def fetch_mod_details(self, provider: Any, page_url: str) -> Dict[str, Any]:
        """
        Atomic action: fetches full details for a single mod from its page URL.
        """
        if not provider or not hasattr(provider, "get_mod_details"):
            return {}
        det = provider.get_mod_details(page_url)
        if hasattr(det, "model_dump"):
            return det.model_dump()
        elif isinstance(det, dict):
            return det
        return {}

    def upsert_mods_batch(
        self, session: Session, mods_data: List[Dict[str, Any]], default_category: str
    ) -> Tuple[int, int]:
        """
        Atomic action: upserts a batch of mods into the CatalogMod table in a single transaction.
        Returns (new_count, updated_count).
        """
        if not mods_data:
            return 0, 0

        remote_ids = [m["remote_id"] for m in mods_data if m.get("remote_id")]
        existing_map: Dict[Tuple[str, str], CatalogMod] = {}
        if remote_ids:
            found = session.query(CatalogMod).filter(CatalogMod.remote_id.in_(remote_ids)).all()
            existing_map = {(str(m.source or ""), str(m.remote_id or "")): m for m in found}

        new_count = 0
        updated_count = 0

        for m_data in mods_data:
            source = m_data.get("source", "loverslab")
            r_id = m_data.get("remote_id", "")
            existing = existing_map.get((source, r_id))

            if not existing:
                mod_record = CatalogMod(
                    source=source,
                    remote_id=r_id,
                    title=m_data["title"],
                    author=m_data.get("author", "Unknown"),
                    category=m_data.get("category", default_category),
                    page_url=m_data["page_url"],
                    thumbnail_url=m_data.get("thumbnail_url", ""),
                    published_date=m_data.get("published_date"),
                    updated_date=m_data.get("updated_date"),
                    patreon_status=m_data.get("patreon_status", "NONE"),
                    patreon_tier=m_data.get("patreon_tier", ""),
                )
                mod_record.set_tags_list(m_data.get("tags", []))
                if m_data.get("external_links"):
                    mod_record.set_external_links_list(m_data["external_links"])
                session.add(mod_record)
                new_count += 1
            else:
                existing.title = m_data["title"]
                existing.author = m_data.get("author", existing.author)
                existing.thumbnail_url = m_data.get("thumbnail_url", existing.thumbnail_url)
                existing.updated_date = m_data.get("updated_date", existing.updated_date)
                if m_data.get("patreon_status"):
                    existing.patreon_status = m_data["patreon_status"]
                if m_data.get("patreon_tier"):
                    existing.patreon_tier = m_data["patreon_tier"]
                if m_data.get("external_links"):
                    existing.set_external_links_list(m_data["external_links"])
                existing.set_tags_list(m_data.get("tags", []))
                updated_count += 1

        session.commit()
        return new_count, updated_count

    def update_mod_scraped_details(self, session: Session, cat_mod: CatalogMod, det_dict: Dict[str, Any]) -> None:
        """
        Atomic action: updates catalog mod with freshly scraped details from provider.
        """
        if det_dict.get("requirements_text") is not None or det_dict.get("requirements_status"):
            cat_mod.requirements_text = det_dict.get("requirements_text")
            cat_mod.requirements_status = det_dict.get("requirements_status", "NONE")
            cat_mod.set_requirements_mods_list(det_dict.get("requirements_mods", []))
        if det_dict.get("download_urls"):
            cat_mod.set_download_urls_list(det_dict.get("download_urls", []))
        if det_dict.get("external_links"):
            cat_mod.set_external_links_list(det_dict.get("external_links", []))
        session.commit()
