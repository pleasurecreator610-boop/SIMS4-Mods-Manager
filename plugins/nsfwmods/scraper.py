"""
NSFWModsProvider: Provider plugin for scraping NSFWMods The Sims 4 files category (287)
and its 10 Sims subcategories, extracting mod details/requirements, downloading files,
and interacting with the IPS4 forum/comments system.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from plugins.loverslab.downloader import (
    download_loverslab_file,
    extract_download_candidates as _ext_dl_candidates,
)
from plugins.loverslab.forum_service import LoversLabForumService
from plugins.loverslab.page_parser import parse_category_page_html
from plugins.loverslab.parsers import extract_gallery_screenshots, sanitize_description_html
from plugins.loverslab.requirements_extractor import (
    KNOWN_MOD_ALIASES,
    extract_loverslab_requirements,
)
from plugins.patreon import PatreonProvider
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger


@ProviderRegistry.register_provider("nsfwmods")
class NSFWModsProvider(BaseSourceProvider):
    """
    Provider for scraping NSFWMods Sims Mods category (287) and all 10 Sims subcategories,
    extracting attachments, requirements, and handling IPS4 downloads and forum interactions.
    """

    provider_name = "nsfwmods"
    display_name = "NSFWMods"
    base_url = "https://nsfwmods.com"
    category_url = "https://nsfwmods.com/files/category/287-sims-mods/"
    login_url = "https://nsfwmods.com/login/"

    CATEGORIES = [
        {
            "id": "nsfwmods_287",
            "name": "Sims Mods (NSFWMods)",
            "slug": "287-sims-mods",
            "url": "https://nsfwmods.com/files/category/287-sims-mods/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_364",
            "name": "Adult (NSFWMods)",
            "slug": "364-adult",
            "url": "https://nsfwmods.com/files/category/364-adult/",
            "default_pages": 4,
        },
        {
            "id": "nsfwmods_289",
            "name": "Clothing (NSFWMods)",
            "slug": "289-clothing",
            "url": "https://nsfwmods.com/files/category/289-clothing/",
            "default_pages": 5,
        },
        {
            "id": "nsfwmods_296",
            "name": "Shoes (NSFWMods)",
            "slug": "296-shoes",
            "url": "https://nsfwmods.com/files/category/296-shoes/",
            "default_pages": 7,
        },
        {
            "id": "nsfwmods_292",
            "name": "Accessories (NSFWMods)",
            "slug": "292-accessories",
            "url": "https://nsfwmods.com/files/category/292-accessories/",
            "default_pages": 3,
        },
        {
            "id": "nsfwmods_288",
            "name": "Body Types (NSFWMods)",
            "slug": "288-body-types",
            "url": "https://nsfwmods.com/files/category/288-body-types/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_290",
            "name": "Hair (NSFWMods)",
            "slug": "290-hair",
            "url": "https://nsfwmods.com/files/category/290-hair/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_294",
            "name": "Skintones (NSFWMods)",
            "slug": "294-skintones",
            "url": "https://nsfwmods.com/files/category/294-skintones/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_295",
            "name": "Facial Hair (NSFWMods)",
            "slug": "295-facial-hair",
            "url": "https://nsfwmods.com/files/category/295-facial-hair/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_291",
            "name": "Makeup (NSFWMods)",
            "slug": "291-makeup",
            "url": "https://nsfwmods.com/files/category/291-makeup/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_293",
            "name": "Eyes (NSFWMods)",
            "slug": "293-eyes",
            "url": "https://nsfwmods.com/files/category/293-eyes/",
            "default_pages": 1,
        },
    ]

    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = KNOWN_MOD_ALIASES

    def __init__(self) -> None:
        super().__init__()
        self.patreon_provider = PatreonProvider()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "Sims Mods (NSFWMods)"

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        """Met à jour le nombre de pages détectées pour une catégorie NSFWMods."""
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
        """Retourne le nombre total de pages sur l'ensemble des catégories NSFWMods."""
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
        """Scrape une page d'une catégorie NSFWMods et retourne (mods, detected_pages)."""
        cat_url = category["url"].rstrip("/") + "/"
        url = cat_url if page == 1 else f"{cat_url}page/{page}/"
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping NSFWMods [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"NSFWMods request returned status {resp.status_code} for {url}")
                return results, detected_pages

            soup = BeautifulSoup(resp.text, "html.parser")
            results, detected_pages = parse_category_page_html(
                soup, category, self.base_url, page, source_name=self.provider_name
            )

            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            if results:

                def _inspect_item_target(entry: Dict[str, Any]) -> Dict[str, Any]:
                    p_url = entry["page_url"]
                    dl_chk = p_url.rstrip("/") + "/?do=download"
                    try:
                        item_session = SessionManager.get_http_session(self.provider_name)
                        r_chk = item_session.get(dl_chk, allow_redirects=False, timeout=6)
                        loc = r_chk.headers.get("Location", "")
                        if r_chk.status_code in [301, 302, 303, 307, 308]:
                            if "patreon.com" in loc.lower():
                                pat_info = self.patreon_provider.check_post_access(loc)
                                entry["patreon_status"] = pat_info.get("status", "PUBLIC")
                                entry["patreon_tier"] = pat_info.get("tier_str", "")
                                if "Patreon" not in entry["tags"]:
                                    entry["tags"].append("Patreon")
                            elif loc and "nsfwmods.com" not in loc.lower():
                                entry["patreon_status"] = "NONE"
                                ext_list = entry.setdefault("external_links", [])
                                if loc not in ext_list:
                                    ext_list.append(loc)
                            else:
                                entry["patreon_status"] = "NONE"
                        else:
                            entry["patreon_status"] = "NONE"
                    except Exception:
                        entry["patreon_status"] = "NONE"
                    return entry

                if ShutdownManager.is_shutting_down():
                    return results, detected_pages

                try:
                    with ThreadPoolExecutor(max_workers=min(len(results), 6)) as pool:
                        results = list(pool.map(_inspect_item_target, results))
                except RuntimeError as r_err:
                    if "interpreter shutdown" in str(r_err).lower() or ShutdownManager.is_shutting_down():
                        return results, detected_pages
                    raise

            logger.info(f"NSFWMods [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error while scraping NSFWMods category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """Scrape une page globale du catalogue NSFWMods."""
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """Extrait les détails complets, captures, dépendances et URLs de téléchargement d'un mod NSFWMods."""
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
            resp = session.get(mod_url, timeout=10)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            candidates = self.extract_download_candidates(soup, self.base_url)
            for cand in candidates:
                details["download_urls"].append(
                    {
                        "name": cand.get("title") or "Téléchargement NSFWMods (Direct)",
                        "url": cand["url"],
                        "size": 0,
                    }
                )

            direct_dl_url = f"{mod_url.rstrip('/')}/?do=download"
            if not details["download_urls"]:
                details["download_urls"].append(
                    {
                        "name": "Téléchargement NSFWMods (Direct)",
                        "url": direct_dl_url,
                        "size": 0,
                    }
                )

            gallery_screenshots: List[str] = extract_gallery_screenshots(soup, self.base_url)
            content_elem = soup.select_one(
                "article div.ipsType_richText, .cFileView_content div.ipsType_richText, [data-role='commentContent'], .ipsType_richText"
            ) or soup.select_one("article")

            if content_elem:
                for a in content_elem.find_all("a", href=True):
                    href = a["href"]
                    if "patreon.com" in href.lower():
                        if href not in details["external_links"]:
                            details["external_links"].append(href)
                    elif any(
                        d in href.lower()
                        for d in ["mega.nz", "mediafire.com", "drive.google.com", "simfileshare.net", "dropbox.com"]
                    ):
                        if href not in details["external_links"]:
                            details["external_links"].append(href)

                clean_body_html, body_imgs = sanitize_description_html(content_elem, self.base_url)
                unique_gallery = [
                    g
                    for g in gallery_screenshots
                    if not any(g.split("/")[-1].replace(".thumb.", ".") in b for b in body_imgs) and g not in body_imgs
                ]

                gallery_html = ""
                if unique_gallery:
                    gallery_cards = "".join(
                        f'<img src="{g_url}" style="max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block;" />'
                        for g_url in unique_gallery
                    )
                    gallery_html = f"""<div class="mod-gallery" style="margin-bottom: 20px; padding: 14px; background-color: #0d121f; border: 1px solid #1e293b; border-radius: 10px;"><div style="font-size: 13px; font-weight: 700; color: #60a5fa; margin-bottom: 12px; display: flex; align-items: center;">📸 Galerie &amp; Captures d'écran ({len(unique_gallery)}) :</div>{gallery_cards}</div>"""

                details["description"] = f"{gallery_html}{clean_body_html}"
                details["screenshots"] = unique_gallery if unique_gallery else gallery_screenshots
            else:
                details["screenshots"] = gallery_screenshots

            req_text, req_status, req_mods = self.extract_requirements(soup)
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_elem = soup.select_one(
                ".cFileInfo_version, [data-role='version'], h1.ipsType_pageTitle span.ipsType_light"
            )
            if v_elem:
                details["version_str"] = v_elem.get_text(strip=True)

        except Exception as e:
            err_str = str(e).lower()
            if "timed out" in err_str or "timeout" in err_str or "28" in err_str:
                logger.warning(
                    f"Timeout lors de l'extraction des détails pour {mod_url} (serveur NSFWMods indisponible ou lent)"
                )
            else:
                logger.error(f"Error extracting details for {mod_url}: {e}", exc_info=True)

        return details

    def extract_download_candidates(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, Any]]:
        """Extrait les candidats de téléchargement IPS4."""
        return _ext_dl_candidates(soup, base_url or self.base_url)

    def extract_requirements(self, soup: BeautifulSoup) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """Extrait et classifie les dépendances depuis le DOM du mod."""
        return extract_loverslab_requirements(soup, self.KNOWN_MOD_ALIASES)

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les métadonnées d'un mod NSFWMods par son ID distant."""
        session = SessionManager.get_http_session(self.provider_name)
        target_url = f"{self.base_url}/files/file/{remote_id}/"
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_elem = soup.select_one("h1.ipsType_pageTitle, .cFileView_title, h1")
                author_elem = soup.select_one(".ipsDataItem_author, a[data-ipshover]")
                v_elem = soup.select_one(".cFileInfo_version, [data-role='version']")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_elem.get_text(strip=True) if title_elem else f"Mod #{remote_id}",
                    "author": author_elem.get_text(strip=True) if author_elem else "Inconnu",
                    "page_url": target_url,
                    "version_str": v_elem.get_text(strip=True) if v_elem else "",
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
        """Télécharge un fichier de mod depuis NSFWMods en résolvant les jetons csrfKey et pages multi-fichiers."""
        target_url = download_url or kwargs.get("mod_url", "")
        target_path = dest_path or kwargs.get("dest_folder") or kwargs.get("dest_path")
        return download_loverslab_file(
            download_url=target_url,
            dest_path=target_path,
            patreon_provider=self.patreon_provider,
            base_url=self.base_url,
            progress_callback=progress_callback,
            provider_name=self.provider_name,
        )

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Vérifie le statut d'accès au mod."""
        external_links = mod_data.get("external_links", [])
        for link in external_links:
            if "patreon.com" in link.lower():
                return self.patreon_provider.check_post_access(link).get("status", "UNKNOWN")
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """Vérifie si l'utilisateur a déjà publié un commentaire sur la page du mod."""
        return LoversLabForumService.check_user_already_commented(
            page_url, required_keywords, provider_name=self.provider_name
        )

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """Publie un commentaire sur la page du mod ou le sujet de support associé."""
        return LoversLabForumService.post_mod_comment(
            page_url, message, provider_name=self.provider_name, base_url=self.base_url
        )

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Supprime un commentaire publié par l'utilisateur sur le forum NSFWMods."""
        return LoversLabForumService.delete_user_comment(
            page_url, required_keywords, provider_name=self.provider_name, base_url=self.base_url
        )

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Récupère les informations du créateur (ID, nom, URL du profil)."""
        return LoversLabForumService.get_creator_info(page_url, provider_name=self.provider_name)

    def check_user_already_sent_pm(
        self,
        creator_id: Optional[str] = None,
        creator_name: Optional[str] = None,
        mod_title: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """Vérifie si un message privé a déjà été envoyé au créateur."""
        return LoversLabForumService.check_user_already_sent_pm(
            creator_id, creator_name, mod_title, provider_name=self.provider_name, base_url=self.base_url
        )

    def send_private_message(
        self,
        creator_id: str,
        creator_name: str,
        subject: str,
        message: str,
    ) -> Tuple[bool, str]:
        """Envoie un message privé au créateur via la messagerie IPS4 NSFWMods."""
        return LoversLabForumService.send_private_message(
            creator_id, creator_name, subject, message, provider_name=self.provider_name, base_url=self.base_url
        )

