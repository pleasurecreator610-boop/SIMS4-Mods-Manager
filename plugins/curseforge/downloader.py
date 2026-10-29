"""
CurseForge Downloader: Resolving and streaming mod archives from CurseForge and ForgeCDN.
"""

from pathlib import Path
import re
from typing import Callable, Optional, Tuple
from bs4 import BeautifulSoup
import requests

from plugins.curseforge.parsers import extract_project_and_file_ids
from src.utils.logger import logger
from src.utils.network import stream_download


def download_curseforge_file(
    download_url: Optional[str] = None,
    dest_path: Optional[Path] = None,
    session: Optional[requests.Session] = None,
    base_url: str = "https://www.curseforge.com",
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
    **kwargs,
) -> Tuple[bool, str]:
    """Downloads a CurseForge mod archive resolving `/api/v1/mods/{projectId}/files/{fileId}/download`

    towards edge.forgecdn.net.
    """
    target_url = download_url or kwargs.get("mod_url", "")
    target_path_raw = dest_path or kwargs.get("dest_folder") or kwargs.get("dest_path")
    if not target_url or not target_path_raw:
        return False, "URL de téléchargement ou chemin de destination manquant."

    target_path = Path(target_path_raw)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if session is None:
        session = requests.Session()

    try:
        if progress_callback:
            progress_callback(5, "Connexion à CurseForge...", "Résolution de l'archive sur ForgeCDN...")

        resolved_api_url = target_url
        if "/api/v1/mods/" not in target_url and "forgecdn.net" not in target_url:
            page_url = re.sub(r"/(?:download|install|files)(?:/\d+)?/?$", "", target_url.split("?")[0])
            m_fid = re.search(r"/(?:download|install|files)/(\d+)", target_url)
            explicit_fid = m_fid.group(1) if m_fid else None

            page_resp = session.get(page_url, timeout=20)
            if page_resp.status_code != 200:
                return False, f"Impossible de charger la page CurseForge (HTTP {page_resp.status_code})"

            soup = BeautifulSoup(page_resp.text, "html.parser")
            project_id, detected_fid = extract_project_and_file_ids(soup, page_resp.text)
            file_id = explicit_fid or detected_fid
            if not project_id or not file_id:
                return False, "Impossible d'extraire Project ID / File ID depuis la page CurseForge."
            resolved_api_url = f"{base_url}/api/v1/mods/{project_id}/files/{file_id}/download"

        resp = session.get(resolved_api_url, stream=True, timeout=180, allow_redirects=True)
        if resp.status_code != 200:
            return False, f"Échec du téléchargement CurseForge (Code HTTP {resp.status_code})"

        content_type = resp.headers.get("Content-Type", "").lower()
        content_disp = resp.headers.get("Content-Disposition", "").lower()
        if "html" not in content_type or "attachment" in content_disp or "filename=" in content_disp:
            if isinstance(getattr(resp, "content", None), (bytes, bytearray)) and len(resp.content) > 0:
                target_path.write_bytes(resp.content)
                if progress_callback:
                    progress_callback(100, "Téléchargement CurseForge terminé", target_path.name)
                return True, str(target_path)
            return stream_download(resp, target_path, progress_callback, "Téléchargement CurseForge")

        return False, "La réponse CurseForge n'est pas une archive binaire valide."
    except Exception as e:
        logger.error(f"Exception lors du téléchargement CurseForge ({target_url}): {e}", exc_info=True)
        return False, str(e)
