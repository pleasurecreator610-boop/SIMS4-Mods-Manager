"""
TheSimsResourceProvider: Provider plugin for scraping The Sims Resource (TSR) Sims 4 catalog
(https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/),
extracting embedded `data-item` JSON metadata, required meshes/dependencies (`RequiredItems`,
`requiredDownloadIds`, `requiredDownloadExternalLinks`), and downloading `.package`/`.zip` archives
via TSR's AJAX ticket flow (`/ajax.php?c=downloads&a=initDownload` -> `/ajax.php?c=downloads&a=getdownloadurl`).
"""

import json
import re
import time
import urllib.parse
from datetime import datetime
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


TSR_KNOWN_CROSS_DEPENDENCIES: List[Tuple[str, Dict[str, str]]] = [
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
        "sims 4 community library",
        {
            "source": "nsfwmods",
            "remote_id": "742",
            "title": "Sims 4 Community Library",
            "url": "https://nsfwmods.com/files/file/742-sims-4-community-library/",
        },
    ),
]


def _parse_tsr_timestamp(raw_val: Any) -> Optional[datetime]:
    """Converts a TSR UNIX timestamp or date string into a naive datetime."""
    if not raw_val:
        return None
    val_str = str(raw_val).strip()
    if not val_str or val_str == "0":
        return None
    if val_str.isdigit():
        try:
            ts = int(val_str)
            if ts > 100000000:
                return datetime.fromtimestamp(ts)
        except Exception:
            pass
    try:
        return date_parser.parse(val_str).replace(tzinfo=None)
    except Exception:
        return None


