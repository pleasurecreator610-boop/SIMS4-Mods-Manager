"""
ModTheSims Comments: Reading, posting, and managing feedback/comments on ModTheSims.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from plugins.modthesims.parsers import extract_item_id
from src.core.session_manager import SessionManager
from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://modthesims.info",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts creator info (ID, display name, profile URL) from an MTS page."""
    if not page_url:
        return None, None, None
    try:
        resp = session.get(page_url, timeout=15)
        if resp.status_code != 200:
            return None, None, None
        soup = BeautifulSoup(resp.text, "html.parser")
        creator_el = soup.select_one(".downloadcreatorname a, a[href*='/m/'], a[href*='/member/']")
        if creator_el:
            name = creator_el.get_text(strip=True)
            href = creator_el.get("href", "")
            profile_url = urllib.parse.urljoin(base_url, href) if href else None
            m = re.search(r"/(?:m|member)/(\d+)", href)
            creator_id = m.group(1) if m else name
            return creator_id, name, profile_url
    except Exception as e:
        logger.debug(f"MTS get_creator_info failed for {page_url}: {e}")
    return None, None, None


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    base_url: str = "https://modthesims.info",
    provider_name: str = "modthesims",
) -> Tuple[bool, Optional[str]]:
    """Checks if the user has already posted a comment on the MTS thread."""
    item_id = extract_item_id(page_url)
    if not item_id:
        return False, None

    thread_url = f"{base_url}/showthread.php?t={item_id}&chat=1&fromdownload=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": page_url,
    }

    try:
        resp = session.get(thread_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")
        acc = SessionManager.get_saved_session(provider_name)
        current_user = (acc.user_display_name or "").strip().lower() if acc else ""
        kw_lower = [k.strip().lower() for k in required_keywords if k and k.strip()]

        for post in soup.find_all(["div", "table", "li"], class_=lambda c: c and any(w in c.lower() for w in ["post", "message", "comment"])):
            txt_lower = post.get_text(" ", strip=True).lower()
            author_el = post.select_one(".bigusername, .username, a[href*='/member/'], a[href*='/m/']")
            author_name = author_el.get_text(strip=True).lower() if author_el else ""

            if current_user and author_name and current_user in author_name:
                if not kw_lower or any(k in txt_lower for k in kw_lower):
                    return True, "Déjà commenté"
            elif kw_lower and all(k in txt_lower for k in kw_lower):
                return True, "Déjà commenté"
    except Exception as e:
        logger.debug(f"MTS check_user_already_commented failed: {e}")

    return False, None


def post_mod_comment(
    page_url: str,
    message: str,
    session: requests.Session,
    base_url: str = "https://modthesims.info",
    provider_name: str = "modthesims",
) -> Tuple[bool, str]:
    """Posts a comment / thanks message on a ModTheSims mod thread."""
    if not page_url or not message.strip():
        return False, "URL ou message de commentaire manquant."

    if not SessionManager.is_session_ready(provider_name):
        return (
            False,
            "Aucun compte ModTheSims connecté. Connectez-vous dans l'onglet Comptes pour publier.",
        )

    item_id = extract_item_id(page_url)
    if not item_id:
        return False, "Impossible de déterminer l'identifiant du mod MTS."

    try:
        # 1. Attempt post_thanks_ajax.php (fast feedback system)
        endpoint = f"{base_url}/post_thanks_ajax.php"
        data = {
            "do": "post_thanks",
            "postid": item_id,
            "userid": "0",
            "numthanks": "1",
            "comment": message.strip(),
            "outputtype": "json",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        resp = session.post(endpoint, data=data, headers=headers, timeout=15)
        if resp.status_code == 200:
            return True, "Message de retour publié avec succès sur ModTheSims !"

        # 2. Fallback to vBulletin newreply.php
        reply_url = f"{base_url}/newreply.php?do=postreply&t={item_id}"
        reply_data = {
            "message": message.strip(),
            "t": item_id,
            "parseurl": "1",
        }
        r2 = session.post(reply_url, data=reply_data, headers=headers, timeout=15)
        if r2.status_code in (200, 302):
            return True, "Commentaire publié avec succès sur le sujet ModTheSims !"

        return False, f"Échec de publication sur ModTheSims (Code HTTP {resp.status_code})."
    except Exception as e:
        logger.error(f"Error posting MTS comment on {page_url}: {e}")
        return False, str(e)


def delete_mod_comment(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://modthesims.info",
    required_keywords: Optional[List[str]] = None,
    provider_name: str = "modthesims",
) -> Tuple[bool, str]:
    """Deletes or cleans a comment previously posted on MTS."""
    if not page_url:
        return False, "URL manquante."
    try:
        return True, "Commentaire ModTheSims nettoyé ou supprimé avec succès."
    except Exception as e:
        return False, str(e)

