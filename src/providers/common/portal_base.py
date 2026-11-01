"""
Socle mutualisé (BasePortalProvider) pour les portails officiels de frameworks,
les catalogues communautaires (HTML / JSON API) et les sites de créateurs Sims 4.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.parse
from bs4 import BeautifulSoup

from src.application.dependencies.dependency_special_cases import find_special_dependency_case
from src.core.dto import ModDetailsDTO
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.base import BaseSourceProvider
from src.utils.dependency_noise_rules import is_likely_comment_or_noise
from src.utils.game_dlc_matcher import GameDlcMatcher
from src.utils.logger import logger
from src.utils.mod_matcher import ModMatcher

__all__ = [
    "BasePortalProvider",
    "extract_portal_requirements",
    "extract_portal_download_links",
    "parse_portal_catalog_html",
]

_DIRECT_EXT_RE = re.compile(r"(?i)\.(?:zip|rar|7z|package|ts4script)(?:$|\?)")
_EXTERNAL_HOST_RE = re.compile(
    r"(?i)(?:simfileshare\.net|sfs\.|github\.com/.+/releases|patreon\.com/file|"
    r"drive\.google\.com|mediafire\.com|mega\.nz|dropbox\.com|curseforge\.com/.+/download|"
    r"wicked\.cc/download|wonderfulwhims\.com/download|deaderpool-mccc\.com|scumbumbomods\.com|"
    r"lumpinoumods\.com|basementalcc\.com|lms-mods\.com|sixam\.cc|itch\.io|gamebanana\.com/dl|"
    r"synthira\.ru/load|smutbase\.com)"
)
_REQ_HEADER_RE = re.compile(
    r"(?i)\b(?:requirements?|pr[ée]requis|required\s*(?:mods?|packs?|files?)|dependencies|needs?)\s*[:\-–—]"
)


def extract_portal_download_links(
    soup: BeautifulSoup,
    page_url: str,
    base_url: str,
    fallback_downloads: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Extrait tous les liens de téléchargement directs ou miroirs depuis une page de mod."""
    links: List[Dict[str, str]] = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        full_url = urllib.parse.urljoin(base_url or page_url, href)
        text = a.get_text(" ", strip=True) or Path(urllib.parse.urlparse(full_url).path).name or "Download"
        cls_str = " ".join(a.get("class", []) if isinstance(a.get("class"), list) else [str(a.get("class") or "")])

        is_dl_button = any(
            kw in f"{text} {cls_str} {href}".lower()
            for kw in ("download", "télécharger", "dl_btn", "download_btn", "file/download", "?do=download")
        )
        if _DIRECT_EXT_RE.search(full_url) or _EXTERNAL_HOST_RE.search(full_url) or is_dl_button:
            if full_url not in seen_urls and full_url.rstrip("/") != base_url.rstrip("/"):
                seen_urls.add(full_url)
                links.append({"name": text[:80] or "Download", "url": full_url})

    if not links and fallback_downloads:
        for fb in fallback_downloads:
            u = fb.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                links.append({"name": fb.get("name", "Download"), "url": u})

    return links


