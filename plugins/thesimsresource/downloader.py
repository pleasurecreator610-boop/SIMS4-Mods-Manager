"""
The Sims Resource (TSR) Downloader: Resolving AJAX download tickets and streaming `.package`/`.zip` archives.
"""

from pathlib import Path
import re
import time
from typing import Callable, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import requests

from plugins.thesimsresource.parsers import extract_item_id
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger
from src.utils.network import stream_download


def download_tsr_file(
    download_url: Optional[str] = None,
    dest_path: Optional[Path] = None,
    session: Optional[requests.Session] = None,
    base_url: str = "https://www.thesimsresource.com",
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ticket_poll_interval: float = 2.5,
    max_ticket_polls: int = 6,
    sleep_fn: Optional[Callable[[float], None]] = None,
    **kwargs,
) -> Tuple[bool, str]:
    """Downloads a TSR mod file via the AJAX ticket sequence:

    1. `/ajax.php?c=downloads&a=initDownload` -> obtains ticket.
    2. Interrogates `/ajax.php?c=downloads&a=getdownloadurl` until signed S3 URL is provided.
    3. Streams binary archive.
    """
    _sleep = sleep_fn or time.sleep
    target_url = download_url or kwargs.get("mod_url", "")
    target_path_raw = dest_path or kwargs.get("dest_folder") or kwargs.get("dest_path")
    if not target_url or not target_path_raw:
        return False, "URL de téléchargement ou chemin de destination manquant."

    if session is None:
        session = requests.Session()

    target_path = Path(target_path_raw)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if progress_callback:
            progress_callback(5, "Connexion à The Sims Resource...", "Initialisation du ticket de téléchargement...")

        final_dl_url = ""
        if "downloads.thesimsresource.com/verify/" in target_url:
            final_dl_url = target_url
        else:
            item_id = extract_item_id(target_url)
            if not item_id:
                page_resp = session.get(target_url, timeout=15)
                if page_resp.status_code == 200:
                    soup = BeautifulSoup(page_resp.text, "html.parser")
                    item_id = extract_item_id(target_url, soup, page_resp.text)
            if not item_id:
                return False, "Impossible d'extraire l'identifiant du mod TSR."

            init_url = f"{base_url}/ajax.php?c=downloads&a=initDownload&itemid={item_id}&setItems=&format=zip"
            init_resp = session.get(init_url, timeout=15)
            if init_resp.status_code != 200:
                return False, f"Échec d'initialisation du ticket TSR (HTTP {init_resp.status_code})"

            init_json = init_resp.json()
            ticket = init_json.get("ticket", "")
            wait_rel_url = init_json.get("url", f"/downloads/download/itemId/{item_id}/ticket/{ticket}")
            if not ticket:
                return False, "Ticket de téléchargement TSR introuvable dans la réponse."

            wait_full_url = urllib.parse.urljoin(base_url, wait_rel_url)
            session.get(wait_full_url, timeout=15)

            get_dl_endpoint = (
                f"{base_url}/ajax.php?c=downloads&a=getdownloadurl&ajax=1&itemid={item_id}&mid=0&lk=0&ticket={ticket}"
            )

            for attempt in range(max_ticket_polls):
                if ShutdownManager.is_shutting_down():
                    return False, "Arrêt de l'application en cours."
                dl_info_resp = session.get(get_dl_endpoint, timeout=15)
                if dl_info_resp.status_code == 200:
                    try:
                        dl_json = dl_info_resp.json()
                        if dl_json.get("url") and not dl_json.get("error"):
                            final_dl_url = str(dl_json["url"])
                            break
                    except Exception:
                        pass
                if attempt < max_ticket_polls - 1 and ticket_poll_interval > 0:
                    if progress_callback:
                        pct = min(20, 6 + (attempt + 1) * 2)
                        progress_callback(
                            pct,
                            "Validation du ticket The Sims Resource...",
                            f"Tentative {attempt + 1}/{max_ticket_polls}",
                        )
                    _sleep(ticket_poll_interval)

            if not final_dl_url:
                return False, "Impossible d'obtenir l'URL finale de téléchargement TSR après expiration du ticket."

        resp = session.get(final_dl_url, stream=True, timeout=180, allow_redirects=True)
        if resp.status_code != 200:
            return False, f"Échec du téléchargement binaire TSR (Code HTTP {resp.status_code})"

        content_type = resp.headers.get("Content-Type", "").lower()
        content_disp = resp.headers.get("Content-Disposition", "")
        content_disp_lower = content_disp.lower()
        if "html" not in content_type or "attachment" in content_disp_lower or "filename=" in content_disp_lower:
            m_fname = re.search(r'filename="?([^";\r\n]+)"?', content_disp, re.IGNORECASE)
            if m_fname:
                raw_fname = Path(m_fname.group(1).strip()).name
                if raw_fname and Path(raw_fname).suffix.lower() in {".package", ".ts4script", ".zip", ".rar", ".7z"}:
                    target_path = target_path.parent / raw_fname
            return stream_download(resp, target_path, progress_callback, "Téléchargement TSR")

        return False, "La réponse TSR n'est pas une archive ou un package binaire valide."
    except Exception as e:
        logger.error(f"Exception lors du téléchargement TSR ({target_url}): {e}", exc_info=True)
        return False, str(e)
