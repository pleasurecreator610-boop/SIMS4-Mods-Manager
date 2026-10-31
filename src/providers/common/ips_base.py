"""Moteur IPS4 unifié (Invision Community) pour le scraping, le téléchargement et les interactions forum.

Partagé entre LoversLabProvider, NSFWModsProvider et toute plateforme basée sur IPS4.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from plugins.loverslab.comments import LoversLabForumService
from plugins.loverslab.downloader import (
    download_loverslab_file,
    extract_download_candidates as _ext_dl_candidates,
)
from plugins.loverslab.parsers import (
    extract_gallery_screenshots,
    parse_category_page_html,
    sanitize_description_html,
)
from plugins.loverslab.requirements_extractor import (
    KNOWN_MOD_ALIASES,
    extract_loverslab_requirements,
)
from plugins.patreon import PatreonProvider
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.utils.logger import logger

__all__ = [
    "BaseIPSForumProvider",
]


class BaseIPSForumProvider(BaseSourceProvider):
    """Classe de base unifiée pour les fournisseurs propulsés par Invision Community (IPS4)."""

    CATEGORIES: List[Dict[str, Any]] = []
    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = KNOWN_MOD_ALIASES
    check_direct_redirect_in_details: bool = True

    def __init__(self) -> None:
        super().__init__()
        self.patreon_provider = PatreonProvider()

    def _own_domain_host(self) -> str:
        parsed = urlparse(self.base_url)
        host = parsed.netloc.lower()
        return host[4:] if host.startswith("www.") else host

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Scrape une page d'une sous-catégorie IPS4 et inspecte en parallèle les cibles de téléchargement."""
        cat_url = category["url"].rstrip("/") + "/"
        url = cat_url if page == 1 else f"{cat_url}page/{page}/"
        session = SessionManager.get_http_session(self.provider_name)

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping {self.display_name} [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None
        own_host = self._own_domain_host()

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"{self.display_name} request returned status {resp.status_code} for {url}")
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
                            elif loc and own_host not in loc.lower():
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

            logger.info(f"{self.display_name} [{category['name']}] p.{page} scraping finished: {len(results)} mods.")
        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(
                f"Error while scraping {self.display_name} category {category['name']} page {page}: {e}",
                exc_info=True,
            )

        return results, detected_pages

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """Extrait les détails complets, captures, dépendances et URLs de téléchargement d'un mod IPS4."""
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
            direct_dl_url = f"{mod_url.rstrip('/')}/?do=download"
            is_direct_download = False
            patreon_redirect_url = None

            if not self.check_direct_redirect_in_details:
                candidates = self.extract_download_candidates(soup, self.base_url)
                for cand in candidates:
                    details["download_urls"].append(
                        {
                            "name": cand.get("title") or f"Téléchargement {self.display_name} (Direct)",
                            "url": cand["url"],
                            "size": 0,
                        }
                    )
                if not details["download_urls"]:
                    details["download_urls"].append(
                        {
                            "name": f"Téléchargement {self.display_name} (Direct)",
                            "url": direct_dl_url,
                            "size": 0,
                        }
                    )
            else:
                try:
                    try:
                        r_chk = session.head(direct_dl_url, allow_redirects=False, timeout=3.0)
                    except Exception:
                        r_chk = None

                    if (
                        r_chk is None
                        or not isinstance(getattr(r_chk, "status_code", None), int)
                        or r_chk.status_code == 405
                    ):
                        r_chk = session.get(direct_dl_url, allow_redirects=False, timeout=3.0)

                    if r_chk.status_code in [301, 302, 303, 307, 308]:
                        loc = r_chk.headers.get("Location", "")
                        if "patreon.com" in loc.lower():
                            patreon_redirect_url = loc
                        elif loc and loc not in details["external_links"]:
                            details["external_links"].append(loc)
                    elif r_chk.status_code in [200, 403]:
                        is_direct_download = True
                        details["download_urls"].append(
                            {
                                "name": f"Téléchargement {self.display_name} (Direct)",
                                "url": direct_dl_url,
                                "size": 0,
                            }
                        )
                except Exception as e:
                    logger.debug(f"Redirect check error for {direct_dl_url}: {e}")

                if patreon_redirect_url:
                    if patreon_redirect_url not in details["external_links"]:
                        details["external_links"].append(patreon_redirect_url)
                    pat_info = self.patreon_provider.check_post_access(patreon_redirect_url)
                    can_view = pat_info.get("can_view", False)
                    p_status = pat_info.get("status", "UNKNOWN")
                    tier_str = pat_info.get("tier_str", "")
                    is_patreon_member = SessionManager.is_member_authenticated("patreon")

                    if p_status == "LOCKED" or (not can_view and not is_patreon_member):
                        details["source"] = "patreon"
                        details["patreon_status"] = "LOCKED"
                        details["patreon_tier"] = tier_str or "Abonnement requis"
                        details["download_urls"] = []
                        if "Patreon" not in details.setdefault("tags", []):
                            details["tags"].append("Patreon")
                    else:
                        details["patreon_status"] = "PUBLIC"
                        dl_urls = pat_info.get("download_urls", [])
                        if dl_urls:
                            details["download_urls"].extend(dl_urls)
                        else:
                            details["download_urls"].append(
                                {
                                    "name": "Post Patreon (Téléchargement)",
                                    "url": patreon_redirect_url,
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
                        if (
                            self.check_direct_redirect_in_details
                            and not is_direct_download
                            and not patreon_redirect_url
                            and not details["download_urls"]
                        ):
                            post_id = self.patreon_provider.extract_post_id(href)
                            if post_id:
                                pat_info = self.patreon_provider.check_post_access(href)
                                if pat_info.get("status") and pat_info.get("status") != "NONE":
                                    details["patreon_status"] = pat_info.get("status", "LOCKED")
                                    details["patreon_tier"] = pat_info.get("tier_str", "")
                                if pat_info.get("download_urls"):
                                    details["download_urls"].extend(pat_info["download_urls"])
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
                ".cFileInfo_version, [data-role='version'], .ipsType_minorHeading, h1.ipsType_pageTitle span.ipsType_light"
            )
            if v_elem:
                details["version_str"] = v_elem.get_text(strip=True)

        except Exception as e:
            err_str = str(e).lower()
            if "timed out" in err_str or "timeout" in err_str or "28" in err_str:
                logger.warning(
                    f"Timeout lors de l'extraction des détails pour {mod_url} (serveur {self.display_name} indisponible ou lent)"
                )
            else:
                logger.error(f"Error extracting details for {mod_url}: {e}", exc_info=True)

        return details

    def extract_download_candidates(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, Any]]:
        """Extrait les candidats de téléchargement IPS4 depuis la page ou la modale de versions."""
        return _ext_dl_candidates(soup, base_url or self.base_url)

    _extract_download_candidates = extract_download_candidates

    def extract_requirements(self, soup: BeautifulSoup) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """Extrait et normalise les prérequis de mods depuis le DOM IPS4."""
        return extract_loverslab_requirements(soup, self.KNOWN_MOD_ALIASES)

    _extract_requirements = extract_requirements

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les métadonnées de base d'un mod IPS4 par son identifiant distant."""
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
        **kwargs: Any,
    ) -> Tuple[bool, str]:
        """Télécharge un fichier de mod depuis cette plateforme IPS4."""
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

    download_mod = download_mod_file

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Vérifie le statut d'accès au mod (notamment en cas de redirection Patreon)."""
        external_links = mod_data.get("external_links", [])
        for link in external_links:
            if "patreon.com" in link.lower():
                return self.patreon_provider.check_post_access(link).get("status", "UNKNOWN")
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """Vérifie si l'utilisateur connecté a déjà publié un commentaire contenant les mots-clés."""
        return LoversLabForumService.check_user_already_commented(
            page_url, required_keywords, provider_name=self.provider_name
        )

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """Publie un commentaire sur la page du mod ou le fil de support associé."""
        return LoversLabForumService.post_mod_comment(
            page_url, message, provider_name=self.provider_name, base_url=self.base_url
        )

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Supprime un commentaire publié par l'utilisateur sur le forum IPS4."""
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
        """Envoie un message privé au créateur via la messagerie IPS4."""
        return LoversLabForumService.send_private_message(
            creator_id, creator_name, subject, message, provider_name=self.provider_name, base_url=self.base_url
        )
