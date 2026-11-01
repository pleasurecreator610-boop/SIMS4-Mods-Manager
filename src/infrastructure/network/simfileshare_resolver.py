"""
SimFileShare Universal Resolver & Direct Downloader.
Gère la détection, la résolution de liens directs, l'extraction de métadonnées
et le streaming haute performance pour simfileshare.net (fichiers uniques et dossiers).
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional, Tuple
from bs4 import BeautifulSoup

from src.core.session_manager import SessionManager
from src.infrastructure.network.base_downloader import BaseDownloader, is_safe_download_url
from src.infrastructure.network.download_pipeline import CHUNK_SIZE
from src.utils.logger import logger


class SimFileShareResolver(BaseDownloader):
    """Résolveur et téléchargeur universel pour simfileshare.net."""

    BASE_URL = "https://simfileshare.net"
    SFS_DOMAINS = ("simfileshare.net", "www.simfileshare.net")

    @classmethod
    def is_simfileshare_url(cls, url: str) -> bool:
        """Détermine si une URL pointe vers le domaine simfileshare.net."""
        if not url:
            return False
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc.lower() in cls.SFS_DOMAINS
        except Exception:
            return False

    @classmethod
    def extract_file_id(cls, url: str) -> Optional[str]:
        """Extrait l'ID numérique d'un fichier hébergé sur SimFileShare."""
        if not url:
            return None
        m = re.search(r"/(?:download|filedetails)/(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"[?&]file=(\d+)", url)
        if m:
            return m.group(1)
        return None

    @classmethod
    def extract_folder_id(cls, url: str) -> Optional[str]:
        """Extrait l'identifiant d'un dossier partagé SimFileShare."""
        if not url:
            return None
        m = re.search(r"/folder/(\d+)", url)
        if m:
            return m.group(1)
        return None

    @classmethod
    def resolve_direct_download(
        cls,
        url: str,
        timeout: float = 20.0,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        Résout une URL SimFileShare vers son lien direct de streaming binaire.
        Retourne (direct_url, filename, size_bytes).
        """
        if not cls.is_simfileshare_url(url):
            return None, None, None

        session = SessionManager.get_http_session("simfileshare")
        file_id = cls.extract_file_id(url)
        clean_url = f"https://simfileshare.net/download/{file_id}/" if file_id else url

        try:
            # 1. Requête GET pour analyser les headers et la page de téléchargement
            resp = session.get(clean_url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f"SimFileShare a retourné le code HTTP {resp.status_code} pour {clean_url}")
                return None, None, None

            content_disp = resp.headers.get("Content-Disposition", "")
            filename = None
            if "filename=" in content_disp:
                match = re.search(r'filename=["\']?([^"\';]+)["\']?', content_disp)
                if match:
                    filename = match.group(1)

            # Si le contenu est directement binaire
            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                size = int(resp.headers.get("Content-Length", 0)) or None
                return str(resp.url), filename, size

            # 2. Parsing HTML pour extraire le bouton direct ou le lien ?dl
            soup = BeautifulSoup(resp.text, "html.parser")
            direct_link = None

            # Chercher <a href="...download/.../?dl"> ou lien contenant /download/
            for a in soup.find_all("a", href=True):
                href = str(a.get("href") or "")
                if "/download/" in href and (file_id in href if file_id else True):
                    direct_link = urllib.parse.urljoin(cls.BASE_URL, href)
                    if not filename:
                        txt = a.get_text(strip=True)
                        if any(ext in txt.lower() for ext in [".package", ".ts4script", ".zip", ".rar", ".7z"]):
                            filename = txt
                    break

            if not direct_link and file_id:
                # Format standard direct SimFileShare
                direct_link = f"https://simfileshare.net/download/{file_id}/?dl"

            if not filename:
                # Chercher le titre du fichier dans le DOM
                h_title = soup.find(["h3", "h2", "h4", "h1", "p"])
                if h_title:
                    cand = h_title.get_text(strip=True)
                    if any(ext in cand.lower() for ext in [".package", ".ts4script", ".zip", ".rar", ".7z"]):
                        filename = cand

            return direct_link or clean_url, filename, None

        except Exception as e:
            logger.error(f"Erreur lors de la résolution SimFileShare pour {url}: {e}")
            return None, None, None

    def download_mod_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> Tuple[bool, str]:
        """
        Télécharge un fichier depuis SimFileShare de manière résiliente avec streaming et callback.
        """
        safe, reason = is_safe_download_url(url, allow_local_for_testing=True)
        if not safe:
            return False, reason

        direct_url, detected_name, _ = self.resolve_direct_download(url, timeout=timeout)
        target_url = direct_url or url

        session = SessionManager.get_http_session("simfileshare")
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = dest_path.with_suffix(dest_path.suffix + ".part")

        if progress_callback:
            progress_callback(10, "Connexion à SimFileShare...", dest_path.name)

        try:
            with session.get(target_url, stream=True, timeout=timeout) as resp:
                if resp.status_code != 200:
                    return False, f"Code HTTP {resp.status_code} reçu de SimFileShare"

                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(part_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            pct = min(int((downloaded / total_size) * 90) + 10, 99)
                            progress_callback(pct, "Téléchargement en cours...", dest_path.name)

            if part_path.exists():
                if dest_path.exists():
                    dest_path.unlink()
                part_path.rename(dest_path)

            if progress_callback:
                progress_callback(100, "Téléchargement terminé avec succès.", dest_path.name)

            return True, str(dest_path)

        except Exception as e:
            if part_path.exists():
                try:
                    part_path.unlink()
                except Exception:
                    pass
            logger.error(f"Échec du téléchargement SimFileShare ({url}): {e}")
            return False, str(e)
