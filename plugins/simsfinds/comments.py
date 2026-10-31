"""
SimsFinds Comments: Lecture, publication et suppression de commentaires / retours créateurs.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from plugins.simsfinds.parsers import extract_item_id
from src.core.session_manager import SessionManager
from src.utils.logger import logger


def get_creator_info(
    page_url: str,
    session: requests.Session,
    base_url: str = "https://www.simsfinds.com",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrait les informations du créateur (ID, nom, profil) depuis une page SimsFinds."""
    if not page_url:
        return None, None, None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": base_url,
        }
        resp = session.get(page_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, None, None

        soup = BeautifulSoup(resp.text, "html.parser")
        creator_el = soup.select_one("a[href*='/creator/'], a._ptflink-profile, ._creator-name")
        if creator_el:
            name = creator_el.get_text(strip=True)
            href = creator_el.get("href", "")
            profile_url = urllib.parse.urljoin(base_url, href) if href else None
            m = re.search(r"/creator/(\d+)", href)
            creator_id = m.group(1) if m else name
            return creator_id, name, profile_url
    except Exception as e:
        logger.debug(f"SimsFinds get_creator_info failed for {page_url}: {e}")
    return None, None, None


def check_user_already_commented(
    page_url: str,
    required_keywords: List[str],
    session: requests.Session,
    base_url: str = "https://www.simsfinds.com",
    provider_name: str = "simsfinds",
) -> Tuple[bool, Optional[str]]:
    """Vérifie si l'utilisateur connecté a déjà publié un commentaire sur ce mod."""
    item_id = extract_item_id(page_url)
    if not item_id:
        return False, None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": page_url,
    }

    try:
        resp = session.get(page_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")
        acc = SessionManager.get_saved_session(provider_name)
        current_user = (acc.user_display_name or "").strip().lower() if acc else ""
        kw_lower = [k.strip().lower() for k in required_keywords if k and k.strip()]

        for comment_box in soup.find_all(class_=re.compile(r"comment|coment", re.I)):
            txt_lower = comment_box.get_text(" ", strip=True).lower()
            author_el = comment_box.find(class_=re.compile(r"user|author|nome", re.I))
            author_name = author_el.get_text(strip=True).lower() if author_el else ""

            if current_user and author_name and current_user in author_name:
                if not kw_lower or any(k in txt_lower for k in kw_lower):
                    cid = comment_box.get("data-id") or comment_box.get("data-comentario-id")
                    return True, str(cid) if cid else "already_commented"
            elif kw_lower and all(k in txt_lower for k in kw_lower):
                cid = comment_box.get("data-id") or comment_box.get("data-comentario-id")
                return True, str(cid) if cid else "already_commented"
    except Exception as e:
        logger.debug(f"SimsFinds check_user_already_commented failed: {e}")

    return False, None


def post_mod_comment(
    page_url: str,
    message: str,
    session: requests.Session,
    base_url: str = "https://www.simsfinds.com",
    provider_name: str = "simsfinds",
) -> Tuple[bool, str]:
    """Publie un message ou un commentaire sur un mod SimsFinds."""
    if not page_url or not message.strip():
        return False, "URL ou message de commentaire manquant."

    if not SessionManager.is_session_ready(provider_name):
        return (
            False,
            "Session SimsFinds non authentifiée. Veuillez vous connecter dans l'onglet Comptes.",
        )

    item_id = extract_item_id(page_url)
    if not item_id:
        return False, f"Impossible d'extraire l'ID du mod depuis {page_url}."

    comment_endpoint = f"{base_url}/files/downloads/acoes/comentar.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": page_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = {
        "c": item_id,
        "t": message.strip(),
        "via": 1,
    }

    try:
        resp = session.post(comment_endpoint, data=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            logger.info(f"Commentaire SimsFinds posté avec succès sur {page_url}")
            return True, "Commentaire publié avec succès sur SimsFinds."
        return False, f"Échec de publication SimsFinds (Code HTTP {resp.status_code})"
    except Exception as e:
        logger.error(f"Erreur lors de la publication sur SimsFinds: {e}")
        return False, str(e)


def delete_mod_comment(
    page_url: str,
    comment_id: str,
    session: requests.Session,
    base_url: str = "https://www.simsfinds.com",
    provider_name: str = "simsfinds",
) -> Tuple[bool, str]:
    """Supprime un commentaire publié sur SimsFinds."""
    if not comment_id:
        return False, "ID de commentaire SimsFinds manquant."

    delete_endpoint = f"{base_url}/files/downloads/acoes/deletar-criacao-requerida.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": page_url,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        resp = session.post(delete_endpoint, data={"i": comment_id}, headers=headers, timeout=20)
        if resp.status_code == 200:
            logger.info(f"Commentaire SimsFinds #{comment_id} supprimé avec succès.")
            return True, "Commentaire SimsFinds supprimé."
        return False, f"Code HTTP {resp.status_code} lors de la suppression."
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du commentaire SimsFinds #{comment_id}: {e}")
        return False, str(e)
