"""
IPS Base: Unified Invision Community (IPS4) forum, file downloading, and catalog scraping engine.
Shared by LoversLab, NSFWMods, and other IPS4-based platforms.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.providers.base import BaseSourceProvider

__all__ = [
    "BaseIPSForumProvider",
]


class BaseIPSForumProvider(BaseSourceProvider):
    """Abstract Base Class for IPS4-based providers (LoversLab, NSFWMods, etc.).

    Standardizes category partitioning, pagination tracking, forum actions, and scraping.
    """

    CATEGORIES: List[Dict[str, Any]] = []
    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        first_cat = self.CATEGORIES[0]["name"] if self.CATEGORIES else self.display_name
        self.current_category_info: str = first_cat

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        """Updates the page count cache for a category."""
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
        """Returns the total number of pages across all configured subcategories."""
        return sum(pages for _, pages in self._get_category_page_counts())

    def _resolve_category_page(self, global_page: int) -> Tuple[Dict[str, Any], int, int]:
        counts = self._get_category_page_counts()
        remaining = max(1, global_page)
        for cat, num_pages in counts:
            if remaining <= num_pages:
                return cat, remaining, num_pages
            remaining -= num_pages
        last_cat, last_pages = counts[-1]
        return last_cat, max(1, remaining), last_pages

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Scrapes a single page of an IPS4 category. To be implemented by subclasses."""
        raise NotImplementedError

    def scrape_catalog_page(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """Scrapes the unified global catalog across all subcategories."""
        category, sub_page, _ = self._resolve_category_page(page)
        self.current_category_info = f"{category['name']} ({self.display_name})"
        results, _ = self.scrape_category_page(category, sub_page, limit)
        return results

    def download_mod(
        self,
        download_url: Optional[str] = None,
        dest_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs: Any,
    ) -> Tuple[bool, str]:
        """Downloads a mod file from this IPS4 platform. To be implemented by subclasses."""
        raise NotImplementedError

    def check_missing_requirements_reported(
        self,
        page_url: str,
        required_keywords: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Checks if the authenticated user has already commented about missing requirements."""
        return False, None

    def post_missing_requirements_comment(
        self,
        page_url: str,
        comment_text: str,
    ) -> Tuple[bool, str]:
        """Submits a public comment regarding missing requirements."""
        return False, "Non implémenté sur ce fournisseur."

    def send_private_message_author(
        self,
        author_name: str,
        subject: str,
        message_body: str,
    ) -> Tuple[bool, str]:
        """Sends an IPS private message to the author."""
        return False, "Non implémenté sur ce fournisseur."