def parse_tsr_browse_html(
    soup_or_html: Any,
    category: Any = None,
    base_url: str = "https://www.thesimsresource.com",
    page: int = 1,
    category_name: Optional[str] = None,
    source: str = "thesimsresource",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Parses a The Sims Resource browse HTML page (`div.item-wrapper[data-item]` and `.item-link` fallback)
    and returns `(mods_list, detected_pages)`.
    """
    soup = (
        BeautifulSoup(soup_or_html, "html.parser")
        if isinstance(soup_or_html, str)
        else soup_or_html
    )
    cat_dict: Dict[str, Any] = (
        category
        if isinstance(category, dict)
        else {"name": category_name or (str(category) if category else "Mods (TSR)")}
    )

    detected_pages: Optional[int] = None
    if page == 1:
        page_nums: List[int] = []
        for a in soup.select("a[href*='/page/']"):
            href = a.get("href", "")
            m_cnt = re.search(r"/cnt/(\d+)", href)
            if m_cnt:
                total_items = int(m_cnt.group(1))
                page_nums.append(max(1, (total_items + 19) // 20))
            m_pg = re.search(r"/page/(\d+)", href)
            if m_pg:
                page_nums.append(int(m_pg.group(1)))
        if page_nums:
            detected_pages = min(max(page_nums), 50)

    results: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for wrapper in soup.select("div.item-wrapper[data-item]"):
        raw_json = wrapper.get("data-item", "")
        item_data: Dict[str, Any] = {}
        if raw_json:
            try:
                item_data = json.loads(raw_json)
            except Exception:
                item_data = {}

        link_el = wrapper.select_one("a.item-link[href]")
        raw_href = link_el["href"] if link_el else ""

        remote_id = str(item_data.get("ID") or item_data.get("ItemID") or "").strip()
        if not remote_id and raw_href:
            m_id = re.search(r"/id/(\d+)", raw_href)
            if m_id:
                remote_id = m_id.group(1)

        if not remote_id or remote_id in seen_ids:
            continue
        seen_ids.add(remote_id)

        title = str(item_data.get("title") or "").strip()
        if not title and link_el:
            title = link_el.get_text(strip=True)
        if not title:
            title = f"TSR Item #{remote_id}"

        author = str(item_data.get("creator") or item_data.get("creatorName") or "Unknown").strip()
        page_url = (
            urllib.parse.urljoin(base_url, raw_href)
            if raw_href
            else f"{base_url}/downloads/details/id/{remote_id}"
        )

        # Thumbnail resolution
        thumbnail_url = ""
        img_div = wrapper.select_one(".item-image[style]")
        if img_div and img_div.get("style"):
            m_bg = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", img_div["style"])
            if m_bg:
                thumbnail_url = urllib.parse.urljoin(base_url, m_bg.group(1))
        if not thumbnail_url and item_data.get("featuredImage"):
            fi = str(item_data["featuredImage"])
            thumbnail_url = fi if fi.startswith("http") else urllib.parse.urljoin(base_url, f"/scaled/{fi}")

        updated_date = (
            _parse_tsr_timestamp(item_data.get("lastUpdated"))
            or _parse_tsr_timestamp(item_data.get("publishDate"))
            or _parse_tsr_timestamp(item_data.get("submittedDate"))
        )
        published_date = (
            _parse_tsr_timestamp(item_data.get("publishDate"))
            or updated_date
        )

        tags: List[str] = []
        kw_raw = item_data.get("keywordsArr") or item_data.get("keywords")
        if isinstance(kw_raw, list):
            tags.extend(str(k).strip() for k in kw_raw if str(k).strip())
        elif isinstance(kw_raw, str) and kw_raw.strip():
            tags.extend(k.strip() for k in kw_raw.split(",") if k.strip())
        cat_label = cat_dict.get("name", "Mods (TSR)")
        if cat_label and cat_label not in tags:
            tags.append(cat_label)

        # Extract embedded requirements if present in data-item (RequiredItems first for rich titles)
        req_mods: List[Dict[str, Any]] = []
        req_items = item_data.get("RequiredItems") or item_data.get("requiredDownloads") or []
        if isinstance(req_items, list):
            for ri in req_items:
                if isinstance(ri, dict):
                    r_id = str(ri.get("ID") or ri.get("id") or ri.get("itemId") or "").strip()
                    r_title = str(ri.get("title") or ri.get("name") or f"TSR Required Mesh #{r_id}").strip()
                    if r_id and r_id != remote_id and not any(x["remote_id"] == r_id for x in req_mods):
                        req_mods.append(
                            {
                                "source": source,
                                "remote_id": r_id,
                                "title": r_title,
                                "url": f"{base_url}/downloads/details/id/{r_id}",
                            }
                        )

        req_ids = item_data.get("requiredDownloadIds") or []
        if isinstance(req_ids, list):
            for rid in req_ids:
                rid_str = str(rid).strip()
                if (
                    rid_str
                    and rid_str.isdigit()
                    and rid_str != remote_id
                    and not any(x["remote_id"] == rid_str for x in req_mods)
                ):
                    req_mods.append(
                        {
                            "source": source,
                            "remote_id": rid_str,
                            "title": f"TSR Required Mesh #{rid_str}",
                            "url": f"{base_url}/downloads/details/id/{rid_str}",
                        }
                    )

        revision = str(item_data.get("revision") or "1").strip()
        ver_str = f"v{revision}" if revision else ""
        req_text = "\n".join(m["title"] for m in req_mods) if req_mods else None
        entry: Dict[str, Any] = {
            "source": source,
            "remote_id": remote_id,
            "title": title,
            "author": author,
            "category": cat_label,
            "tags": tags[:10],
            "page_url": page_url,
            "thumbnail_url": thumbnail_url,
            "updated_date": updated_date,
            "published_date": published_date,
            "version": ver_str,
            "version_str": ver_str,
            "patreon_status": "NONE",
            "patreon_tier": "",
            "requirements_text": req_text,
            "requirements_status": "FOUND" if req_mods else "NONE",
            "requirements_mods": req_mods,
        }
        results.append(entry)

    return results, detected_pages


@ProviderRegistry.register_provider("thesimsresource")
class TheSimsResourceProvider(BaseSourceProvider):
    """
    Provider for scraping The Sims Resource (TSR) Sims 4 catalog across 12 main categories,
    extracting required meshes/dependencies, and downloading archives via TSR's ticket API.
    """

    provider_name = "thesimsresource"
    display_name = "The Sims Resource"
    base_url = "https://www.thesimsresource.com"
    sims4_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    sims4_browse_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    category_url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
    login_url = "https://www.thesimsresource.com/account/login"

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
            "default_pages": 3,
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Mods (TSR)"

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        """Met à jour le nombre de pages détectées pour une catégorie TSR."""
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
        """Retourne le nombre total de pages sur l'ensemble des 12 catégories TSR."""
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
            return f"{clean}/"
        if "/page/" in clean:
            return re.sub(r"/page/\d+", f"/page/{page}", clean) + "/"
        return f"{clean}/page/{page}/"

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Scrape une page de catégorie The Sims Resource Sims 4."""
        url = self._build_paginated_url(category["url"], page)
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping TSR [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"TSR request returned status {resp.status_code} for {url}")
                return results, detected_pages

            soup = BeautifulSoup(resp.text, "html.parser")
            results, detected_pages = parse_tsr_browse_html(
                soup,
                category=category,
                base_url=self.base_url,
                page=page,
                source=self.provider_name,
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
        """Scrape une page globale du catalogue TSR."""
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    @staticmethod
    def _extract_item_id(url_or_id: str, soup: Optional[BeautifulSoup] = None, html_text: str = "") -> Optional[str]:
        """Extrait l'identifiant numérique d'un mod TSR depuis l'URL ou le HTML."""
        clean = str(url_or_id).strip()
        if clean.isdigit():
            return clean
        for pattern in [
            r"/id/(\d+)",
            r"/itemId/(\d+)",
            r"[?&]itemid=(\d+)",
            r"/downloads/(\d{5,10})(?:[/?#]|$)",
        ]:
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                return m.group(1)

        if soup:
            dl_btn = soup.select_one("[itemid], [data-itemid], [data-item-id]")
            if dl_btn:
                val = dl_btn.get("itemid") or dl_btn.get("data-itemid") or dl_btn.get("data-item-id")
                if val and str(val).strip().isdigit():
                    return str(val).strip()

        if html_text:
            m_raw = re.search(r'itemid="(\d{5,10})"', html_text)
            if m_raw:
                return m_raw.group(1)
        return None

    def extract_requirements(
        self,
        soup: BeautifulSoup,
        own_id: str = "",
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """
        Extrait les dépendances et meshes requis d'une page de mod TSR
        (section Required Items, attributs JSON `RequiredItems`/`requiredDownloadIds` et mentions connues).
        """
        req_mods: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        seen_rids: set[str] = set()

        def _add_req(dep_dict: Dict[str, str]) -> None:
            key = dep_dict["title"].strip().lower()
            rid = dep_dict.get("remote_id", "").strip().lower()
            if key and key not in seen_keys and (not rid or rid not in seen_rids):
                seen_keys.add(key)
                if rid:
                    seen_rids.add(rid)
                req_mods.append(dep_dict)

        # 1. Explicit required items block in TSR detail page
        for req_container in soup.select(".required-items, #required-items, .required-downloads, .item-required"):
            for a in req_container.find_all("a", href=True):
                href = a["href"]
                m_id = re.search(r"/id/(\d+)|/downloads/(\d+)", href)
                if m_id:
                    rid = m_id.group(1) or m_id.group(2)
                    if rid and rid != own_id:
                        t_txt = a.get_text(strip=True) or f"TSR Required Mesh #{rid}"
                        _add_req(
                            {
                                "source": self.provider_name,
                                "remote_id": rid,
                                "title": t_txt,
                                "url": urllib.parse.urljoin(self.base_url, href),
                            }
                        )

        # 2. Check description links & known cross-platform dependencies
        desc_el = soup.select_one(".item-description, #item-description, .description, article")
        if desc_el:
            desc_text_lower = desc_el.get_text(" ", strip=True).lower()
            for a in desc_el.find_all("a", href=True):
                href = a["href"]
                m_tsr = re.search(
                    r"thesimsresource\.com/downloads/details/(?:[^\"']*?/)?id/(\d+)|^/downloads/details/(?:[^\"']*?/)?id/(\d+)",
                    href,
                )
                if m_tsr:
                    rid = m_tsr.group(1) or m_tsr.group(2)
                    if rid and rid != own_id:
                        t_txt = a.get_text(strip=True)
                        if not t_txt or t_txt.lower() in {"here", "link", "mesh", "download", "tsr"}:
                            m_title_slug = re.search(r"/title/([^/]+)/", href)
                            t_txt = (
                                m_title_slug.group(1).replace("-", " ").title()
                                if m_title_slug
                                else f"TSR Required Mesh #{rid}"
                            )
                        _add_req(
                            {
                                "source": self.provider_name,
                                "remote_id": rid,
                                "title": t_txt,
                                "url": urllib.parse.urljoin(self.base_url, href),
                            }
                        )

            for kw, dep_info in TSR_KNOWN_CROSS_DEPENDENCIES:
                if kw in desc_text_lower:
                    _add_req(dict(dep_info))

        if not req_mods:
            return None, "NONE", []

        req_text = "\n".join(m["title"] for m in req_mods)
        return req_text, "FOUND", req_mods

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """Extrait les détails complets, captures, dépendances et URL d'initialisation de téléchargement d'un mod TSR."""
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

            desc_el = soup.select_one(".item-description, #item-description, .description")
            if desc_el:
                clean_body_html, body_imgs = sanitize_description_html(desc_el, self.base_url)
                details["description"] = clean_body_html
                details["screenshots"] = body_imgs

            req_text, req_status, req_mods = self.extract_requirements(soup, own_id=item_id or "")
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_el = soup.select_one(".item-revision, .revision")
            if v_el:
                details["version_str"] = v_el.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error extracting TSR details for {mod_url}: {e}", exc_info=True)

        return details

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les métadonnées d'un mod TSR par son ID numérique."""
        session = SessionManager.get_http_session(self.provider_name)
        target_url = (
            remote_id
            if str(remote_id).startswith("http")
            else f"{self.base_url}/downloads/details/id/{str(remote_id).strip('/')}"
        )
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_el = soup.select_one("h1, .item-title")
                author_el = soup.select_one("a.creator-name, .creator-name, .big-creator-name")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_el.get_text(strip=True) if title_el else f"TSR #{remote_id}",
                    "author": author_el.get_text(strip=True) if author_el else "Unknown",
                    "page_url": target_url,
                    "version_str": "",
                }
        except Exception as e:
            logger.debug(f"TSR fetch_mod_by_id failed for {remote_id}: {e}")
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
        """
        Télécharge le fichier `.package` ou `.zip` d'un mod TSR via le flux AJAX :
        1. `/ajax.php?c=downloads&a=initDownload&itemid={id}&setItems=&format=zip` -> obtient `ticket` et `url`.
        2. Visite `{url}` pour initialiser le cookie `tsrdlsession`.
        3. Interroge `/ajax.php?c=downloads&a=getdownloadurl&ajax=1&itemid={id}&mid=0&lk=0&ticket={ticket}`
           jusqu'à obtenir l'URL signée S3 (`downloads.thesimsresource.com/verify/downloads/...`).
        4. Télécharge le binaire en streaming.
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
                progress_callback(5, "Connexion à The Sims Resource...", "Initialisation du ticket de téléchargement...")

            final_dl_url = ""
            if "downloads.thesimsresource.com/verify/" in target_url:
                final_dl_url = target_url
            else:
                item_id = self._extract_item_id(target_url)
                if not item_id:
                    page_resp = session.get(target_url, timeout=15)
                    if page_resp.status_code == 200:
                        soup = BeautifulSoup(page_resp.text, "html.parser")
                        item_id = self._extract_item_id(target_url, soup, page_resp.text)
                if not item_id:
                    return False, "Impossible d'extraire l'identifiant du mod TSR."

                init_url = (
                    f"{self.base_url}/ajax.php?c=downloads&a=initDownload&itemid={item_id}&setItems=&format=zip"
                )
                init_resp = session.get(init_url, timeout=15)
                if init_resp.status_code != 200:
                    return False, f"Échec d'initialisation du ticket TSR (HTTP {init_resp.status_code})"

                init_json = init_resp.json()
                ticket = init_json.get("ticket", "")
                wait_rel_url = init_json.get("url", f"/downloads/download/itemId/{item_id}/ticket/{ticket}")
                if not ticket:
                    return False, "Ticket de téléchargement TSR introuvable dans la réponse."

                wait_full_url = urllib.parse.urljoin(self.base_url, wait_rel_url)
                session.get(wait_full_url, timeout=15)

                get_dl_endpoint = (
                    f"{self.base_url}/ajax.php?c=downloads&a=getdownloadurl"
                    f"&ajax=1&itemid={item_id}&mid=0&lk=0&ticket={ticket}"
                )

                for attempt in range(max_ticket_polls):
                    if ShutdownManager.is_shutting_down():
                        return False, "Arrêt de l'application en cours."
                    dl_info_resp = session.get(get_dl_endpoint, timeout=15)
                    if dl_info_resp.status_code == 200:
                        try:
                            dl_json = dl_info_resp.json()
                            if dl_json.get("url") and not dl_json.get("error"):
                                final_dl_url = str(dl_json["url"])
                                break
                        except Exception:
                            pass
                    if attempt < max_ticket_polls - 1 and ticket_poll_interval > 0:
                        if progress_callback:
                            pct = min(20, 6 + (attempt + 1) * 2)
                            progress_callback(
                                pct,
                                "Validation du ticket The Sims Resource...",
                                f"Tentative {attempt + 1}/{max_ticket_polls}",
                            )
                        time.sleep(ticket_poll_interval)

                if not final_dl_url:
                    return False, "Impossible d'obtenir l'URL finale de téléchargement TSR après expiration du ticket."

            resp = session.get(final_dl_url, stream=True, timeout=180, allow_redirects=True)
            if resp.status_code != 200:
                return False, f"Échec du téléchargement binaire TSR (Code HTTP {resp.status_code})"

            content_type = resp.headers.get("Content-Type", "").lower()
            content_disp = resp.headers.get("Content-Disposition", "")
            content_disp_lower = content_disp.lower()
            if "html" not in content_type or "attachment" in content_disp_lower or "filename=" in content_disp_lower:
                m_fname = re.search(r'filename="?([^";\r\n]+)"?', content_disp, re.IGNORECASE)
                if m_fname:
                    raw_fname = Path(m_fname.group(1).strip()).name
                    if raw_fname and Path(raw_fname).suffix.lower() in {".package", ".ts4script", ".zip", ".rar", ".7z"}:
                        target_path = target_path.parent / raw_fname
                return stream_download(resp, target_path, progress_callback, "Téléchargement TSR")

            return False, "La réponse TSR n'est pas une archive ou un package binaire valide."
        except Exception as e:
            logger.error(f"Exception lors du téléchargement TSR ({target_url}): {e}", exc_info=True)
            return False, str(e)

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Tous les mods TSR sont téléchargeables publiquement via le système de ticket."""
        return "PUBLIC"

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extrait les informations du créateur (ID/slug, nom, URL du profil) depuis une page TSR."""
        if not page_url:
            return None, None, None
        session = SessionManager.get_http_session(self.provider_name)
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                return None, None, None
            soup = BeautifulSoup(resp.text, "html.parser")
            author_el = soup.select_one(
                "a.creator-name, .big-creator-name a, a[href*='/artists/'], a[href*='/members/']"
            )
            if author_el:
                name = author_el.get_text(strip=True)
                href = author_el.get("href", "")
                profile_url = urllib.parse.urljoin(self.base_url, href) if href else None
                creator_id = href.rstrip("/").split("/")[-1] if href else name
                return creator_id, name, profile_url
        except Exception as e:
            logger.debug(f"TSR get_creator_info failed for {page_url}: {e}")
        return None, None, None

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Vérifie si un commentaire mentionnant les dépendances ou posté par l'utilisateur
        est déjà présent dans la section `.comments-area .comment-list` sur The Sims Resource.
        """
        if not page_url:
            return False, None
        session = SessionManager.get_http_session(self.provider_name)
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                return False, None
            soup = BeautifulSoup(resp.text, "html.parser")
            acc = SessionManager.get_saved_session(self.provider_name)
            current_user = (acc.user_display_name or "").strip().lower() if acc else ""
            kw_lower = [k.strip().lower() for k in required_keywords if k and k.strip()]

            for comment_div in soup.select(".comments-area .comment-list .comment, #details-comments .comment"):
                msg_el = comment_div.select_one(".comment-message") or comment_div
                txt_lower = msg_el.get_text(" ", strip=True).lower()
                author_el = msg_el.select_one("strong a, a[href*='/members/'], a[href*='/artists/']")
                author_name = author_el.get_text(strip=True).lower() if author_el else ""
                date_el = msg_el.select_one(".date-added")
                date_str = date_el.get_text(" ", strip=True).lstrip("∙ ").strip() if date_el else "Déjà commenté"

                if current_user and author_name and current_user in author_name:
                    if not kw_lower or any(k in txt_lower for k in kw_lower):
                        return True, date_str
                elif kw_lower and all(k in txt_lower for k in kw_lower):
                    return True, date_str
        except Exception as e:
            logger.debug(f"TSR check_user_already_commented failed for {page_url}: {e}")
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """
        Publie un commentaire sur la page d'un mod The Sims Resource via l'endpoint AJAX officiel :
        `POST /feedback/ax-add-comment/` avec `{item: itemId, type: 'ITEM', body: message, ref: pathname}`.
        """
        if not page_url or not message.strip():
            return False, "URL ou message de commentaire manquant."
        if not SessionManager.is_session_ready(self.provider_name):
            return (
                False,
                "Aucun compte The Sims Resource connecté. Connectez-vous dans l'onglet Comptes ou ouvrez dans le navigateur.",
            )

        session = SessionManager.get_http_session(self.provider_name)
        try:
            item_id = self._extract_item_id(page_url)
            parsed_url = urllib.parse.urlparse(page_url)
            ref_path = parsed_url.path or f"/downloads/details/id/{item_id}"

            if not item_id:
                page_resp = session.get(page_url, timeout=15)
                if page_resp.status_code == 200:
                    soup = BeautifulSoup(page_resp.text, "html.parser")
                    item_id = self._extract_item_id(page_url, soup, page_resp.text)
            if not item_id:
                return False, "Impossible d'extraire l'identifiant du mod TSR pour publier le commentaire."

            endpoint = f"{self.base_url}/feedback/ax-add-comment/"
            resp = session.post(
                endpoint,
                data={
                    "item": str(item_id),
                    "type": "ITEM",
                    "body": message.strip(),
                    "ref": ref_path,
                },
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": page_url,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                resp_txt = (resp.text or "").strip().lower()
                if "login" in resp_txt or "not logged in" in resp_txt or "error" in resp_txt:
                    return (
                        False,
                        f"Session TSR non authentifiée pour commenter ({resp.text.strip()[:120]}).",
                    )
                return True, "Commentaire publié avec succès sur The Sims Resource !"
            return False, f"Échec de publication du commentaire sur TSR (Code HTTP {resp.status_code})."
        except Exception as e:
            logger.error(f"Error posting TSR comment on {page_url}: {e}")
            return False, str(e)

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Supprime un commentaire publié par l'utilisateur sur The Sims Resource via `/feedback/ax-remove-comment/`."""
        if not page_url:
            return False, "URL de la page manquante."
        session = SessionManager.get_http_session(self.provider_name)
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                return False, f"Impossible de charger la page TSR (HTTP {resp.status_code})."
            soup = BeautifulSoup(resp.text, "html.parser")
            parsed_url = urllib.parse.urlparse(page_url)
            ref_path = parsed_url.path or "/"

            for a in soup.select(".comments-area a[href*='removeComment']"):
                m_cid = re.search(r"removeComment\((\d+)\)", a.get("href", ""))
                if m_cid:
                    cid = m_cid.group(1)
                    del_resp = session.post(
                        f"{self.base_url}/feedback/ax-remove-comment/",
                        data={"id": cid, "ref": ref_path},
                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
                        timeout=15,
                    )
                    if del_resp.status_code == 200:
                        return True, "Commentaire supprimé avec succès sur The Sims Resource."
            return False, "Aucun commentaire supprimable trouvé sur cette page TSR."
        except Exception as e:
            return False, str(e)