def extract_portal_requirements(
    soup: BeautifulSoup,
    provider_name: str,
    base_url: str,
) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    """
    Extrait et structure les prérequis d'une page de mod en distinguant :
    - Les frameworks officiels (Deaderpool, Scumbumbo, Lumpinou, Wicked.cc, Basemental, S4S).
    - Les DLC officiels EA Games.
    - Les mods prérequis liés ou nommés.
    - Les notes/commentaires (conservés pour classification COMMENT_NOISE / signalement).
    """
    req_lines: List[str] = []
    req_mods: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    # 1. Inspect explicit requirement blocks or lists
    for el in soup.find_all(["div", "section", "ul", "p", "li", "tr"]):
        txt = el.get_text("\n", strip=True)
        if not txt or len(txt) > 600:
            continue
        if _REQ_HEADER_RE.search(txt):
            # Collect links inside this requirement block
            for a in el.find_all("a", href=True):
                a_title = a.get_text(" ", strip=True)
                a_href = urllib.parse.urljoin(base_url, str(a["href"]).strip())
                if not a_title or len(a_title) < 2:
                    continue
                special = find_special_dependency_case(a_title, url=a_href)
                if special:
                    k = f"{special['source']}:{special['remote_id']}"
                    if k not in seen_keys:
                        seen_keys.add(k)
                        req_mods.append(
                            {
                                "source": special["source"],
                                "remote_id": special["remote_id"],
                                "title": special["title"],
                                "url": special["url"],
                            }
                        )
                    continue

                is_dlc, dlc_name, dlc_code = GameDlcMatcher.match_dlc(a_title)
                if is_dlc:
                    k = f"dlc:{dlc_code or dlc_name}"
                    if k not in seen_keys:
                        seen_keys.add(k)
                        req_mods.append(
                            {
                                "source": "game_dlc",
                                "remote_id": dlc_code or "",
                                "title": f"The Sims 4 : {dlc_name}",
                                "url": "",
                                "is_game_dlc": True,
                                "dlc_name": dlc_name,
                                "dlc_code": dlc_code,
                            }
                        )
                    continue

                k = a_title.lower()
                if k not in seen_keys:
                    seen_keys.add(k)
                    req_mods.append(
                        {
                            "source": provider_name,
                            "remote_id": "",
                            "title": a_title,
                            "url": a_href,
                        }
                    )

            # Also parse text tokens after header
            cleaned_block = _REQ_HEADER_RE.sub("", txt, count=1).strip()
            if cleaned_block:
                req_lines.append(cleaned_block)

    for line in req_lines:
        parts = [p.strip(" •*-–—\t\r\n.") for p in re.split(r"[,;\n•]+|\s+and\s+|\s+&\s+", line) if p.strip()]
        for part in parts:
            if len(part) < 2 or part.lower() in ModMatcher.GENERIC_EXCLUDED_WORDS:
                continue
            special = find_special_dependency_case(part)
            if special:
                k = f"{special['source']}:{special['remote_id']}"
                if k not in seen_keys:
                    seen_keys.add(k)
                    req_mods.append(
                        {
                            "source": special["source"],
                            "remote_id": special["remote_id"],
                            "title": special["title"],
                            "url": special["url"],
                        }
                    )
                continue

            is_dlc, dlc_name, dlc_code = GameDlcMatcher.match_dlc(part)
            if is_dlc:
                k = f"dlc:{dlc_code or dlc_name}"
                if k not in seen_keys:
                    seen_keys.add(k)
                    req_mods.append(
                        {
                            "source": "game_dlc",
                            "remote_id": dlc_code or "",
                            "title": f"The Sims 4 : {dlc_name}",
                            "url": "",
                            "is_game_dlc": True,
                            "dlc_name": dlc_name,
                            "dlc_code": dlc_code,
                        }
                    )
                continue

            k = part.lower()
            if k not in seen_keys:
                seen_keys.add(k)
                is_comment = is_likely_comment_or_noise(part)
                req_mods.append(
                    {
                        "source": provider_name,
                        "remote_id": "",
                        "title": part,
                        "url": "",
                        "is_comment": is_comment,
                        "status": "COMMENT_NOISE" if is_comment else "PENDING_VERIFICATION",
                    }
                )

    raw_text = "\n".join(req_lines) if req_lines else None
    if not req_mods:
        return raw_text, "NONE", []
    all_resolved = all(bool(m.get("remote_id")) or bool(m.get("is_game_dlc")) for m in req_mods)
    return raw_text, ("RESOLVED" if all_resolved else "FOUND"), req_mods


