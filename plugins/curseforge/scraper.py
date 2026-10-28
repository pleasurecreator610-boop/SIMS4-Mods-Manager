"""
CurseForgeProvider: Provider plugin for scraping CurseForge The Sims 4 catalog (https://www.curseforge.com/sims4),
extracting project metadata, dependencies (/relations/dependencies + description), and downloading mod archives
via CurseForge's CDN (edge.forgecdn.net / /api/v1/mods/{projectId}/files/{fileId}/download).
"""

import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from plugins.loverslab.parsers import sanitize_description_html
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger
from src.utils.network import stream_download


CURSEFORGE_KNOWN_DEPENDENCIES: List[Tuple[str, Dict[str, str]]] = [
    (
        "xml injector",
        {
            "source": "curseforge",
            "remote_id": "xml-injector",
            "title": "XML Injector",
            "url": "https://www.curseforge.com/sims4/mods/xml-injector",
        },
    ),
    (
        "lot 51 core library",
        {
            "source": "curseforge",
            "remote_id": "lot-51-core-library",
            "title": "Lot 51 Core Library",
            "url": "https://www.curseforge.com/sims4/mods/lot-51-core-library",
        },
    ),
    (
        "lot51 core library",
        {
            "source": "curseforge",
            "remote_id": "lot-51-core-library",
            "title": "Lot 51 Core Library",
            "url": "https://www.curseforge.com/sims4/mods/lot-51-core-library",
        },
    ),
    (
        "smart core script",
        {
            "source": "curseforge",
            "remote_id": "smart-core-script",
            "title": "Smart Core Script",
            "url": "https://www.curseforge.com/sims4/mods/smart-core-script",
        },
    ),
    (
        "sims 4 community library",
        {
            "source": "nsfwmods",
            "remote_id": "742",
            "title": "Sims 4 Community Library",
            "url": "https://nsfwmods.com/files/file/742-sims-4-community-library/",
        },
    ),
]


