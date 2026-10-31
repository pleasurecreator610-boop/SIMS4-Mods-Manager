"""
SimsFinds Provider & Scraper: SimsFinds (simsfinds.com) integration for Sims 4 Mods Manager.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from plugins.simsfinds.comments import (
    check_user_already_commented as _sfinds_check_commented,
    delete_mod_comment as _sfinds_delete_comment,
    get_creator_info as _sfinds_get_creator_info,
    post_mod_comment as _sfinds_post_comment,
)
from plugins.simsfinds.downloader import download_simsfinds_file
from plugins.simsfinds.parsers import (
    extract_simsfinds_download_links,
    extract_simsfinds_requirements,
    parse_simsfinds_browse_html,
)
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger


@ProviderRegistry.register_provider("simsfinds")
class SimsFindsProvider(BaseSourceProvider):
    """Fournisseur pour SimsFinds (simsfinds.com / sims4mods.cc)."""

    base_url = "https://www.simsfinds.com"
    provider_name = "simsfinds"
    display_name = "SimsFinds"
    login_url = "https://www.simsfinds.com/en/downloads/sims4"

    CATEGORIES = [
        {
            "id": "sfinds_hairstyles",
            "name": "Hairstyles (SimsFinds)",
            "slug": "hairstyles",
            "hashtag_id": 1,
            "url": "https://www.simsfinds.com/en/downloads/sims4/hairstyles-1",
            "default_pages": 4,
        },
        {
            "id": "sfinds_clothing",
            "name": "Clothing (SimsFinds)",
            "slug": "clothing",
            "hashtag_id": 2,
            "url": "https://www.simsfinds.com/en/downloads/sims4/clothing-2",
            "default_pages": 5,
        },
        {
            "id": "sfinds_accessories",
            "name": "Accessories (SimsFinds)",
            "slug": "accessories",
            "hashtag_id": 7,
            "url": "https://www.simsfinds.com/en/downloads/sims4/accessories-7",
            "default_pages": 3,
        },
        {
            "id": "sfinds_shoes",
            "name": "Shoes (SimsFinds)",
            "slug": "shoes",
            "hashtag_id": 6,
            "url": "https://www.simsfinds.com/en/downloads/sims4/shoes-6",
            "default_pages": 3,
        },
        {
            "id": "sfinds_makeup",
            "name": "Makeup (SimsFinds)",
            "slug": "makeup",
            "hashtag_id": 8,
            "url": "https://www.simsfinds.com/en/downloads/sims4/makeup-8",
            "default_pages": 3,
        },
        {
            "id": "sfinds_skintones",
            "name": "Skintones & Details (SimsFinds)",
            "slug": "skintones",
            "hashtag_id": 9,
            "url": "https://www.simsfinds.com/en/downloads/sims4/skintones-9",
            "default_pages": 2,
        },
        {
            "id": "sfinds_eyebrows",
            "name": "Eyebrows (SimsFinds)",
            "slug": "eyebrows",
            "hashtag_id": 803,
            "url": "https://www.simsfinds.com/en/downloads/sims4/eyebrows-803",
            "default_pages": 2,
        },
        {
            "id": "sfinds_objects",
            "name": "Objects & Furniture (SimsFinds)",
            "slug": "objects",
            "hashtag_id": 12,
            "url": "https://www.simsfinds.com/en/downloads/sims4/objects-12",
            "default_pages": 4,
        },
        {
            "id": "sfinds_build_mode",
            "name": "Build Mode (SimsFinds)",
            "slug": "build-mode",
            "hashtag_id": 11,
            "url": "https://www.simsfinds.com/en/downloads/sims4/build-mode-11",
            "default_pages": 3,
        },
        {
            "id": "sfinds_mods",
            "name": "Mods & Presets (SimsFinds)",
            "slug": "mods",
            "hashtag_id": 4,
            "url": "https://www.simsfinds.com/en/downloads/sims4/mods-4",
            "default_pages": 3,
        },
        {
            "id": "sfinds_sims",
            "name": "Sims (SimsFinds)",
            "slug": "sims",
            "hashtag_id": 10,
            "url": "https://www.simsfinds.com/en/downloads/sims4/sims-10",
            "default_pages": 2,
        },
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._min_request_interval = 0.5
        self._last_request_time = 0.0
        self._rate_limit_lock = threading.Lock()
        self.current_category_info: str = ""

    def _wait_for_rate_limit(self) -> None:
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()

    def check_access(self, mod_data: Optional[Dict[str, Any]] = None) -> str:
        """Vérifie le type d'accès pour un mod SimsFinds."""
        return "PUBLIC"

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        session = SessionManager.get_http_session(self.provider_name)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.simsfinds.com/en/downloads/sims4",
        }

        if ShutdownManager.is_shutting_down():
            return [], 0

        cat_name = category.get("name", category.get("id", "Unknown"))
        base_cat_url = category.get("url", f"{self.base_url}/en/downloads/sims4")
        hid = category.get("hashtag_id", 2)

        if page == 1:
            target_url = base_cat_url
        else:
            target_url = (
                f"https://s8.simsfinds.com/cached/files/downloads/funcoes/carregar-downloads.php?g=62&h={hid}&p={page}"
            )

        logger.info(f"Scraping SimsFinds [{cat_name}] page {page}: {target_url}")
        self._wait_for_rate_limit()

        results: List[Dict[str, Any]] = []
        try:
            resp = session.get(target_url, headers=headers, timeout=20)
            if resp.status_code == 429:
                time.sleep(2.0)
                resp = session.get(target_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                results = parse_simsfinds_browse_html(
                    resp.text,
                    category=category,
                    base_url=self.base_url,
                    source=self.provider_name,
                )
        except Exception as e:
            logger.error(f"Erreur scraping SimsFinds [{cat_name}] page {page}: {e}")

        return results, category.get("default_pages", 3)

    def scrape_catalog(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    def extract_requirements(
        self, soup_or_html: Any, own_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]]]:
        raw_html = ""
        if isinstance(soup_or_html, str):
            raw_html = soup_or_html
        elif hasattr(soup_or_html, "get_text"):
            raw_html = str(soup_or_html)

        reqs = extract_simsfinds_requirements(raw_html)
        mods_only = [r for r in reqs if r.get("type") == "MOD"]
        return mods_only, raw_html, reqs

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        details: Dict[str, Any] = {
            "title": "",
            "description": "",
            "author": "",
            "images": [],
            "download_urls": [],
            "requirements": [],
            "raw_requirements_html": "",
        }
        if not mod_url:
            return details

        session = SessionManager.get_http_session(self.provider_name)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.simsfinds.com/en/downloads/sims4",
        }

        try:
            self._wait_for_rate_limit()
            resp = session.get(mod_url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            title_el = soup.find("title")
            details["title"] = title_el.get_text(strip=True).replace(" - SimsFinds", "") if title_el else ""

            # Extraction auteur
            creator_el = soup.select_one("a[href*='/creator/'], a._ptflink-profile, ._creator-name")
            details["author"] = creator_el.get_text(strip=True) if creator_el else "SimsFinds Creator"

            # Extraction images
            imgs = []
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if "simsfinds" in src and any(ext in src.lower() for ext in [".jpg", ".png", ".webp"]):
                    imgs.append(src)
            details["images"] = imgs[:5]

            # Liens de téléchargement
            details["download_urls"] = extract_simsfinds_download_links(resp.text, base_url=self.base_url)

            # Requirements
            _, raw_html, reqs = self.extract_requirements(resp.text, own_id=mod_url)
            details["requirements"] = reqs
            details["raw_requirements_html"] = raw_html

        except Exception as e:
            logger.debug(f"Erreur extraction détails SimsFinds sur {mod_url}: {e}")

        return details

    def download_mod_file(
        self,
        file_info: Any,
        dest_path: Any,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        file_dict = file_info if isinstance(file_info, dict) else {"url": str(file_info)}
        return download_simsfinds_file(
            file_info=file_dict,
            dest_path=str(dest_path),
            progress_callback=progress_callback,
            session=session,
            provider_name=self.provider_name,
        )

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _sfinds_get_creator_info(page_url, session, self.base_url)

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _sfinds_check_commented(page_url, required_keywords, session, self.base_url, self.provider_name)

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _sfinds_post_comment(page_url, message, session, self.base_url, self.provider_name)

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _sfinds_delete_comment(page_url, "1", session, self.base_url, self.provider_name)

    def send_private_message(self, _recipient_username: str, _subject: str, _message: str) -> Tuple[bool, str]:
        return False, "Les messages privés SimsFinds ne sont pas configurés."

    def check_user_already_sent_pm(
        self, _recipient_username: str, _required_keywords: List[str]
    ) -> Tuple[bool, Optional[str]]:
        return False, None

    def category_url(self, cat_slug: str) -> str:
        return f"{self.base_url}/en/downloads/sims4/{cat_slug}"
