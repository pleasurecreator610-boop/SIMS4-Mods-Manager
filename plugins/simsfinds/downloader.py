"""
SimsFinds Downloader: Téléchargement direct ou résolution de redirection vers les hébergeurs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
import requests

from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger


def download_simsfinds_file(
    file_info: Dict[str, Any],
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    session: Optional[requests.Session] = None,
    provider_name: str = "simsfinds",
) -> Tuple[bool, str]:
    """Télécharge un fichier depuis SimsFinds ou résout l'URL finale via redirection."""
    url = file_info.get("url")
    if not url:
        return False, "URL de téléchargement SimsFinds manquante."

    http_session = session or SessionManager.get_http_session(provider_name)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.simsfinds.com/",
        }

        resp = http_session.get(url, stream=True, timeout=30, headers=headers, allow_redirects=True)
        if resp.status_code != 200:
            return False, f"Échec du téléchargement SimsFinds (Code HTTP {resp.status_code})"

        total_bytes = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        target_file = Path(dest_path)
        target_file.parent.mkdir(parents=True, exist_ok=True)

        with open(target_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if ShutdownManager.is_shutting_down():
                    return False, "Téléchargement interrompu (arrêt demandé)."
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes)

        if os.path.exists(target_file) and os.path.getsize(target_file) > 0:
            logger.info(f"Fichier SimsFinds téléchargé avec succès: {target_file.name} ({downloaded} octets)")
            return True, f"Téléchargement réussi ({downloaded} octets)."

        return False, "Le fichier téléchargé est vide."
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement SimsFinds sur {url}: {e}", exc_info=True)
        return False, str(e)
