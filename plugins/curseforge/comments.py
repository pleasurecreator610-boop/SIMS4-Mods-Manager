"""
CurseForge Comments: Reading, posting, and deleting user comments on CurseForge mods.
"""

import re
from typing import Any, Callable, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from plugins.curseforge.parsers import extract_project_and_file_ids
from src.core.session_manager import SessionManager
from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.curseforge.com",
    get_with_retry: Optional[Callable[..., Any]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts creator info (ID, display name, profile URL) from a CurseForge page."""
    if not page_url:
        return None, None, None
    try:
        if get_with_retry:
            resp = get_with_retry(session, page_url, timeout=15)
        else:
            resp = session.get(page_url, timeout=15)
        if resp is None or resp.status_code != 200:
            return None, None, None
        soup = BeautifulSoup(resp.text, "html.parser")
        author_el = soup.select_one("a.author-name, .author-name, a[href*='/members/']")
        if author_el:
            name = author_el.get_text(strip=True)
            href = author_el.get("href", "")
            profile_url = urllib.parse.urljoin(base_url, href) if href else None
            creator_id = href.rstrip("/").split("/")[-1] if href else name
            return creator_id, name, profile_url
    except Exception as e:
        logger.debug(f"CurseForge get_creator_info failed for {page_url}: {e}")
    return None, None, None


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    base_url: str = "https://www.curseforge.com",
    provider_name: str = "curseforge",
    get_with_retry: Optional[Callable[..., Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """Checks via `/api/v1/mods/{projectId}/comments` if a comment mentioning requirements has already been published."""
    if not page_url:
        return False, None
    try:
        clean_url = re.sub(r"/comments/?$", "", page_url.split("?")[0].rstrip("/"))
        if get_with_retry:
            page_resp = get_with_retry(session, clean_url, timeout=15)
        else:
            page_resp = session.get(clean_url, timeout=15)
        if page_resp is None or page_resp.status_code != 200:
            return False, None
        soup = BeautifulSoup(page_resp.text, "html.parser")
        project_id, _ = extract_project_and_file_ids(soup, page_resp.text)
        if not project_id:
            return False, None

        comments_api = f"{base_url}/api/v1/mods/{project_id}/comments"
        if get_with_retry:
            c_resp = get_with_retry(session, comments_api, timeout=12)
        else:
            c_resp = session.get(comments_api, timeout=12)
        if c_resp is None or c_resp.status_code != 200:
            return False, None

        payload = c_resp.json()
        comments_list = payload.get("data", []) if isinstance(payload, dict) else []
        acc = SessionManager.get_saved_session(provider_name)
        current_user = (acc.user_display_name or "").strip().lower() if acc else ""

        kw_lower = [k.strip().lower() for k in required_keywords if k and k.strip()]
        for item in comments_list:
            body_text = str(item.get("body") or item.get("text") or "").lower()
            author_info = item.get("author") or {}
            author_name = str(author_info.get("username") or author_info.get("displayName") or "").lower()
            if current_user and author_name and current_user in author_name:
                if not kw_lower or any(k in body_text for k in kw_lower):
                    return True, str(item.get("datePosted") or "Déjà commenté")
            elif kw_lower and all(k in body_text for k in kw_lower):
                return True, str(item.get("datePosted") or "Déjà commenté")
    except Exception as e:
        logger.debug(f"CurseForge check_user_already_commented failed for {page_url}: {e}")
    return False, None


def post_mod_comment(
    page_url: str,
    message: str,
    session: requests.Session,
    base_url: str = "https://www.curseforge.com",
    get_with_retry: Optional[Callable[..., Any]] = None,
) -> Tuple[bool, str]:
    """Posts a comment on a CurseForge mod via `/api/v1/mods/{projectId}/comments`."""
    if not page_url or not message.strip():
        return False, "URL ou message de commentaire manquant."
    try:
        clean_url = re.sub(r"/comments/?$", "", page_url.split("?")[0].rstrip("/"))
        if get_with_retry:
            page_resp = get_with_retry(session, clean_url, timeout=15)
        else:
            page_resp = session.get(clean_url, timeout=15)
        if page_resp is None or page_resp.status_code != 200:
            return False, "Impossible de charger la page du mod CurseForge."

        if '"hasComments":false' in page_resp.text or '\\"hasComments\\":false' in page_resp.text:
            return (
                False,
                "L'auteur de ce mod a désactivé la section commentaires sur CurseForge.",
            )

        soup = BeautifulSoup(page_resp.text, "html.parser")
        project_id, _ = extract_project_and_file_ids(soup, page_resp.text)
        if not project_id:
            return False, "Impossible d'identifier le Project ID CurseForge pour publier le commentaire."

        comments_api = f"{base_url}/api/v1/mods/{project_id}/comments"
        post_resp = session.post(
            comments_api,
            json={"body": message.strip(), "bodyType": 1},
            headers={"Referer": f"{clean_url}/comments"},
            timeout=15,
        )
        if post_resp.status_code in (200, 201):
            return True, "Commentaire publié avec succès sur CurseForge !"
        if post_resp.status_code in (401, 403):
            return (
                False,
                "Session CurseForge non connectée ou protégée par Cloudflare. Utilisez le bouton d'ouverture dans le navigateur.",
            )
        return False, f"Échec de publication du commentaire sur CurseForge (HTTP {post_resp.status_code})."
    except Exception as e:
        logger.error(f"Error posting CurseForge comment on {page_url}: {e}")
        return False, str(e)


def delete_mod_comment(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.curseforge.com",
    required_keywords: Optional[List[str]] = None,
    provider_name: str = "curseforge",
    get_with_retry: Optional[Callable[..., Any]] = None,
) -> Tuple[bool, str]:
    """Deletes a comment published on CurseForge via `DELETE /api/v1/mods/{projectId}/comments/{commentId}`."""
    if not page_url:
        return False, "URL de la page manquante."
    try:
        clean_url = re.sub(r"/comments/?$", "", page_url.split("?")[0].rstrip("/"))
        if get_with_retry:
            page_resp = get_with_retry(session, clean_url, timeout=15)
        else:
            page_resp = session.get(clean_url, timeout=15)
        if page_resp is None or page_resp.status_code != 200:
            return False, "Impossible de charger la page du mod CurseForge."

        soup = BeautifulSoup(page_resp.text, "html.parser")
        project_id, _ = extract_project_and_file_ids(soup, page_resp.text)
        if not project_id:
            return False, "Impossible d'identifier le Project ID CurseForge."

        comments_api = f"{base_url}/api/v1/mods/{project_id}/comments"
        if get_with_retry:
            c_resp = get_with_retry(session, comments_api, timeout=12)
        else:
            c_resp = session.get(comments_api, timeout=12)
        if c_resp is None or c_resp.status_code != 200:
            return False, "Impossible de récupérer les commentaires CurseForge."

        payload = c_resp.json()
        comments_list = payload.get("data", []) if isinstance(payload, dict) else []
        acc = SessionManager.get_saved_session(provider_name)
        current_user = (acc.user_display_name or "").strip().lower() if acc else ""

        kw_lower = [k.strip().lower() for k in (required_keywords or []) if k and k.strip()]
        target_comment_id = None

        for item in comments_list:
            cid = item.get("id")
            body_text = str(item.get("body") or item.get("text") or "").lower()
            author_info = item.get("author") or {}
            author_name = str(author_info.get("username") or author_info.get("displayName") or "").lower()

            if current_user and author_name and current_user in author_name:
                if not kw_lower or any(k in body_text for k in kw_lower):
                    target_comment_id = cid
                    break
            elif kw_lower and all(k in body_text for k in kw_lower):
                target_comment_id = cid
                break

        if not target_comment_id:
            return False, "Aucun commentaire supprimable correspondant trouvé sur CurseForge."

        del_url = f"{base_url}/api/v1/mods/{project_id}/comments/{target_comment_id}"
        del_resp = session.delete(del_url, timeout=15)
        if del_resp.status_code in (200, 204):
            return True, "Commentaire supprimé avec succès sur CurseForge."
        return False, f"Échec de suppression du commentaire sur CurseForge (HTTP {del_resp.status_code})."
    except Exception as e:
        logger.error(f"Error deleting CurseForge comment on {page_url}: {e}")
        return False, str(e)
