"""
Nexus Mods Comments & Feedback: Gestion des commentaires et retours créateurs sur nexusmods.com.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.nexusmods.com",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrait le créateur (nom, profil, ID) depuis la page d'un mod Nexus Mods."""
    if not page_url:
        return None, None, None
    try:
        resp = session.get(page_url, timeout=15)
        if resp.status_code != 200:
            return None, None, None

        soup = BeautifulSoup(resp.text, "html.parser")
        creator_el = soup.select_one("a[href*='/users/'], .user-name, .header-user")
        if creator_el:
            name = creator_el.get_text(strip=True)
            href = creator_el.get("href", "")
            profile_url = urllib.parse.urljoin(base_url, href) if href else None
            m = re.search(r"/users/(\d+)", href)
            creator_id = m.group(1) if m else name
            return creator_id, name, profile_url
    except Exception as e:
        logger.debug(f"Nexus Mods get_creator_info failed for {page_url}: {e}")
    return None, None, None


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    base_url: str = "https://www.nexusmods.com",
    provider_name: str = "nexusmods",
) -> Tuple[bool, Optional[str]]:
    """Vérifie si l'utilisateur connecté a déjà publié un commentaire sur ce mod."""
    try:
        # Onglet posts du mod
        posts_url = page_url
        if "?tab=" not in posts_url:
            posts_url = f"{posts_url.rstrip('/')}?tab=posts"

        resp = session.get(posts_url, timeout=15)
        if resp.status_code != 200:
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")
        comments = soup.select(".comment, .forum-post, .comment-content")

        for c in comments:
            text = c.get_text(strip=True).lower()
            if any(k.lower() in text for k in required_keywords):
                cid_attr = c.get("id", "") or c.get("data-comment-id", "")
                m = re.search(r"\d+", str(cid_attr))
                comment_id = m.group(0) if m else "found"
                return True, comment_id

    except Exception as e:
        logger.debug(f"Nexus Mods check_user_already_commented error: {e}")

    return False, None


def post_mod_comment(
    page_url: str,
    comment_text: str,
    session: requests.Session,
    base_url: str = "https://www.nexusmods.com",
    provider_name: str = "nexusmods",
) -> Tuple[bool, str, Optional[str]]:
    """Publie un message ou retour sous un mod Nexus Mods."""
    try:
        m = re.search(r"/mods/(\d+)", page_url)
        if not m:
            return False, "ID de mod introuvable dans l'URL.", None

        mod_id = m.group(1)
        # Endpoint de publication de commentaire Nexus Mods
        post_endpoint = f"{base_url}/Core/Libs/Common/Widgets/CommentContainer?action=add-comment"
        payload = {
            "mod_id": mod_id,
            "comment": comment_text,
            "game_id": 641,
        }
        headers = {
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        resp = session.post(post_endpoint, data=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            return True, "Commentaire publié avec succès sur Nexus Mods.", f"nm_c_{mod_id}"
        return False, f"Erreur lors de la publication Nexus Mods (code {resp.status_code}).", None

    except Exception as e:
        logger.error(f"Erreur post_mod_comment Nexus Mods: {e}")
        return False, f"Exception lors de la publication: {e}", None


def delete_mod_comment(
    comment_id: str,
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.nexusmods.com",
    provider_name: str = "nexusmods",
) -> Tuple[bool, str]:
    """Supprime un commentaire publié sur Nexus Mods."""
    try:
        delete_endpoint = f"{base_url}/Core/Libs/Common/Widgets/CommentContainer?action=delete-comment"
        m = re.search(r"\d+", comment_id)
        cid = m.group(0) if m else comment_id

        payload = {
            "comment_id": cid,
            "game_id": 641,
        }
        headers = {
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        resp = session.post(delete_endpoint, data=payload, headers=headers, timeout=15)
        if resp.status_code in (200, 204):
            return True, "Commentaire Nexus Mods supprimé avec succès."
        return False, f"Impossible de supprimer le commentaire (code HTTP {resp.status_code})."

    except Exception as e:
        logger.error(f"Erreur delete_mod_comment Nexus Mods: {e}")
        return False, f"Exception suppression: {e}"
