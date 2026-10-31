"""
Nexus Mods Provider & Scraper: Intégration Nexus Mods (nexusmods.com/thesims4) pour Sims 4 Mods Manager.
Exploite l'API GraphQL v2 souveraine et l'API v1 pour la synchronisation, le téléchargement et les retours.
"""

from __future__ import annotations

from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import httpx

from plugins.nexusmods.comments import (
    check_user_already_commented as _nexus_check_commented,
    delete_mod_comment as _nexus_delete_comment,
    get_creator_info as _nexus_get_creator_info,
    post_mod_comment as _nexus_post_comment,
)
from plugins.nexusmods.downloader import download_nexusmods_file
from plugins.nexusmods.parsers import (
    extract_nexusmods_requirements,
    parse_nexusmods_graphql_mods,
)
from src.core.dto import ModDetailsDTO
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger


@ProviderRegistry.register_provider("nexusmods")
class NexusModsProvider(BaseSourceProvider):
    """Fournisseur pour Nexus Mods (nexusmods.com/thesims4)."""

    base_url = "https://www.nexusmods.com"
    graphql_url = "https://api.nexusmods.com/v2/graphql"
    provider_name = "nexusmods"
    display_name = "Nexus Mods"
    login_url = "https://users.nexusmods.com/auth/sign_in?redirect_url=https%3A%2F%2Fwww.nexusmods.com%2Fthesims4"

    CATEGORIES = [
        {
            "id": "nexus_gameplay",
            "name": "Gameplay (Nexus)",
            "slug": "gameplay",
            "category_name": "Gameplay",
            "default_pages": 4,
        },
        {
            "id": "nexus_utilities",
            "name": "Utilities (Nexus)",
            "slug": "utilities",
            "category_name": "Utilities",
            "default_pages": 3,
        },
        {
            "id": "nexus_user_interface",
            "name": "User Interface (Nexus)",
            "slug": "user_interface",
            "category_name": "User Interface",
            "default_pages": 3,
        },
        {
            "id": "nexus_clothing",
            "name": "Clothing (Nexus)",
            "slug": "clothing",
            "category_name": "Clothing",
            "default_pages": 4,
        },
        {
            "id": "nexus_cas",
            "name": "Create a Sim (Nexus)",
            "slug": "cas",
            "category_name": "Create a Sim (CAS)",
            "default_pages": 4,
        },
        {
            "id": "nexus_build_mode",
            "name": "Build Mode (Nexus)",
            "slug": "build_mode",
            "category_name": "Build Mode",
            "default_pages": 3,
        },
        {
            "id": "nexus_buy_mode",
            "name": "Buy Mode (Nexus)",
            "slug": "buy_mode",
            "category_name": "Buy Mode",
            "default_pages": 3,
        },
        {
            "id": "nexus_decorations",
            "name": "Decorations (Nexus)",
            "slug": "decorations",
            "category_name": "Decorations",
            "default_pages": 3,
        },
        {
            "id": "nexus_careers",
            "name": "Careers & Traits (Nexus)",
            "slug": "careers",
            "category_name": "Careers",
            "default_pages": 3,
        },
        {
            "id": "nexus_miscellaneous",
            "name": "Miscellaneous (Nexus)",
            "slug": "miscellaneous",
            "category_name": "Miscellaneous",
            "default_pages": 2,
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
        """Scrape une page générale du catalogue Nexus Mods."""
        first_cat = self.CATEGORIES[0] if self.CATEGORIES else {"id": "nexus_gameplay", "name": "Gameplay"}
        return self.scrape_category(first_cat, page=page, page_size=limit)

    def scrape_category(
        self,
        category: Dict[str, Any],
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """Scrape une page de catégorie Nexus Mods via l'API GraphQL v2 souveraine."""
        if ShutdownManager.is_shutting_down():
            return []

        self._throttle(0.2)
        cat_name = category.get("category_name")
        offset = (page - 1) * page_size

        filter_clause = 'gameDomainName: { value: "thesims4" }'
        if cat_name:
            filter_clause += f', categoryName: {{ value: "{cat_name}" }}'

        query = f"""
        query GetSims4CategoryMods {{
          mods(
            filter: {{ {filter_clause} }},
            sort: [{{ endorsements: {{ direction: DESC }} }}],
            offset: {offset},
            count: {page_size}
          ) {{
            nodes {{
              modId
              name
              summary
              author
              downloads
              endorsements
              pictureUrl
              version
              category
              createdAt
              modRequirements {{
                nexusRequirements {{
                  nodes {{
                    modName
                    notes
                    url
                  }}
                }}
              }}
            }}
            totalCount
          }}
        }}
        """

        try:
            logger.info(f"Requête Nexus Mods GraphQL pour [{category.get('name')}] page {page}...")
            resp = httpx.post(
                self.graphql_url,
                json={"query": query},
                headers={"User-Agent": "SIMS4-Mods-Manager/0.5.0"},
                timeout=20.0,
            )
            if resp.status_code != 200:
                logger.warning(f"Erreur HTTP Nexus Mods GraphQL: {resp.status_code}")
                return []

            data = resp.json()
            nodes = data.get("data", {}).get("mods", {}).get("nodes", [])
            mods = parse_nexusmods_graphql_mods(nodes, category, source=self.provider_name)
            logger.info(f"Nexus Mods [{category.get('name')}] p.{page} récupération terminée: {len(mods)} mods.")
            return mods

        except Exception as e:
            logger.error(f"Erreur lors du scraping Nexus Mods [{category.get('name')}]: {e}")
            return []

    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """Récupère les détails complets d'un mod (fichiers, prérequis MOD vs COMMENT)."""
        m = re.search(r"(\d+)", str(mod_url))
        if not m:
            return {}
        mod_id = int(m.group(1))

        query = f"""
        query GetSims4ModComplete {{
          mod(gameId: 641, modId: {mod_id}) {{
            modId
            name
            summary
            description
            author
            version
            category
            pictureUrl
            downloads
            endorsements
            modRequirements {{
              nexusRequirements {{
                nodes {{
                  modName
                  notes
                  url
                }}
              }}
            }}
          }}
          modFiles(gameId: 641, modId: {mod_id}) {{
            fileId
            name
            version
            sizeInBytes
            description
            uri
          }}
        }}
        """

        try:
            resp = httpx.post(
                self.graphql_url,
                json={"query": query},
                headers={"User-Agent": "SIMS4-Mods-Manager/0.5.0"},
                timeout=20.0,
            )
            if resp.status_code != 200:
                return {}

            data = resp.json()
            mod_data = data.get("data", {}).get("mod")
            if not mod_data:
                return {}

            files_data = data.get("data", {}).get("modFiles") or []
            reqs = extract_nexusmods_requirements(mod_data)

            # Normalisation des fichiers
            download_files = []
            for f in files_data:
                fid = f.get("fileId")
                fname = f.get("name") or f"File #{fid}"
                download_files.append(
                    {
                        "file_id": fid,
                        "name": fname,
                        "version": f.get("version"),
                        "size_bytes": int(f.get("sizeInBytes") or 0),
                        "description": f.get("description", ""),
                    }
                )

            return {
                "remote_id": f"nexusmods_{mod_id}",
                "mod_id": mod_id,
                "title": mod_data.get("name"),
                "description": mod_data.get("description") or mod_data.get("summary", ""),
                "author": mod_data.get("author"),
                "version": mod_data.get("version"),
                "category": mod_data.get("category"),
                "page_url": f"https://www.nexusmods.com/thesims4/mods/{mod_id}",
                "thumbnail_url": mod_data.get("pictureUrl"),
                "downloads_count": mod_data.get("downloads", 0),
                "likes_count": mod_data.get("endorsements", 0),
                "requirements": reqs,
                "files": download_files,
                "download_urls": [f"https://www.nexusmods.com/thesims4/mods/{mod_id}?tab=files"],
                "source": self.provider_name,
            }

        except Exception as e:
            logger.error(f"Erreur get_mod_details Nexus Mods #{mod_id}: {e}")
            return {}

    def search(self, query_text: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Recherche des mods sur Nexus Mods."""
        offset = (page - 1) * page_size
        clean_q = query_text.replace('"', '\\"')

        query = f"""
        query SearchSims4Mods {{
          mods(
            filter: {{ gameDomainName: {{ value: "thesims4" }}, name: {{ value: "*{clean_q}*", op: WILDCARD }} }},
            sort: [{{ endorsements: {{ direction: DESC }} }}],
            offset: {offset},
            count: {page_size}
          ) {{
            nodes {{
              modId
              name
              summary
              author
              downloads
              endorsements
              pictureUrl
              version
              category
            }}
          }}
        }}
        """

        try:
            resp = httpx.post(
                self.graphql_url,
                json={"query": query},
                headers={"User-Agent": "SIMS4-Mods-Manager/0.5.0"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                nodes = resp.json().get("data", {}).get("mods", {}).get("nodes", [])
                dummy_cat = {"id": "nexus_miscellaneous", "name": "Search Results", "slug": "search"}
                return parse_nexusmods_graphql_mods(nodes, dummy_cat, source=self.provider_name)
        except Exception as e:
            logger.error(f"Erreur recherche Nexus Mods '{query_text}': {e}")

        return []

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Vérifie le statut d'accès d'un mod Nexus Mods."""
        if mod_data.get("adultContent"):
            saved_cookies = SessionManager.get_saved_cookies(self.provider_name)
            if not saved_cookies:
                return "LOCKED"
        return "PUBLIC"

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Télécharge un fichier de mod Nexus Mods vers dest_path."""
        cb: Optional[Callable[[int, int], None]] = None
        if progress_callback:

            def _adapted_cb(downloaded: int, total: int):
                progress_callback(int((downloaded / total) * 100) if total > 0 else 0, str(downloaded), str(total))

            cb = _adapted_cb

        return download_nexusmods_file(
            file_id=0,
            mod_id=0,
            target_path=Path(dest_path),
            download_url=download_url,
            progress_callback=cb,
        )

    # --- Gestion des Retours & Commentaires ---

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _nexus_get_creator_info(page_url, session=session, base_url=self.base_url)

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        session = SessionManager.get_http_session(self.provider_name)
        return _nexus_check_commented(
            page_url,
            required_keywords,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        ok, msg, _ = _nexus_post_comment(
            page_url,
            message,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )
        return ok, msg

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        session = SessionManager.get_http_session(self.provider_name)
        comment_id = "0"
        if required_keywords:
            has_c, cid = self.check_user_already_commented(page_url, required_keywords)
            if has_c and cid:
                comment_id = cid
        return _nexus_delete_comment(
            comment_id,
            page_url,
            session=session,
            base_url=self.base_url,
            provider_name=self.provider_name,
        )
