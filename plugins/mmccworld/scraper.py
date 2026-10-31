"""
Maxis Match CC World Provider & Scraper: Intégration Tumblr (maxismatchccworld.tumblr.com).
Exploite le flux RSS souverain, les tags de curation et le résolveur SimFileShare.
"""

from __future__ import annotations

from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from bs4 import BeautifulSoup

from plugins.mmccworld.comments import (
    check_user_already_commented as _mmccw_check_commented,
    delete_mod_comment as _mmccw_delete_comment,
    get_creator_info as _mmccw_get_creator_info,
    post_mod_comment as _mmccw_post_comment,
)
from plugins.mmccworld.downloader import download_mmccworld_file
from plugins.mmccworld.parsers import (
    extract_download_links,
    extract_mmccworld_requirements,
    parse_mmccworld_rss,
)
from src.core.dto import ModDetailsDTO
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger


@ProviderRegistry.register_provider("mmccworld")
class MMCCWorldProvider(BaseSourceProvider):
    """Fournisseur pour Maxis Match CC World (maxismatchccworld.tumblr.com)."""

    base_url = "https://maxismatchccworld.tumblr.com"
    rss_url = "https://maxismatchccworld.tumblr.com/rss"
    provider_name = "mmccworld"
    display_name = "Maxis Match CC World"
    login_url = "https://www.tumblr.com/login?redirect_to=https%3A%2F%2Fmaxismatchccworld.tumblr.com%2F"

    CATEGORIES = [
        {
            "id": "mmccw_clothing",
            "name": "Clothing (MMCCW)",
            "slug": "clothing",
            "tag": "s4clothing",
            "default_pages": 4,
        },
        {
            "id": "mmccw_hair",
            "name": "Hairstyles (MMCCW)",
            "slug": "hair",
            "tag": "s4hair",
            "default_pages": 4,
        },
        {
            "id": "mmccw_accessories",
            "name": "Accessories (MMCCW)",
            "slug": "accessories",
            "tag": "s4accessories",
            "default_pages": 3,
        },
        {
            "id": "mmccw_shoes",
            "name": "Shoes (MMCCW)",
            "slug": "shoes",
            "tag": "s4shoes",
            "default_pages": 3,
        },
        {
            "id": "mmccw_build_buy",
            "name": "Build & Buy (MMCCW)",
            "slug": "build_buy",
            "tag": "s4build",
            "default_pages": 4,
        },
        {
            "id": "mmccw_gameplay",
            "name": "Gameplay & Mods (MMCCW)",
            "slug": "gameplay",
            "tag": "s4mods",
            "default_pages": 3,
        },
        {
            "id": "mmccw_poses",
            "name": "Poses & Animations (MMCCW)",
            "slug": "poses",
            "tag": "s4poses",
            "default_pages": 2,
        },
        {
            "id": "mmccw_miscellaneous",
            "name": "All Recent Finds (MMCCW)",
            "slug": "all",
            "tag": "s4cc",
            "default_pages": 3,
        },
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rate_limit_lock = threading.Lock()
        self._last_request_time = 0.0

    def get_categories(self) -> List[Dict[str, Any]]:
        return self.CATEGORIES

    def _throttle(self, delay: float = 0.3) -> None:
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_request_time = time.time()

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """Scrape le flux de créations de Maxis Match CC World."""
        first_cat = self.CATEGORIES[0] if self.CATEGORIES else {"id": "mmccw_clothing", "name": "Clothing"}
        return self.scrape_category(first_cat, page=page, page_size=limit)

    def scrape_category(
        self,
        category: Dict[str, Any],
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """Scrape une catégorie ou le flux RSS de Maxis Match CC World."""
        if ShutdownManager.is_shutting_down():
            return []

        self._throttle(0.2)
        tag = category.get("tag", "s4cc")
        feed_url = f"{self.base_url}/tagged/{tag}/rss" if tag != "s4cc" else self.rss_url

        try:
            logger.info(f"Scraping Maxis Match CC World pour [{category.get('name')}] via flux RSS...")
            session = SessionManager.get_http_session(self.provider_name)
            resp = session.get(feed_url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"Erreur HTTP MMCCWorld RSS: {resp.status_code}")
                # Fallback sur le flux global si le flux tagué est restreint
                if feed_url != self.rss_url:
                    resp = session.get(self.rss_url, timeout=20)

            if resp.status_code == 200:
                mods = parse_mmccworld_rss(resp.text, category, source=self.provider_name)
                # Appliquer la pagination demandée
                start_idx = (page - 1) * page_size
                paged_mods = mods[start_idx : start_idx + page_size]
                logger.info(f"MMCCWorld [{category.get('name')}] p.{page} : {len(paged_mods)} création(s).")
                return paged_mods

        except Exception as e:
            logger.error(f"Erreur lors du scraping MMCCWorld [{category.get('name')}]: {e}")

        return []

    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """Extrait les informations détaillées d'une création Maxis Match CC World."""
        if not mod_url:
            return {}

        try:
            session = SessionManager.get_http_session(self.provider_name)
            resp = session.get(mod_url, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title else "MMCCW Mod"
                title = re.sub(r"\s*-\s*Maxis Match CC World.*", "", title)

                text = soup.get_text("\n", strip=True)
                reqs = extract_mmccworld_requirements(resp.text)
                dl_links = extract_download_links(resp.text)

                m = re.search(r"/post/(\d+)", mod_url)
                post_id = m.group(1) if m else str(abs(hash(mod_url)) % 10000000)

                return {
                    "remote_id": f"mmccworld_{post_id}",
                    "title": title,
                    "description": text[:500],
                    "page_url": mod_url,
                    "author": "Maxis Match Creator",
                    "category": "clothing",
                    "source": self.provider_name,
                    "requirements": reqs,
                    "download_urls": dl_links,
                }
        except Exception as e:
            logger.debug(f"Erreur get_mod_details MMCCWorld pour {mod_url}: {e}")

        return {}

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        return "PUBLIC"

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Télécharge un fichier de mod en routant vers SimFileShare ou direct."""
        cb: Optional[Callable[[int, int], None]] = None
        if progress_callback:
            def _adapted_cb(downloaded: int, total: int):
                progress_callback(int((downloaded / total) * 100) if total > 0 else 0, str(downloaded), str(total))
            cb = _adapted_cb

        return download_mmccworld_file(
            file_info=download_url,
            dest_path=Path(dest_path),
            progress_callback=cb,
        )

    # --- Gestion des Retours & Commentaires ---

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mmccw_get_creator_info(page_url, session=session, base_url=self.base_url)

    def check_user_already_commented(
        self, page_url: str, required_keywords: List[str]
    ) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mmccw_check_commented(
            page_url,
            required_keywords,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )

    def post_mod_comment(
        self, page_url: str, message: str
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        ok, msg, _ = _mmccw_post_comment(
            page_url,
            message,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )
        return ok, msg

    def delete_mod_comment(
        self, page_url: str, required_keywords: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        return _mmccw_delete_comment(
            "0",
            page_url,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )
