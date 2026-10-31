"""
Downloader pour Nexus Mods (nexusmods.com).
Gère la résolution des liens de téléchargement directs via l'API Nexus Mods v1 ou session membre.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Tuple
import httpx

from src.core.session_manager import SessionManager
from src.utils.logger import logger


def download_nexusmods_file(
    file_id: int,
    mod_id: int,
    target_path: Path,
    game_domain: str = "thesims4",
    download_url: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, str]:
    """
    Télécharge un fichier de mod depuis Nexus Mods en utilisant :
    1. La clé API personnelle (si configurée).
    2. La session membre authentifiée.
    3. Ou l'URL directe fournie.
    """
    try:
        resolved_url = download_url
        saved_cookies = SessionManager.get_saved_cookies("nexusmods")
        api_key = saved_cookies.get("nexusmods_api_key")

        # 1. Résolution via API Nexus Mods v1 si clé API disponible
        if not resolved_url and api_key and file_id and mod_id:
            api_endpoint = (
                f"https://api.nexusmods.com/v1/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json"
            )
            try:
                resp = httpx.get(
                    api_endpoint,
                    headers={"apikey": api_key},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    links = resp.json()
                    if isinstance(links, list) and links:
                        resolved_url = links[0].get("URI")
                        logger.info(f"Lien CDN Nexus Mods obtenu avec succès via clé API: {resolved_url[:60]}...")
            except Exception as e:
                logger.warning(f"Échec de résolution du lien de téléchargement via clé API: {e}")

        # 2. Si aucun lien direct n'a pu être résolu
        if not resolved_url:
            return (
                False,
                "Impossible d'obtenir le lien de téléchargement direct Nexus Mods. "
                "Veuillez connecter votre clé API ou session membre dans Paramètres -> Comptes.",
            )

        # 3. Téléchargement streamé du fichier
        target_path.parent.mkdir(parents=True, exist_ok=True)
        session = SessionManager.get_http_session("nexusmods")

        with session.get(resolved_url, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                return False, f"Erreur HTTP lors du téléchargement: code {resp.status_code}"

            total_bytes = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(target_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_bytes > 0:
                            progress_callback(downloaded, total_bytes)

        if target_path.exists() and target_path.stat().st_size > 0:
            return True, f"Téléchargement réussi : {target_path.name}"
        return False, "Le fichier téléchargé est vide ou introuvable."

    except Exception as e:
        logger.error(f"Erreur lors du téléchargement Nexus Mods: {e}")
        return False, f"Exception téléchargement Nexus Mods: {e}"
