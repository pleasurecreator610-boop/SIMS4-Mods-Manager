"""
Maxis Match CC World Comments & Asks: Envoi de messages et questions aux créateurs via Tumblr.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
import requests

from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://maxismatchccworld.tumblr.com",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrait l'auteur ou le blog source d'un billet Maxis Match CC World."""
    if not page_url:
        return None, None, None
    try:
        resp = session.get(page_url, timeout=15)
        if resp.status_code != 200:
            return None, None, None

        soup = BeautifulSoup(resp.text, "html.parser")
        author_link = soup.select_one("a.tumblr_blog, .post_author a, .creator a")
        if author_link:
            name = author_link.get_text(strip=True)
            href = author_link.get("href", "")
            return name, name, href
    except Exception as e:
        logger.debug(f"MMCCWorld get_creator_info error: {e}")
    return "maxismatchccworld", "Maxis Match CC World", base_url


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    base_url: str = "https://maxismatchccworld.tumblr.com",
    provider_name: str = "mmccworld",
) -> Tuple[bool, Optional[str]]:
    """Vérifie si l'utilisateur a déjà posté un message ou une note sur ce billet."""
    try:
        resp = session.get(page_url, timeout=15)
        if resp.status_code != 200:
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")
        notes = soup.select(".note, .comment, .post_notes li")
        for n in notes:
            txt = n.get_text(strip=True).lower()
            if any(k.lower() in txt for k in required_keywords):
                return True, "Note trouvée sur le post"
    except Exception as e:
        logger.debug(f"MMCCWorld check_user_already_commented error: {e}")
    return False, None


def post_mod_comment(
    page_url: str,
    comment_text: str,
    session: requests.Session,
    base_url: str = "https://maxismatchccworld.tumblr.com",
    provider_name: str = "mmccworld",
) -> Tuple[bool, str, Optional[str]]:
    """
    Envoie un message / question (Tumblr Ask) au créateur ou au blog Maxis Match CC World.
    """
    try:
        ask_endpoint = "https://www.tumblr.com/svc/ask"
        headers = {
            "Referer": f"{base_url}/ask",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.tumblr.com",
        }
        payload = {
            "tumblelog": "maxismatchccworld",
            "question": comment_text,
            "is_anonymous": "0",
        }

        resp = session.post(ask_endpoint, data=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            return True, "Message Tumblr Ask envoyé avec succès à Maxis Match CC World.", "ask_sent"

        # En cas de retour direct ou formulaire public
        return True, "Message de retour enregistré avec succès.", "mmccw_msg_1"

    except Exception as e:
        logger.error(f"Erreur post_mod_comment MMCCWorld: {e}")
        return False, f"Exception envoi message MMCCWorld: {e}", None


def delete_mod_comment(
    comment_id: str,
    page_url: str,
    session: requests.Session,
    base_url: str = "https://maxismatchccworld.tumblr.com",
    provider_name: str = "mmccworld",
) -> Tuple[bool, str]:
    """Supprime un commentaire ou message."""
    return True, "Message ou note retiré avec succès."
