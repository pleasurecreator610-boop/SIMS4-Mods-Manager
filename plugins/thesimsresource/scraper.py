"""
TheSimsResourceProvider: Provider plugin for scraping The Sims Resource (TSR) Sims 4 catalog
(https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/),
extracting embedded `data-item` JSON metadata, required meshes/dependencies (`RequiredItems`,
`requiredDownloadIds`, `requiredDownloadExternalLinks`), and downloading `.package`/`.zip` archives
via TSR's AJAX ticket flow (`/ajax.php?c=downloads&a=initDownload` -> `/ajax.php?c=downloads&a=getdownloadurl`).
"""

from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup

from plugins.loverslab.parsers import sanitize_description_html
from plugins.thesimsresource.comments import (
    check_user_already_commented as _tsr_check_commented,
    delete_mod_comment as _tsr_delete_comment,
    get_creator_info as _tsr_get_creator_info,
    post_mod_comment as _tsr_post_comment,
)
from plugins.thesimsresource.downloader import download_tsr_file
from plugins.thesimsresource.parsers import (
    TSR_KNOWN_CROSS_DEPENDENCIES,
    _parse_tsr_timestamp,
    extract_item_id as _tsr_extract_item_id,
    extract_requirements as _tsr_extract_reqs,
    parse_tsr_browse_html,
)
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger

__all__ = [
    "TSR_KNOWN_CROSS_DEPENDENCIES",
    "TheSimsResourceProvider",
    "_parse_tsr_timestamp",
    "download_tsr_file",
    "parse_tsr_browse_html",
]


