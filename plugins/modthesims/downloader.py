"""
ModTheSims Downloader: Direct streaming and downloading of files from chii.modthesims.info.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
import requests

from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger


def download_mts_file(
    file_info: Dict[str, Any],
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    session: Optional[requests.Session] = None,
    provider_name: str = "modthesims",
) -> Tuple[bool, str]:
    """Downloads a file directly from ModTheSims / chii.modthesims.info."""
    url = file_info.get("url")
    if not url:
        return False, "URL de téléchargement ModTheSims manquante."

    http_session = session or SessionManager.get_http_session(provider_name)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://modthesims.info/",
        }

        resp = http_session.get(url, stream=True, timeout=30, headers=headers)
        if resp.status_code != 200:
            return False, f"Échec du téléchargement MTS (Code HTTP {resp.status_code})"

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
            logger.info(f"Fichier MTS téléchargé avec succès: {target_file.name} ({downloaded} octets)")
            return True, f"Téléchargement réussi ({downloaded} octets)."

        return False, "Le fichier téléchargé est vide."
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement MTS sur {url}: {e}", exc_info=True)
        return False, str(e)

