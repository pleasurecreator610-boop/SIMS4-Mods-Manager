"""
The Sims Resource (TSR) Comments: Reading, posting, and deleting user comments on TSR mods.
"""

import re
from typing import List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from plugins.thesimsresource.parsers import extract_item_id
from src.core.session_manager import SessionManager
from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.thesimsresource.com",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts creator info (ID, display name, profile URL) from a TSR mod page."""
    if not page_url:
        return None, None, None
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
            profile_url = urllib.parse.urljoin(base_url, href) if href else None
            creator_id = href.rstrip("/").split("/")[-1] if href else name
            return creator_id, name, profile_url
    except Exception as e:
        logger.debug(f"TSR get_creator_info failed for {page_url}: {e}")
    return None, None, None


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    provider_name: str = "thesimsresource",
) -> Tuple[bool, Optional[str]]:
    """Checks if a comment mentioning requirements or from the user is already present on TSR."""
    if not page_url:
        return False, None
    try:
        resp = session.get(page_url, timeout=15)
        if resp.status_code != 200:
            return False, None
        soup = BeautifulSoup(resp.text, "html.parser")
        acc = SessionManager.get_saved_session(provider_name)
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


def post_mod_comment(
    page_url: str,
    message: str,
    session: requests.Session,
    base_url: str = "https://www.thesimsresource.com",
    provider_name: str = "thesimsresource",
) -> Tuple[bool, str]:
    """Posts a comment on a TSR mod page via `/feedback/ax-add-comment/`."""
    if not page_url or not message.strip():
        return False, "URL ou message de commentaire manquant."
    if not SessionManager.is_session_ready(provider_name):
        return (
            False,
            "Aucun compte The Sims Resource connecté. Connectez-vous dans l'onglet Comptes ou ouvrez dans le navigateur.",
        )

    try:
        item_id = extract_item_id(page_url)
        parsed_url = urllib.parse.urlparse(page_url)
        ref_path = parsed_url.path or f"/downloads/details/id/{item_id}"

        if not item_id:
            page_resp = session.get(page_url, timeout=15)
            if page_resp.status_code == 200:
                soup = BeautifulSoup(page_resp.text, "html.parser")
                item_id = extract_item_id(page_url, soup, page_resp.text)
        if not item_id:
            return False, "Impossible d'extraire l'identifiant du mod TSR pour publier le commentaire."

        endpoint = f"{base_url}/feedback/ax-add-comment/"
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


def delete_mod_comment(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.thesimsresource.com",
    required_keywords: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Deletes a comment published by the user on TSR via `/feedback/ax-remove-comment/`."""
    if not page_url:
        return False, "URL de la page manquante."
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
                    f"{base_url}/feedback/ax-remove-comment/",
                    data={"id": cid, "ref": ref_path},
                    headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
                    timeout=15,
                )
                if del_resp.status_code == 200:
                    return True, "Commentaire supprimé avec succès sur The Sims Resource."
        return False, "Aucun commentaire supprimable trouvé sur cette page TSR."
    except Exception as e:
        return False, str(e)