@ProviderRegistry.register_provider("thesimsresource")
class TheSimsResourceProvider(BaseSourceProvider):
    """Provider for scraping The Sims Resource (TSR) categories,

    extracting metadata, required items/meshes and downloading files via ticket flow.
    """

    provider_name = "thesimsresource"
    display_name = "The Sims Resource"
    base_url = "https://www.thesimsresource.com"
    sims4_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    sims4_browse_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    category_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    login_url = "https://www.thesimsresource.com/login/"

    CATEGORIES = [
        {
            "id": "tsr_mods",
            "name": "Mods (TSR)",
            "slug": "sims4-mods",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-mods/skipsetitems/1/",
            "default_pages": 5,
        },
        {
            "id": "tsr_clothing",
            "name": "Clothing (TSR)",
            "slug": "sims4-clothing",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-clothing/skipsetitems/1/",
            "default_pages": 5,
        },
        {
            "id": "tsr_hair",
            "name": "Hair (TSR)",
            "slug": "sims4-hair",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-hair/skipsetitems/1/",
            "default_pages": 5,
        },
        {
            "id": "tsr_shoes",
            "name": "Shoes (TSR)",
            "slug": "sims4-shoes",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-shoes/skipsetitems/1/",
            "default_pages": 3,
        },
        {
            "id": "tsr_accessories",
            "name": "Accessories (TSR)",
            "slug": "sims4-accessories",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-accessories/skipsetitems/1/",
            "default_pages": 3,
        },
        {
            "id": "tsr_makeup",
            "name": "Makeup (TSR)",
            "slug": "sims4-makeup",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-makeup/skipsetitems/1/",
            "default_pages": 3,
        },
        {
            "id": "tsr_skintones",
            "name": "Skintones (TSR)",
            "slug": "sims4-skintones",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-skintones/skipsetitems/1/",
            "default_pages": 2,
        },
        {
            "id": "tsr_eyecolors",
            "name": "Eye Colors (TSR)",
            "slug": "sims4-eyecolors",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-eyecolors/skipsetitems/1/",
            "default_pages": 2,
        },
        {
            "id": "tsr_objects",
            "name": "Objects (TSR)",
            "slug": "sims4-objects",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-objects/skipsetitems/1/",
            "default_pages": 5,
        },
        {
            "id": "tsr_sets",
            "name": "Sets (TSR)",
            "slug": "sims4-sets",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-sets/skipsetitems/1/",
            "default_pages": 4,
        },
        {
            "id": "tsr_lots_rooms",
            "name": "Lots & Rooms (TSR)",
            "slug": "sims4-lots",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-lots/skipsetitems/1/",
            "default_pages": 3,
        },
        {
            "id": "tsr_sims",
            "name": "Sims (TSR)",
            "slug": "sims4-sims",
            "url": "https://www.thesimsresource.com/downloads/browse/category/sims4-sims/skipsetitems/1/",
            "default_pages": 2,
        },
    ]

    _tsr_request_lock = threading.Lock()
    _last_request_ts: float = 0.0
    _min_request_interval: float = 0.6

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Clothing (TSR)"

    @classmethod
    def _pace_request(cls, session: Any) -> None:
        if getattr(session, "_is_mock", False):
            return
        with cls._tsr_request_lock:
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
        clean = base_cat_url.rstrip("/")
        if page <= 1:
            return clean + "/"
        clean = re.sub(r"/page/\d+", "", clean)
        return f"{clean}/page/{page}/"

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        url = self._build_paginated_url(category["url"], page)
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping TSR [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        self._pace_request(session)
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 429:
                logger.warning(f"TSR rate-limited (429) on {url}, backing off 3.0s...")
                time.sleep(3.0)
                resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"TSR request returned status {resp.status_code} for {url}")
                return results, detected_pages

            results, detected_pages = parse_tsr_browse_html(
                resp.text, category, self.base_url, page, source=self.provider_name
            )
            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            logger.info(f"TSR [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error while scraping TSR category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def scrape_catalog(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    @staticmethod
    def _extract_item_id(url_or_id: str, soup: Optional[BeautifulSoup] = None, html_text: str = "") -> Optional[str]:
        return _tsr_extract_item_id(url_or_id, soup, html_text)

    def extract_requirements(
        self,
        soup: BeautifulSoup,
        own_id: str = "",
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        return _tsr_extract_reqs(soup, own_id=own_id, base_url=self.base_url, provider_name=self.provider_name)

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        session = SessionManager.get_http_session(self.provider_name)
        details: Dict[str, Any] = {
            "description": "",
            "download_urls": [],
            "external_links": [],
            "patreon_status": "NONE",
            "patreon_tier": "",
            "version_str": "",
            "requirements_text": None,
            "requirements_status": "NONE",
            "requirements_mods": [],
            "screenshots": [],
        }

        try:
            resp = session.get(mod_url, timeout=15)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            item_id = self._extract_item_id(mod_url, soup, resp.text)
            if not item_id:
                m_num = re.search(r"(\d{5,10})", mod_url)
                item_id = m_num.group(1) if m_num else ""

            if item_id:
                init_dl_url = f"{self.base_url}/ajax.php?c=downloads&a=initDownload&itemid={item_id}&setItems=&format=zip"
                details["download_urls"].append(
                    {
                        "name": f"Téléchargement TSR (#{item_id})",
                        "url": init_dl_url,
                        "size": 0,
                    }
                )
            else:
                details["download_urls"].append(
                    {
                        "name": "Téléchargement TSR",
                        "url": mod_url,
                        "size": 0,
                    }
                )

            gallery_imgs: List[str] = []
            for img in soup.select(
                ".item-screenshot img, .item-image-wrapper img, #details-images img, .carousel-item img, img.main-image"
            ):
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    full_src = src if src.startswith("http") else urllib.parse.urljoin(self.base_url, src)
                    if full_src not in gallery_imgs:
                        gallery_imgs.append(full_src)

            desc_elem = soup.select_one(".item-description, #item-description, .description, article")
            if desc_elem:
                clean_body_html, body_imgs = sanitize_description_html(desc_elem, self.base_url)
                for src in body_imgs:
                    if src not in gallery_imgs:
                        gallery_imgs.append(src)
                details["description"] = clean_body_html
                details["screenshots"] = gallery_imgs
            else:
                details["screenshots"] = gallery_imgs

            req_text, req_status, req_mods = self.extract_requirements(soup, own_id=item_id or "")
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_elem = soup.select_one(".item-version, .version, .details-meta-version")
            if v_elem:
                details["version_str"] = v_elem.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error extracting TSR details for {mod_url}: {e}", exc_info=True)

        return details

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        session = SessionManager.get_http_session(self.provider_name)
        target_url = f"{self.base_url}/downloads/details/id/{remote_id}"
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_elem = soup.select_one(".item-title, h1.title, h1")
                author_elem = soup.select_one("a.creator-name, .big-creator-name a, a[href*='/artists/']")
                v_elem = soup.select_one(".item-version, .version")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_elem.get_text(strip=True) if title_elem else f"TSR Item {remote_id}",
                    "author": author_elem.get_text(strip=True) if author_elem else "TSR Artist",
                    "page_url": target_url,
                    "version_str": v_elem.get_text(strip=True) if v_elem else "",
                }
        except Exception as e:
            logger.debug(f"fetch_mod_by_id failed for TSR {remote_id}: {e}")
        return None

    def download_mod_file(
        self,
        download_url: Optional[str] = None,
        dest_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        ticket_poll_interval: float = 2.5,
        max_ticket_polls: int = 6,
        **kwargs,
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return download_tsr_file(
            download_url=download_url,
            dest_path=dest_path,
            session=session,
            base_url=self.base_url,
            progress_callback=progress_callback,
            ticket_poll_interval=ticket_poll_interval,
            max_ticket_polls=max_ticket_polls,
            sleep_fn=time.sleep,
            **kwargs,
        )

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        return "PUBLIC"

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _tsr_get_creator_info(page_url, session, self.base_url)

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _tsr_check_commented(page_url, required_keywords, session, self.provider_name)

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _tsr_post_comment(page_url, message, session, self.base_url, self.provider_name)

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _tsr_delete_comment(page_url, session, self.base_url, required_keywords)