def parse_portal_catalog_html(
    html_text: str,
    category: Dict[str, Any],
    base_url: str,
    source_name: str,
    default_author: str = "Creator",
) -> Tuple[List[Dict[str, Any]], int]:
    """Parse une page de catalogue HTML générique (articles, cartes de mods, entrées de forum)."""
    soup = BeautifulSoup(html_text or "", "html.parser")
    results: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Detect total pages
    detected_pages = category.get("default_pages", 1)
    page_nums: List[int] = []
    for p_el in soup.select(".pagination a, .page-numbers, .ipsPagination a, .pagenav a, a[href*='page=']"):
        m = re.search(r"(?:page[/=]|p=)(\d+)", str(p_el.get("href", ""))) or re.search(
            r"^\d+$", p_el.get_text(strip=True)
        )
        if m:
            try:
                val = int(m.group(1) if m.lastindex else m.group(0))
                if 1 <= val <= 500:
                    page_nums.append(val)
            except ValueError:
                pass
    if page_nums:
        detected_pages = max(page_nums)

    cards = soup.select(
        "article, .post, .entry, .mod-card, .project-card, .game_cell, "
        ".ipsDataItem, .structItem, .thread-row, .item-card, .catalog-item"
    )
    for card in cards:
        a_el = card.select_one(
            "h1 a, h2 a, h3 a, h4 a, .title a, .entry-title a, .game_title a, "
            ".structItem-title a, a.name, a.mod-link, a[href]"
        )
        if not a_el or not a_el.get("href"):
            continue
        href = str(a_el["href"]).strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        page_url = urllib.parse.urljoin(base_url, href)
        title = a_el.get_text(" ", strip=True).replace("\u200b", "").strip()
        if not title or len(title) < 2:
            continue

        slug = Path(urllib.parse.urlparse(page_url).path.rstrip("/")).name
        slug_clean = re.sub(r"[^a-zA-Z0-9_-]", "_", slug).strip("_") or f"item_{len(results) + 1}"
        remote_id = f"{source_name}_{slug_clean}" if not slug_clean.startswith(source_name) else slug_clean
        if remote_id in seen_ids:
            continue
        seen_ids.add(remote_id)

        author_el = card.select_one(".author, .creator, .game_author, .username, a[href*='/member'], a[href*='/user']")
        author = author_el.get_text(" ", strip=True) if author_el else default_author

        img_el = card.select_one("img")
        thumb_url = ""
        if img_el:
            raw_src = img_el.get("data-src") or img_el.get("src") or ""
            if raw_src:
                thumb_url = urllib.parse.urljoin(base_url, str(raw_src))

        desc_el = card.select_one("p, .description, .summary, .entry-summary, .game_text")
        summary = desc_el.get_text(" ", strip=True)[:300] if desc_el else title

        results.append(
            {
                "source": source_name,
                "remote_id": remote_id,
                "title": title,
                "author": author,
                "page_url": page_url,
                "thumbnail_url": thumb_url,
                "description": summary,
                "category": category.get("name", source_name),
                "patreon_status": "PUBLIC",
                "tags": [category.get("name", source_name)],
            }
        )

    return results, detected_pages


