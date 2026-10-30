"""
CurseForgeProvider: Provider plugin for scraping CurseForge The Sims 4 catalog (https://www.curseforge.com/sims4),
extracting project metadata, dependencies (/relations/dependencies + description), and downloading mod archives
via CurseForge's CDN (edge.forgecdn.net / /api/v1/mods/{projectId}/files/{fileId}/download).
"""

from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import requests

from plugins.curseforge.comments import (
    check_user_already_commented as _cf_check_commented,
    delete_mod_comment as _cf_delete_comment,
    get_creator_info as _cf_get_creator_info,
    post_mod_comment as _cf_post_comment,
)
from plugins.curseforge.downloader import download_curseforge_file
from plugins.curseforge.parsers import (
    CURSEFORGE_KNOWN_DEPENDENCIES,
    extract_project_and_file_ids as _cf_extract_ids,
    extract_requirements as _cf_extract_reqs,
    parse_curseforge_search_html,
)
from plugins.loverslab.parsers import sanitize_description_html
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger

__all__ = [
    "CURSEFORGE_KNOWN_DEPENDENCIES",
    "CurseForgeProvider",
    "download_curseforge_file",
    "parse_curseforge_search_html",
]


@ProviderRegistry.register_provider("curseforge")
class CurseForgeProvider(BaseSourceProvider):
    """Provider for scraping CurseForge The Sims 4 mods and CC categories,

    extracting project details and dependencies, and downloading archives from ForgeCDN.
    """

    provider_name = "curseforge"
    display_name = "CurseForge"
    base_url = "https://www.curseforge.com"
    sims4_url = "https://www.curseforge.com/sims4"
    category_url = "https://www.curseforge.com/sims4"
    login_url = "https://www.curseforge.com/login"

    CATEGORIES = [
        {
            "id": "cf_mods_gameplay",
            "name": "Mods - Gameplay (CurseForge)",
            "slug": "mods-gameplay",
            "url": "https://www.curseforge.com/sims4/search?class=mods&pageSize=20&sortBy=relevancy&categories=gameplay",
            "default_pages": 5,
        },
        {
            "id": "cf_mods_utilities",
            "name": "Mods - Utilities (CurseForge)",
            "slug": "mods-utilities",
            "url": "https://www.curseforge.com/sims4/search?class=mods&pageSize=20&sortBy=relevancy&categories=utilities",
            "default_pages": 3,
        },
        {
            "id": "cf_mods_poses",
            "name": "Mods - Poses & Animations (CurseForge)",
            "slug": "mods-poses-animations",
            "url": "https://www.curseforge.com/sims4/search?class=mods&pageSize=20&sortBy=relevancy&categories=poses-and-animations",
            "default_pages": 3,
        },
        {
            "id": "cf_create_a_sim",
            "name": "Create a Sim (CurseForge)",
            "slug": "create-a-sim",
            "url": "https://www.curseforge.com/sims4/search?class=create-a-sim&pageSize=20&sortBy=relevancy",
            "default_pages": 5,
        },
        {
            "id": "cf_build_buy",
            "name": "Build / Buy (CurseForge)",
            "slug": "build-buy",
            "url": "https://www.curseforge.com/sims4/search?class=build-buy&pageSize=20&sortBy=relevancy",
            "default_pages": 5,
        },
        {
            "id": "cf_rooms_lots",
            "name": "Rooms / Lots (CurseForge)",
            "slug": "rooms-lots",
            "url": "https://www.curseforge.com/sims4/search?class=rooms-lots&pageSize=20&sortBy=relevancy",
            "default_pages": 3,
        },
        {
            "id": "cf_sims_households",
            "name": "Sims / Households (CurseForge)",
            "slug": "sims-households",
            "url": "https://www.curseforge.com/sims4/search?class=sims-households&pageSize=20&sortBy=relevancy",
            "default_pages": 3,
        },
        {
            "id": "cf_worlds",
            "name": "Worlds (CurseForge)",
            "slug": "worlds",
            "url": "https://www.curseforge.com/sims4/search?class=worlds&pageSize=20&sortBy=relevancy",
            "default_pages": 1,
        },
        {
            "id": "cf_translations",
            "name": "Translations (CurseForge)",
            "slug": "translations",
            "url": "https://www.curseforge.com/sims4/search?class=translations&pageSize=20&sortBy=relevancy",
            "default_pages": 2,
        },
    ]

    _cf_request_lock = threading.Lock()
    _last_request_ts: float = 0.0
    _min_request_interval: float = 1.0

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Mods - Gameplay (CurseForge)"

    @classmethod
    def _pace_request(cls, session: Any) -> None:
        if getattr(session, "_is_mock", False):
            return
        with cls._cf_request_lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_ts
            if elapsed < cls._min_request_interval:
                time.sleep(cls._min_request_interval - elapsed)
            cls._last_request_ts = time.monotonic()

    def _get_with_retry(
        self,
        session: Any,
        url: str,
        timeout: int = 20,
        max_retries: int = 5,
        backoff_factor: float = 2.0,
    ) -> Optional[requests.Response]:
        for attempt in range(max_retries + 1):
            if ShutdownManager.is_shutting_down():
                return None
            self._pace_request(session)
            try:
                resp = session.get(url, timeout=timeout)
                if resp.status_code == 429:
                    if attempt < max_retries:
                        retry_after_hdr = resp.headers.get("Retry-After")
                        delay = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else backoff_factor * (1.8**attempt)
                        # Augmenter l'intervalle global pour calmer le serveur
                        with self._cf_request_lock:
                            self._min_request_interval = min(3.0, self._min_request_interval + 0.3)
                        logger.warning(
                            f"CurseForge request rate-limited (429) for {url}, backing off {delay:.1f}s (tentative {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                return resp
            except Exception as exc:
                if attempt < max_retries:
                    time.sleep(backoff_factor * (1.5**attempt))
                    continue
                logger.debug(f"CurseForge GET failed for {url}: {exc}")
                return None
        return None

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
        if page <= 1:
            return base_cat_url
        sep = "&" if "?" in base_cat_url else "?"
        return f"{base_cat_url}{sep}page={page}"

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        url = self._build_paginated_url(category["url"], page)
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping CurseForge [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        try:
            resp = self._get_with_retry(session, url, timeout=20)
            if resp is None:
                return results, detected_pages
            if resp.status_code != 200:
                logger.warning(f"CurseForge request returned status {resp.status_code} for {url}")
                return results, detected_pages

            results, detected_pages = parse_curseforge_search_html(
                resp.text, category, self.base_url, page, source=self.provider_name
            )
            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            logger.info(f"CurseForge [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error while scraping CurseForge category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def scrape_catalog(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    @staticmethod
    def _extract_project_and_file_ids(soup: BeautifulSoup, html_text: str) -> Tuple[Optional[str], Optional[str]]:
        return _cf_extract_ids(soup, html_text)

    def extract_requirements(
        self,
        soup: BeautifulSoup,
        rel_soup: Optional[BeautifulSoup] = None,
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        return _cf_extract_reqs(soup, rel_soup)

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
            resp = self._get_with_retry(session, mod_url, timeout=15)
            if resp is None or resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            project_id, file_id = self._extract_project_and_file_ids(soup, resp.text)

            if project_id and file_id:
                api_dl_url = f"{self.base_url}/api/v1/mods/{project_id}/files/{file_id}/download"
                details["download_urls"].append(
                    {
                        "name": f"Téléchargement CurseForge (#{file_id})",
                        "url": api_dl_url,
                        "size": 0,
                    }
                )
            elif file_id:
                details["download_urls"].append(
                    {
                        "name": f"Téléchargement CurseForge (#{file_id})",
                        "url": f"{mod_url.rstrip('/')}/download/{file_id}",
                        "size": 0,
                    }
                )
            else:
                details["download_urls"].append(
                    {
                        "name": "Téléchargement CurseForge",
                        "url": mod_url,
                        "size": 0,
                    }
                )

            gallery_imgs: List[str] = []
            for img in soup.select(".gallery-item img, .project-screenshot img, .carousel img, .screenshots img"):
                src = img.get("src") or img.get("data-src") or ""
                if src and src.startswith("http") and src not in gallery_imgs:
                    gallery_imgs.append(src)

            content_elem = soup.select_one(".project-description, .description, article, .tab-description")
            if content_elem:
                clean_body_html, body_imgs = sanitize_description_html(content_elem, self.base_url)
                for src in body_imgs:
                    if src.startswith("http") and src not in gallery_imgs:
                        gallery_imgs.append(src)
                details["description"] = clean_body_html
                details["screenshots"] = gallery_imgs
            else:
                details["screenshots"] = gallery_imgs

            rel_url = f"{mod_url.rstrip('/')}/relations/dependencies"
            rel_resp = self._get_with_retry(session, rel_url, timeout=10)
            rel_soup = BeautifulSoup(rel_resp.text, "html.parser") if rel_resp and rel_resp.status_code == 200 else None

            req_text, req_status, req_mods = self.extract_requirements(soup, rel_soup=rel_soup)
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_elem = soup.select_one(".version, span.file-name, .project-details .date")
            if v_elem:
                details["version_str"] = v_elem.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error extracting CurseForge details for {mod_url}: {e}", exc_info=True)

        return details

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        session = SessionManager.get_http_session(self.provider_name)
        target_url = f"{self.base_url}/sims4/mods/{remote_id}"
        try:
            resp = self._get_with_retry(session, target_url, timeout=15)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_elem = soup.select_one("h1.project-title, h1.name, h1")
                author_elem = soup.select_one("a.author-name, .author-name, a[href*='/members/']")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_elem.get_text(strip=True) if title_elem else f"Mod {remote_id}",
                    "author": author_elem.get_text(strip=True) if author_elem else "CurseForge Creator",
                    "page_url": target_url,
                    "version_str": "",
                }
        except Exception as e:
            logger.debug(f"fetch_mod_by_id failed for {remote_id}: {e}")
        return None

    def download_mod_file(
        self,
        download_url: Optional[str] = None,
        dest_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return download_curseforge_file(
            download_url=download_url,
            dest_path=dest_path,
            session=session,
            base_url=self.base_url,
            progress_callback=progress_callback,
            **kwargs,
        )

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        return "PUBLIC"

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _cf_get_creator_info(page_url, session, self.base_url, self._get_with_retry)

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _cf_check_commented(page_url, required_keywords, session, self.base_url, self.provider_name, self._get_with_retry)

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _cf_post_comment(page_url, message, session, self.base_url, self._get_with_retry)

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _cf_delete_comment(page_url, session, self.base_url, required_keywords, self.provider_name, self._get_with_retry)