def parse_curseforge_search_html(
    soup_or_html: Any,
    category: Any = None,
    base_url: str = "https://www.curseforge.com",
    page: int = 1,
    category_name: Optional[str] = None,
    source: str = "curseforge",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Parses a CurseForge Sims 4 search/category HTML page to extract `.project-card` entries
    and detected pagination count.
    """
    soup = (
        BeautifulSoup(soup_or_html, "html.parser")
        if isinstance(soup_or_html, str)
        else soup_or_html
    )
    cat_dict: Dict[str, Any] = (
        category
        if isinstance(category, dict)
        else {"name": category_name or (str(category) if category else "Mods (CurseForge)")}
    )
    detected_pages: Optional[int] = None
    if page == 1:
        page_nums: List[int] = []
        for a in soup.select("a[href*='page=']"):
            m = re.search(r"[?&]page=(\d+)", a.get("href", ""))
            if m:
                page_nums.append(int(m.group(1)))
        for btn in soup.select(".pagination-item, [class*='pagination'] button, [class*='pagination'] a"):
            txt = btn.get_text(strip=True)
            if txt.isdigit():
                page_nums.append(int(txt))
        if page_nums:
            detected_pages = min(max(page_nums), 50)

    cards = soup.select(".project-card")
    results: List[Dict[str, Any]] = []

    for card in cards:
        name_el = card.select_one("a.name, a.overlay-link")
        if not name_el or not name_el.get("href"):
            continue

        raw_href = name_el["href"].split("?")[0].rstrip("/")
        page_url = urllib.parse.urljoin(base_url, raw_href)
        slug = raw_href.split("/")[-1]
        remote_id = slug

        title = name_el.get_text(strip=True)
        if not title and name_el.get("title"):
            title = re.sub(r"^Go to\s+|\s+Project Page$", "", name_el["title"], flags=re.IGNORECASE).strip()
        if not title:
            title = slug.replace("-", " ").title()

        author_el = card.select_one("a.author-name, .author-name")
        author = author_el.get_text(strip=True) if author_el else "Unknown"

        thumb_el = card.select_one(".art img, img#row-image, img")
        thumbnail_url = ""
        if thumb_el:
            thumbnail_url = thumb_el.get("src") or thumb_el.get("data-src") or ""
            if thumbnail_url.startswith("/"):
                thumbnail_url = urllib.parse.urljoin(base_url, thumbnail_url)

        updated_date = None
        date_el = card.select_one("li.detail-updated .date-full, li.detail-updated")
        if date_el:
            try:
                updated_date = date_parser.parse(date_el.get_text(strip=True)).replace(tzinfo=None)
            except Exception:
                pass

        version_el = card.select_one("li.detail-game-version")
        version_str = version_el.get_text(strip=True) if version_el else ""

        tags: List[str] = []
        for cat_tag in card.select(".class-tag-overlay, li.detail-category a"):
            t_txt = cat_tag.get_text(strip=True)
            if t_txt and t_txt not in tags:
                tags.append(t_txt)
        if cat_dict.get("name") and cat_dict["name"] not in tags:
            tags.append(cat_dict["name"])

        dl_cta = card.select_one("a.download-cta[href*='/download/']")
        dl_file_id = ""
        if dl_cta and dl_cta.get("href"):
            m_fid = re.search(r"/download/(\d+)", dl_cta["href"])
            if m_fid:
                dl_file_id = m_fid.group(1)

        entry: Dict[str, Any] = {
            "source": source,
            "remote_id": remote_id,
            "title": title,
            "author": author,
            "category": cat_dict.get("name", "Mods (CurseForge)"),
            "tags": tags,
            "page_url": page_url,
            "thumbnail_url": thumbnail_url,
            "updated_date": updated_date,
            "published_date": updated_date,
            "version_str": version_str,
            "patreon_status": "NONE",
            "patreon_tier": "",
        }
        if dl_file_id:
            entry["latest_file_id"] = dl_file_id
        results.append(entry)

    return results, detected_pages


@ProviderRegistry.register_provider("curseforge")
class CurseForgeProvider(BaseSourceProvider):
    """
    Provider for scraping CurseForge The Sims 4 mods and CC categories,
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

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Mods - Gameplay (CurseForge)"

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        """Met à jour le nombre de pages détectées pour une catégorie CurseForge."""
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
        """Retourne le nombre total de pages sur l'ensemble des catégories CurseForge."""
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
        if "page=" in base_cat_url:
            return re.sub(r"([?&])page=\d+", rf"\g<1>page={page}", base_cat_url)
        sep = "&" if "?" in base_cat_url else "?"
        return f"{base_cat_url}{sep}page={page}"

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Scrape une page de catégorie CurseForge Sims 4."""
        url = self._build_paginated_url(category["url"], page)
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping CurseForge [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"CurseForge request returned status {resp.status_code} for {url}")
                return results, detected_pages

            soup = BeautifulSoup(resp.text, "html.parser")
            results, detected_pages = parse_curseforge_search_html(soup, category, self.base_url, page)

            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            logger.info(f"CurseForge [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error while scraping CurseForge category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def scrape_catalog(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """Scrape une page globale du catalogue CurseForge."""
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    @staticmethod
    def _extract_project_and_file_ids(soup: BeautifulSoup, html_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extrait le Project ID numérique et le dernier File ID depuis une page de mod CurseForge."""
        project_id: Optional[str] = None
        for dt in soup.find_all(["dt", "span", "div", "li", "section", "dl"]):
            txt = dt.get_text(" ", strip=True)
            m_pid = re.search(r"Project\s+ID\s*[:#]?\s*(\d{4,10})", txt, re.IGNORECASE)
            if m_pid:
                project_id = m_pid.group(1)
                break
        if not project_id:
            m_raw = re.search(r"Project\s+ID</dt>\s*<dd[^>]*>\s*(\d{4,10})\s*</dd>", html_text, re.IGNORECASE)
            if m_raw:
                project_id = m_raw.group(1)
        if not project_id:
            m_api = re.search(r"/api/v1/mods/(\d{4,10})", html_text)
            if m_api:
                project_id = m_api.group(1)
        if not project_id:
            m_json_pid = re.search(r'"project"\s*:\s*\{[^}]*"id"\s*:\s*(\d{4,10})', html_text)
            if m_json_pid:
                project_id = m_json_pid.group(1)

        file_id: Optional[str] = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m_f = re.search(r"/(?:files|download)/(\d{5,12})(?:[/?#]|$)", href)
            if m_f:
                file_id = m_f.group(1)
                break
        if not file_id:
            m_f_raw = re.search(r"/(?:files|download)/(\d{5,12})", html_text)
            if m_f_raw:
                file_id = m_f_raw.group(1)
        if not file_id:
            m_json_fid = re.search(r'"mainFile"\s*:\s*\{[^}]*"id"\s*:\s*(\d{5,12})', html_text)
            if m_json_fid:
                file_id = m_json_fid.group(1)

        return project_id, file_id

    def extract_requirements(
        self,
        soup: BeautifulSoup,
        mod_url: str = "",
        fetch_relations: bool = True,
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """
        Extrait les dépendances d'un mod CurseForge depuis :
        1. L'onglet `/relations/dependencies` (si disponible)
        2. Les liens et mentions de prérequis dans `.project-description`
        """
        req_mods: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()

        def _add_req(dep_dict: Dict[str, str]) -> None:
            key = dep_dict["title"].strip().lower()
            if key and key not in seen_keys:
                seen_keys.add(key)
                req_mods.append(dep_dict)

        # 1. Check /relations/dependencies if mod_url is provided
        if fetch_relations and mod_url and mod_url.startswith("http"):
            rel_url = f"{mod_url.rstrip('/')}/relations/dependencies"
            session = SessionManager.get_http_session(self.provider_name)
            try:
                rel_resp = session.get(rel_url, timeout=8)
                if rel_resp.status_code == 200:
                    rel_soup = BeautifulSoup(rel_resp.text, "html.parser")
                    for card in rel_soup.select(".project-card"):
                        name_el = card.select_one("a.name")
                        if name_el and name_el.get("href"):
                            href = name_el["href"].split("?")[0].rstrip("/")
                            slug = href.split("/")[-1]
                            t_name = name_el.get_text(strip=True) or slug.replace("-", " ").title()
                            _add_req(
                                {
                                    "source": "curseforge",
                                    "remote_id": slug,
                                    "title": t_name,
                                    "url": urllib.parse.urljoin(self.base_url, href),
                                }
                            )
            except Exception as e:
                logger.debug(f"CurseForge relations check skipped for {rel_url}: {e}")

        # 2. Check description links & known dependency mentions
        desc_el = soup.select_one(".project-description, #project-description, article")
        if desc_el:
            desc_text_lower = desc_el.get_text(" ", strip=True).lower()
            own_slug = mod_url.rstrip("/").split("/")[-1].lower() if mod_url else ""

            for a in desc_el.find_all("a", href=True):
                href = a["href"].split("?")[0].rstrip("/")
                m_cf = re.search(r"curseforge\.com/sims4/mods/([a-z0-9-]+)|^/sims4/mods/([a-z0-9-]+)$", href)
                if m_cf:
                    dep_slug = (m_cf.group(1) or m_cf.group(2) or "").strip()
                    if dep_slug and dep_slug.lower() != own_slug:
                        link_title = a.get_text(strip=True)
                        if not link_title or link_title.lower() in {"here", "link", "curseforge", "download"}:
                            link_title = dep_slug.replace("-", " ").title()
                        _add_req(
                            {
                                "source": "curseforge",
                                "remote_id": dep_slug,
                                "title": link_title,
                                "url": f"https://www.curseforge.com/sims4/mods/{dep_slug}",
                            }
                        )

            for kw, dep_info in CURSEFORGE_KNOWN_DEPENDENCIES:
                if dep_info["remote_id"].lower() == own_slug:
                    continue
                if kw in desc_text_lower:
                    _add_req(dict(dep_info))

        if not req_mods:
            return None, "NONE", []

        req_text = "\n".join(m["title"] for m in req_mods)
        return req_text, "FOUND", req_mods

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """Extrait les détails complets, captures, dépendances et URL de téléchargement directe d'un mod CurseForge."""
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

            desc_el = soup.select_one(".project-description, #project-description")
            if desc_el:
                clean_body_html, body_imgs = sanitize_description_html(desc_el, self.base_url)
                details["description"] = clean_body_html
                details["screenshots"] = body_imgs

            req_text, req_status, req_mods = self.extract_requirements(soup, mod_url=mod_url)
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_el = soup.select_one("li.detail-game-version, .game-version")
            if v_el:
                details["version_str"] = v_el.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error extracting CurseForge details for {mod_url}: {e}", exc_info=True)

        return details

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les métadonnées d'un mod CurseForge par son slug ou ID."""
        session = SessionManager.get_http_session(self.provider_name)
        target_url = (
            remote_id
            if remote_id.startswith("http")
            else f"{self.base_url}/sims4/mods/{remote_id.strip('/')}"
        )
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_el = soup.select_one("h1")
                author_el = soup.select_one("a.author-name, .author-name")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_el.get_text(strip=True) if title_el else str(remote_id),
                    "author": author_el.get_text(strip=True) if author_el else "Unknown",
                    "page_url": target_url,
                    "version_str": "",
                }
        except Exception as e:
            logger.debug(f"CurseForge fetch_mod_by_id failed for {remote_id}: {e}")
        return None

    def download_mod_file(
        self,
        download_url: Optional[str] = None,
        dest_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        """
        Télécharge l'archive d'un mod CurseForge en résolvant l'endpoint
        `/api/v1/mods/{projectId}/files/{fileId}/download` vers `edge.forgecdn.net`.
        """
        target_url = download_url or kwargs.get("mod_url", "")
        target_path = dest_path or kwargs.get("dest_folder") or kwargs.get("dest_path")
        if not target_url or not target_path:
            return False, "URL de téléchargement ou chemin de destination manquant."

        session = SessionManager.get_http_session(self.provider_name)
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if progress_callback:
                progress_callback(5, "Connexion à CurseForge...", "Résolution de l'archive sur ForgeCDN...")

            resolved_api_url = target_url
            if "/api/v1/mods/" not in target_url and "forgecdn.net" not in target_url:
                page_url = re.sub(r"/(?:download|install|files)(?:/\d+)?/?$", "", target_url.split("?")[0])
                m_fid = re.search(r"/(?:download|install|files)/(\d+)", target_url)
                explicit_fid = m_fid.group(1) if m_fid else None

                page_resp = session.get(page_url, timeout=20)
                if page_resp.status_code != 200:
                    return False, f"Impossible de charger la page CurseForge (HTTP {page_resp.status_code})"

                soup = BeautifulSoup(page_resp.text, "html.parser")
                project_id, detected_fid = self._extract_project_and_file_ids(soup, page_resp.text)
                file_id = explicit_fid or detected_fid
                if not project_id or not file_id:
                    return False, "Impossible d'extraire Project ID / File ID depuis la page CurseForge."
                resolved_api_url = f"{self.base_url}/api/v1/mods/{project_id}/files/{file_id}/download"

            resp = session.get(resolved_api_url, stream=True, timeout=180, allow_redirects=True)
            if resp.status_code != 200:
                return False, f"Échec du téléchargement CurseForge (Code HTTP {resp.status_code})"

            content_type = resp.headers.get("Content-Type", "").lower()
            content_disp = resp.headers.get("Content-Disposition", "").lower()
            if "html" not in content_type or "attachment" in content_disp or "filename=" in content_disp:
                if isinstance(getattr(resp, "content", None), (bytes, bytearray)) and len(resp.content) > 0:
                    target_path.write_bytes(resp.content)
                    if progress_callback:
                        progress_callback(100, "Téléchargement CurseForge terminé", target_path.name)
                    return True, str(target_path)
                return stream_download(resp, target_path, progress_callback, "Téléchargement CurseForge")

            return False, "La réponse CurseForge n'est pas une archive binaire valide."
        except Exception as e:
            logger.error(f"Exception lors du téléchargement CurseForge ({target_url}): {e}", exc_info=True)
            return False, str(e)

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Tous les mods indexés sur CurseForge sont publics."""
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """Vérifie si l'utilisateur a déjà commenté sur CurseForge."""
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """Publication de commentaire sur CurseForge."""
        return False, "La publication automatisée de commentaires n'est pas supportée sur CurseForge."
