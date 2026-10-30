"""
ModTheSims Provider & Scraper: ModTheSims.info integration for Sims 4 Mods Manager.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from plugins.modthesims.comments import (
    check_user_already_commented as _mts_check_commented,
    delete_mod_comment as _mts_delete_comment,
    get_creator_info as _mts_get_creator_info,
    post_mod_comment as _mts_post_comment,
)
from plugins.modthesims.downloader import download_mts_file
from plugins.modthesims.parsers import (
    extract_mts_download_links,
    extract_mts_requirements,
    parse_mts_browse_html,
)
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger


@ProviderRegistry.register_provider("modthesims")
class ModTheSimsProvider(BaseSourceProvider):
    """Fournisseur officiel pour ModTheSims.info (TS4)."""

    base_url = "https://modthesims.info"
    provider_name = "modthesims"
    display_name = "ModTheSims"
    login_url = "https://modthesims.info/login.php"

    CATEGORIES = [
        {
            "id": "mts_game_mods",
            "name": "Game Mods (MTS)",
            "slug": "game-mods",
            "url": "https://modthesims.info/downloads/ts4/414/?showType=1",
            "default_pages": 5,
        },
        {
            "id": "mts_traits",
            "name": "Traits (MTS)",
            "slug": "traits",
            "url": "https://modthesims.info/downloads/ts4/747/?showType=1",
            "default_pages": 3,
        },
        {
            "id": "mts_careers",
            "name": "Careers (MTS)",
            "slug": "careers",
            "url": "https://modthesims.info/downloads/ts4/229/?showType=1",
            "default_pages": 3,
        },
        {
            "id": "mts_build_mode",
            "name": "Build Mode (MTS)",
            "slug": "build-mode",
            "url": "https://modthesims.info/downloads/ts4/380/?showType=1",
            "default_pages": 3,
        },
        {
            "id": "mts_buy_mode",
            "name": "Buy Mode (MTS)",
            "slug": "buy-mode",
            "url": "https://modthesims.info/downloads/ts4/385/?showType=1",
            "default_pages": 4,
        },
        {
            "id": "mts_body_shop",
            "name": "Body Shop (MTS)",
            "slug": "body-shop",
            "url": "https://modthesims.info/downloads/ts4/342/?showType=1",
            "default_pages": 4,
        },
        {
            "id": "mts_lots_housing",
            "name": "Lots & Housing (MTS)",
            "slug": "lots-housing",
            "url": "https://modthesims.info/downloads/ts4/143/?showType=1",
            "default_pages": 3,
        },
        {
            "id": "mts_sims",
            "name": "Sims (MTS)",
            "slug": "sims",
            "url": "https://modthesims.info/downloads/ts4/145/?showType=1",
            "default_pages": 2,
        },
        {
            "id": "mts_pets",
            "name": "Pets (MTS)",
            "slug": "pets",
            "url": "https://modthesims.info/downloads/ts4/485/?showType=1",
            "default_pages": 2,
        },
        {
            "id": "mts_programs_utilities",
            "name": "Programs and Utilities (MTS)",
            "slug": "programs-utilities",
            "url": "https://modthesims.info/downloads/ts4/139/?showType=1",
            "default_pages": 2,
        },
        {
            "id": "mts_miscellaneous",
            "name": "Miscellaneous (MTS)",
            "slug": "miscellaneous",
            "url": "https://modthesims.info/downloads/ts4/519/?showType=1",
            "default_pages": 2,
        },
    ]

    _mts_request_lock = threading.Lock()
    _last_request_ts: float = 0.0
    _min_request_interval: float = 0.5

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Game Mods (MTS)"

    @classmethod
    def _pace_request(cls, session: Any) -> None:
        if getattr(session, "_is_mock", False):
            return
        with cls._mts_request_lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_ts
            if elapsed < cls._min_request_interval:
                time.sleep(cls._min_request_interval - elapsed)
            cls._last_request_ts = time.monotonic()

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
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

    @staticmethod
    def _build_paginated_url(base_cat_url: str, page: int) -> str:
        clean = base_cat_url
        if "p=" in clean:
            clean = re.sub(r"p=\d+", f"p={page}", clean)
        else:
            delimiter = "&" if "?" in clean else "?"
            clean = f"{clean}{delimiter}p={page}"
        return clean

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        url = self._build_paginated_url(category["url"], page)
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping ModTheSims [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        self._pace_request(session)
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://modthesims.info/downloads/ts4/",
            }
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code == 429:
                logger.warning(f"MTS rate-limited (429) on {url}, backing off 2.5s...")
                time.sleep(2.5)
                resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"MTS request returned status {resp.status_code} for {url}")
                return results, detected_pages

            results, detected_pages = parse_mts_browse_html(
                resp.text, category, self.base_url, page, source=self.provider_name
            )
            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            logger.info(f"MTS [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error scraping MTS category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """ModTheSims mods are publicly accessible and free."""
        return "PUBLIC"

    def scrape_catalog(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    def extract_requirements(
        self,
        soup: BeautifulSoup,
        own_id: str = "",
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        return extract_mts_requirements(
            soup,
            page_text=soup.get_text(),
            own_id=own_id,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        session = SessionManager.get_http_session(self.provider_name)
        details: Dict[str, Any] = {
            "description": "",
            "download_urls": [],
            "requirements": [],
            "raw_requirements_html": "",
            "tags": [],
            "images": [],
        }
        if not mod_url:
            return details

        self._pace_request(session)
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://modthesims.info/downloads/ts4/",
            }
            resp = session.get(mod_url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            desc_el = soup.select_one("#descriptionbox, .downloadDescription, #actualcontent1")
            details["description"] = desc_el.get_text("\n", strip=True) if desc_el else ""

            # Images
            imgs = []
            for img in soup.select("#screenshots img, .main-carousel img, .featuredimage"):
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("//"):
                        src = f"https:{src}"
                    imgs.append(src)
            details["images"] = imgs

            # Download links
            details["download_urls"] = extract_mts_download_links(soup, mod_url)

            # Requirements
            _, raw_html, reqs = self.extract_requirements(soup, own_id=mod_url)
            details["requirements"] = reqs
            details["raw_requirements_html"] = raw_html

        except Exception as e:
            logger.debug(f"Error fetching MTS mod details from {mod_url}: {e}")

        return details

    def download_mod_file(
        self,
        file_info: Dict[str, Any],
        dest_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return download_mts_file(
            file_info=file_info,
            dest_path=dest_path,
            progress_callback=progress_callback,
            session=session,
            provider_name=self.provider_name,
        )

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mts_get_creator_info(page_url, session, self.base_url)

    def check_user_already_commented(
        self, page_url: str, required_keywords: List[str]
    ) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mts_check_commented(page_url, required_keywords, session, self.base_url, self.provider_name)

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mts_post_comment(page_url, message, session, self.base_url, self.provider_name)

    def delete_mod_comment(
        self, page_url: str, required_keywords: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mts_delete_comment(page_url, session, self.base_url, required_keywords, self.provider_name)

    def send_private_message(self, recipient_username: str, subject: str, message: str) -> Tuple[bool, str]:
        return False, "Les messages privés ModTheSims ne sont pas configurés."

    def check_user_already_sent_pm(self, recipient_username: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        return False, None

    def category_url(self, cat_slug: str) -> str:
        return f"{self.base_url}/downloads/ts4/"