class BasePortalProvider(BaseSourceProvider):
    """
    Classe de base mutualisée pour les portails de frameworks officiels,
    les catalogues communautaires et les sites de créateurs Sims 4.
    """

    provider_name: str = "portal"
    display_name: str = "Portal Provider"
    base_url: str = ""
    login_url: str = ""
    default_author: str = "Creator"
    is_adult_provider: bool = False
    requires_account_card: bool = False
    supports_comments: bool = False
    CATEGORIES: List[Dict[str, Any]] = []
    REFERENCE_MODS: List[Dict[str, Any]] = []

    def _get_reference_mods_for_category(self, cat_id: str) -> List[Dict[str, Any]]:
        matched = [m for m in self.REFERENCE_MODS if m.get("category_id") == cat_id or not m.get("category_id")]
        return matched if matched else list(self.REFERENCE_MODS)

    def _find_reference_mod(self, mod_url: str) -> Optional[Dict[str, Any]]:
        if not mod_url:
            return None
        u_low = mod_url.strip().lower().rstrip("/")
        for ref in self.REFERENCE_MODS:
            ref_url = str(ref.get("page_url", "")).strip().lower().rstrip("/")
            ref_rid = str(ref.get("remote_id", "")).strip().lower()
            if (ref_url and (ref_url == u_low or ref_url in u_low or u_low in ref_url)) or (
                ref_rid and ref_rid in u_low
            ):
                return ref
        return None

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Scrape une page de sous-catégorie avec repli sur le catalogue de référence officiel."""
        if ShutdownManager.is_shutting_down():
            return [], 0

        cat_id = category.get("id", "")
        cat_url = category.get("url", self.base_url)
        url = cat_url if page <= 1 else f"{cat_url.rstrip('/')}/?page={page}"
        session = SessionManager.get_http_session(self.provider_name)
        self._pace_request(session)

        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = category.get("default_pages", 1)

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and resp.text:
                parsed, det_p = parse_portal_catalog_html(
                    resp.text,
                    category=category,
                    base_url=self.base_url,
                    source_name=self.provider_name,
                    default_author=self.default_author,
                )
                if parsed:
                    results = parsed[:limit]
                    detected_pages = det_p
        except Exception as e:
            logger.debug(f"[{self.provider_name}] Repli catalogue de référence sur {url}: {e}")

        if not results and page == 1 and self.REFERENCE_MODS:
            for ref in self._get_reference_mods_for_category(cat_id):
                results.append(
                    {
                        "source": self.provider_name,
                        "remote_id": ref["remote_id"],
                        "title": ref["title"],
                        "author": ref.get("author", self.default_author),
                        "page_url": ref["page_url"],
                        "thumbnail_url": ref.get("thumbnail_url", ""),
                        "description": ref.get("description", ref["title"]),
                        "version_str": ref.get("version_str", ""),
                        "category": category.get("name", self.display_name),
                        "patreon_status": "PUBLIC",
                        "tags": list(ref.get("tags", [category.get("name", self.display_name)])),
                    }
                )

        if detected_pages and page == 1 and cat_id:
            self.update_category_detected_pages(cat_id, detected_pages)

        return results, detected_pages

    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """Extrait les détails complets, liens de téléchargement et dépendances d'un mod."""
        ref = self._find_reference_mod(mod_url)
        fallback_dls = list(ref.get("download_urls", [])) if ref else []
        fallback_reqs = list(ref.get("requirements_mods", [])) if ref else []

        details: Dict[str, Any] = {
            "remote_id": ref["remote_id"] if ref else f"{self.provider_name}_mod",
            "title": ref["title"] if ref else self.display_name,
            "author": ref.get("author", self.default_author) if ref else self.default_author,
            "description": ref.get("description", "") if ref else "",
            "version_str": ref.get("version_str", "1.0") if ref else "",
            "page_url": mod_url,
            "source": self.provider_name,
            "download_urls": fallback_dls,
            "external_links": [],
            "patreon_status": "NONE",
            "patreon_tier": "",
            "requirements_text": None,
            "requirements_status": "RESOLVED" if fallback_reqs else "NONE",
            "requirements_mods": fallback_reqs,
            "screenshots": [],
        }
        if not mod_url:
            return details

        session = SessionManager.get_http_session(self.provider_name)
        self._pace_request(session)
        try:
            resp = session.get(mod_url, timeout=15)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                if not ref and soup.title and soup.title.string:
                    details["title"] = soup.title.string.strip().split("|")[0].split("-")[0].strip()

                desc_el = soup.select_one(
                    "article, .entry-content, .post-content, .project-description, "
                    ".mod-description, .user_formatted, #description, main"
                )
                if desc_el:
                    details["description"] = desc_el.get_text("\n", strip=True)[:2000]

                dl_links = extract_portal_download_links(
                    soup, page_url=mod_url, base_url=self.base_url, fallback_downloads=fallback_dls
                )
                if dl_links:
                    details["download_urls"] = dl_links

                req_text, req_status, req_mods = extract_portal_requirements(
                    soup, provider_name=self.provider_name, base_url=self.base_url
                )
                if req_mods:
                    details["requirements_text"] = req_text
                    details["requirements_status"] = req_status
                    details["requirements_mods"] = req_mods
        except Exception as e:
            logger.debug(f"[{self.provider_name}] get_mod_details fallback pour {mod_url}: {e}")

        if not details["download_urls"] and mod_url:
            details["download_urls"] = [{"name": f"{details['title']}.zip", "url": f"{mod_url.rstrip('/')}/download"}]

        return details

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Retourne le niveau d'accès du mod."""
        if self.requires_account_card and mod_data.get("requires_login", False):
            return "UNLOCKED" if SessionManager.is_member_authenticated(self.provider_name) else "NEEDS_ACCOUNT"
        return "PUBLIC"

    def download_mod_file(
        self,
        download_url: Union[str, Dict[str, Any]],
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Télécharge et valide une archive ou un fichier de mod."""
        target_url = download_url.get("url", "") if isinstance(download_url, dict) else str(download_url or "")
        if not target_url:
            return False, "URL de téléchargement manquante."

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # If target_url is a mod page URL rather than direct file, resolve via get_mod_details first
        if not _DIRECT_EXT_RE.search(target_url) and "download" not in target_url.lower():
            det = self.get_mod_details(target_url)
            det_dict = det.model_dump() if hasattr(det, "model_dump") else (det if isinstance(det, dict) else {})
            dls = det_dict.get("download_urls", [])
            if dls:
                first_dl = dls[0]
                target_url = first_dl["url"] if isinstance(first_dl, dict) else str(first_dl)

        session = SessionManager.get_http_session(self.provider_name)
        self._pace_request(session)

        try:
            resp = session.get(target_url, stream=True, timeout=30)
            if resp.status_code != 200:
                return False, f"Échec HTTP {resp.status_code} sur {target_url}"

            ctype = (resp.headers.get("Content-Type") or "").lower()
            total_bytes = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            chunks: List[bytes] = []

            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                chunks.append(chunk)
                downloaded += len(chunk)
                if progress_callback and total_bytes > 0:
                    pct = min(99, int((downloaded / total_bytes) * 100))
                    progress_callback(pct, f"Téléchargement ({pct}%)...", dest.name)

            payload = b"".join(chunks) if chunks else (resp.content or b"")
            head_lower = payload[:256].lstrip().lower()
            if "text/html" in ctype or head_lower.startswith(b"<!doctype html") or head_lower.startswith(b"<html"):
                return (
                    False,
                    "Le serveur a retourné une page HTML (authentification ou page intermédiaire) au lieu d'un fichier binaire.",
                )

            if not payload:
                return False, "Fichier téléchargé vide."

            dest.write_bytes(payload)
            if progress_callback:
                progress_callback(100, "Téléchargement terminé", dest.name)
            return True, str(dest)
        except Exception as e:
            logger.error(f"[{self.provider_name}] Erreur téléchargement {target_url}: {e}")
            return False, str(e)

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extrait l'identifiant, le nom et l'URL de profil du créateur."""
        ref = self._find_reference_mod(page_url)
        if ref and ref.get("author"):
            author = str(ref["author"])
            return author.lower().replace(" ", "_"), author, self.base_url
        if not page_url:
            return None, None, None
        try:
            session = SessionManager.get_http_session(self.provider_name)
            resp = session.get(page_url, timeout=12)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                a_el = soup.select_one(
                    ".author a, .creator a, .username, a[href*='/user/'], a[href*='/member/'], a[href*='/profile/']"
                )
                if a_el:
                    name = a_el.get_text(" ", strip=True) or self.default_author
                    href = urllib.parse.urljoin(self.base_url, str(a_el.get("href", "")))
                    cid = Path(urllib.parse.urlparse(href).path.rstrip("/")).name or name.lower()
                    return cid, name, href
        except Exception as e:
            logger.debug(f"[{self.provider_name}] get_creator_info ignoré: {e}")
        return self.default_author.lower(), self.default_author, self.base_url

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """Vérifie en direct sur la page si l'utilisateur connecté a déjà signalé les prérequis."""
        if not self.supports_comments or not page_url:
            return False, None
        try:
            session = SessionManager.get_http_session(self.provider_name)
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200 or not resp.text:
                return False, None

            soup = BeautifulSoup(resp.text, "html.parser")
            acc = SessionManager.get_saved_session(self.provider_name)
            current_user = (acc.user_display_name or "").strip().lower() if acc else ""
            kw_lower = [k.strip().lower() for k in required_keywords if k and k.strip()]

            for comment_el in soup.select(
                ".comment, .post, .message, .reply, .comment_post, .structItem, article.message"
            ):
                txt_lower = comment_el.get_text(" ", strip=True).lower()
                if "sims 4 mods manager" in txt_lower:
                    return True, "Déjà signalé sur la page"
                if current_user and current_user in txt_lower:
                    if not kw_lower or any(k in txt_lower for k in kw_lower):
                        return True, "Déjà commenté par l'utilisateur"
                if kw_lower and all(k in txt_lower for k in kw_lower):
                    return True, "Déjà signalé"
        except Exception as e:
            logger.debug(f"[{self.provider_name}] check_user_already_commented erreur: {e}")
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """Publie un commentaire sur la page du mod (requiert une session membre authentifiée)."""
        if not self.supports_comments:
            return False, f"La plateforme {self.display_name} ne supporte pas les commentaires publics."
        if not page_url or not message.strip():
            return False, "URL ou contenu du commentaire manquant."
        if not SessionManager.is_member_authenticated(self.provider_name):
            return (
                False,
                f"Veuillez vous authentifier sur {self.display_name} dans l'onglet 'Comptes' avant de poster un commentaire.",
            )

        try:
            session = SessionManager.get_http_session(self.provider_name)
            post_url = f"{page_url.rstrip('/')}/comment"
            resp = session.post(
                post_url,
                data={"message": message.strip(), "body": message.strip(), "comment": message.strip()},
                timeout=15,
            )
            if resp.status_code in (200, 201, 204, 302):
                return True, f"Commentaire publié avec succès sur {self.display_name}."
            return False, f"Échec de publication sur {self.display_name} (HTTP {resp.status_code})."
        except Exception as e:
            logger.error(f"[{self.provider_name}] Erreur post_mod_comment: {e}")
            return False, str(e)

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Supprime un commentaire précédemment publié par l'utilisateur connecté."""
        if not self.supports_comments:
            return False, f"La plateforme {self.display_name} ne supporte pas la suppression de commentaires."
        if not SessionManager.is_member_authenticated(self.provider_name):
            return (
                False,
                f"Veuillez vous authentifier sur {self.display_name} dans l'onglet 'Comptes' pour supprimer un commentaire.",
            )
        try:
            session = SessionManager.get_http_session(self.provider_name)
            del_url = f"{page_url.rstrip('/')}/comment/delete"
            resp = session.post(del_url, data={"keywords": ",".join(required_keywords or [])}, timeout=15)
            if resp.status_code in (200, 204, 302):
                return True, f"Commentaire supprimé avec succès sur {self.display_name}."
            return False, f"Échec de suppression sur {self.display_name} (HTTP {resp.status_code})."
        except Exception as e:
            return False, str(e)

    def send_private_message(
        self,
        creator_id: str,
        creator_name: str,
        subject: str,
        message: str,
    ) -> Tuple[bool, str]:
        """Envoie un message privé au créateur sur les plateformes communautaires authentifiées."""
        if not self.supports_comments:
            return False, f"La plateforme {self.display_name} ne supporte pas les messages privés."
        if not SessionManager.is_member_authenticated(self.provider_name):
            return (
                False,
                f"Veuillez vous authentifier sur {self.display_name} dans l'onglet 'Comptes' pour envoyer un message privé.",
            )
        try:
            session = SessionManager.get_http_session(self.provider_name)
            pm_url = f"{self.base_url.rstrip('/')}/messages/send"
            resp = session.post(
                pm_url,
                data={"to": creator_id, "recipient": creator_name, "subject": subject, "message": message},
                timeout=15,
            )
            if resp.status_code in (200, 201, 204, 302):
                return True, f"Message privé envoyé à {creator_name} sur {self.display_name}."
            return False, f"Échec d'envoi du message privé sur {self.display_name} (HTTP {resp.status_code})."
        except Exception as e:
            return False, str(e)
