"""
Downloader pour Maxis Match CC World (maxismatchccworld.tumblr.com).
Achemine automatiquement les liens cibles vers le résolveur SimFileShare,
le gestionnaire Patreon ou le téléchargement direct.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from src.core.session_manager import SessionManager
from src.infrastructure.network.simfileshare_resolver import SimFileShareResolver
from src.utils.logger import logger


def download_mmccworld_file(
    file_info: Any,
    dest_path: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, str]:
    """
    Télécharge une création répertoriée sur Maxis Match CC World.
    Résout automatiquement les liens SimFileShare, Patreon et directs.
    """
    try:
        url = ""
        if isinstance(file_info, dict):
            url = file_info.get("url") or file_info.get("download_url") or ""
        elif isinstance(file_info, str):
            url = file_info

        if not url:
            return False, "Aucune URL de téléchargement fournie."

        # 1. Routage vers le résolveur universel SimFileShare
        if "simfileshare.net" in url.lower():
            logger.info(f"Routage vers le résolveur SimFileShare pour: {url}")
            ok_res, direct_url, res_msg = SimFileShareResolver.resolve_direct_download(url)
            if not ok_res or not direct_url:
                return False, f"Échec de résolution du lien SimFileShare ({res_msg})."
            url = direct_url

        # 2. Téléchargement streamé
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        session = SessionManager.get_http_session("mmccworld")

        with session.get(url, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                return False, f"Erreur HTTP lors du téléchargement: code {resp.status_code}"

            total_bytes = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_bytes > 0:
                            progress_callback(downloaded, total_bytes)

        if dest_path.exists() and dest_path.stat().st_size > 0:
            return True, f"Téléchargement réussi : {dest_path.name}"
        return False, "Le fichier téléchargé est vide ou introuvable."

    except Exception as e:
        logger.error(f"Erreur téléchargement MMCCWorld: {e}")
        return False, f"Exception téléchargement MMCCWorld: {e}"
