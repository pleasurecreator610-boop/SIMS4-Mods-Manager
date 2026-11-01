"""Classe de base abstraite et utilitaires mutualisés pour tous les fournisseurs de mods."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.core.dto import ModDetailsDTO


class BaseSourceProvider(ABC):
    """Classe de base abstraite pour les fournisseurs de mods (LoversLab, CurseForge, NexusMods, etc.).

    Fournit nativement la gestion des sous-catégories, le calcul de pagination globale
    et la régulation de cadence des requêtes HTTP (_pace_request).
    """

    provider_name: str = "base"
    display_name: str = "Base Provider"
    base_url: str = ""
    login_url: str = ""
    CATEGORIES: List[Dict[str, Any]] = []

    _request_lock: threading.Lock = threading.Lock()
    _last_request_ts: float = 0.0
    _min_request_interval: float = 0.5

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._request_lock = threading.Lock()
        cls._last_request_ts = 0.0

    def __init__(self) -> None:
        self._category_pages_cache: Dict[str, int] = {
            c["id"]: c.get("default_pages", 1) for c in self.CATEGORIES if "id" in c
        }
        first_cat = self.CATEGORIES[0]["name"] if self.CATEGORIES else self.display_name
        self.current_category_info: str = first_cat

    @classmethod
    def _pace_request(cls, session: Any) -> None:
        """Régule les requêtes HTTP sortantes (ignoré sur les sessions mockées en test)."""
        if getattr(session, "_is_mock", False):
            return
        with cls._request_lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_ts
            if elapsed < cls._min_request_interval:
                time.sleep(cls._min_request_interval - elapsed)
            cls._last_request_ts = time.monotonic()

    @classmethod
    def _fetch_with_retry(
        cls,
        session: Any,
        url: str,
        timeout: float = 15.0,
        max_retries: int = 2,
        **kwargs: Any,
    ) -> Any:
        """Exécute une requête HTTP GET avec gestion résiliente des codes 429/502/503/504 et Retry-After."""
        cls._pace_request(session)
        is_mock = bool(getattr(session, "_is_mock", False) or hasattr(session, "assert_called"))
        attempts = 1 if is_mock else max(1, max_retries + 1)
        last_resp = None
        for attempt in range(attempts):
            resp = session.get(url, timeout=timeout, **kwargs)
            last_resp = resp
            status = getattr(resp, "status_code", 200)
            if status not in (429, 502, 503, 504) or attempt + 1 >= attempts:
                return resp
            retry_after = 0.5 * (attempt + 1)
            headers = getattr(resp, "headers", None)
            if isinstance(headers, dict) and "Retry-After" in headers:
                try:
                    retry_after = min(5.0, max(0.2, float(headers["Retry-After"])))
                except (ValueError, TypeError):
                    pass
            time.sleep(retry_after)
        return last_resp

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        """Met à jour le cache du nombre de pages détectées pour une sous-catégorie."""
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [
            (cat, self._category_pages_cache.get(cat["id"], cat.get("default_pages", 1))) for cat in self.CATEGORIES
        ]

    def get_total_pages(self) -> int:
        """Retourne le nombre total de pages sur l'ensemble des sous-catégories configurées."""
        if not self.CATEGORIES:
            return 0
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
        """Scrape une page d'une sous-catégorie spécifique et retourne (mods, detected_pages)."""
        return [], 0

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """Scrape une page globale du catalogue et retourne la liste des métadonnées de mods."""
        if not self.CATEGORIES:
            return []
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    @abstractmethod
    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """Récupère les détails complets d'une page de mod (liens de téléchargement, version, prérequis)."""

    @abstractmethod
    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Télécharge une archive ou un fichier de mod vers dest_path."""

    @abstractmethod
    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """Vérifie le statut d'accessibilité du mod (PUBLIC, UNLOCKED, LOCKED, NEEDS_ACCOUNT)."""

    @abstractmethod
    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """Vérifie si l'utilisateur connecté a déjà publié un commentaire contenant les mots-clés."""

    @abstractmethod
    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """Publie un commentaire sur la page du mod ou le fil de support."""

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Supprime un commentaire publié par l'utilisateur connecté sur la page du mod."""
        return False, "Ce fournisseur ne supporte pas la suppression de commentaires."

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extrait les informations du créateur (member_id, member_name, profile_url) si supporté."""
        return None, None, None

    def check_user_already_sent_pm(
        self,
        creator_id: Optional[str] = None,
        creator_name: Optional[str] = None,
        mod_title: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """Vérifie si un message privé a déjà été envoyé au créateur."""
        return False, None

    def send_private_message(
        self,
        creator_id: str,
        creator_name: str,
        subject: str,
        message: str,
    ) -> Tuple[bool, str]:
        """Envoie un message privé au créateur si supporté par la plateforme."""
        return False, "Ce fournisseur ne supporte pas l'envoi de messages privés."
