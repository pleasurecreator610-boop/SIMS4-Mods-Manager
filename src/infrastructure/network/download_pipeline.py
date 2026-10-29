"""Pipeline universel et sécurisé de téléchargement de fichiers.

Gère le streaming par blocs de 64 Ko, le calcul d'empreinte SHA-256 à la volée,
la validation anti-SSRF, les fichiers temporaires .part et la notification de progression.
"""

import hashlib
from pathlib import Path
from typing import Callable, Optional, Set
import httpx

from src.infrastructure.network.url_sanitizer import validate_download_url
from src.utils.logger import logger


CHUNK_SIZE: int = 64 * 1024  # 64 Ko


class DownloadSecurityError(ValueError):
    """Exception levée lorsqu'une URL de téléchargement viole les règles de sécurité anti-SSRF."""


class BaseFileDownloader:
    """Gestionnaire de téléchargement streaming universel."""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        allowed_domains: Optional[Set[str]] = None,
        allow_local: bool = False,
    ) -> None:
        self._external_client = client
        self.allowed_domains = allowed_domains
        self.allow_local = allow_local

    def download_file(
        self,
        url: str,
        dest_path: Path,
        headers: Optional[dict[str, str]] = None,
        progress_cb: Optional[Callable[[int, str], None]] = None,
        timeout: float = 60.0,
    ) -> tuple[Path, str]:
        """Télécharge un fichier distant vers dest_path.

        Retourne un tuple (chemin_fichier, sha256_hex).
        """
        if not validate_download_url(url, allowed_domains=self.allowed_domains, allow_local=self.allow_local):
            logger.error(f"URL de téléchargement bloquée pour violation de sécurité : {url}")
            raise DownloadSecurityError(f"URL non autorisée ou suspecte : {url}")

        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = dest_path.with_suffix(dest_path.suffix + ".part")

        sha256 = hashlib.sha256()
        client = self._external_client or httpx.Client(follow_redirects=True, timeout=timeout)
        should_close = self._external_client is None

        try:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                total_bytes = int(response.headers.get("Content-Length", 0))
                downloaded_bytes = 0

                with open(part_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        sha256.update(chunk)
                        downloaded_bytes += len(chunk)

                        if progress_cb and total_bytes > 0:
                            percent = int((downloaded_bytes / total_bytes) * 100)
                            progress_cb(min(percent, 99), dest_path.name)

            if part_path.exists():
                if dest_path.exists():
                    dest_path.unlink()
                part_path.rename(dest_path)

            if progress_cb:
                progress_cb(100, dest_path.name)

            return dest_path, sha256.hexdigest()

        except Exception as e:
            if part_path.exists():
                try:
                    part_path.unlink()
                except Exception:
                    pass
            logger.error(f"Erreur lors du téléchargement de {dest_path.name}: {e}")
            raise
        finally:
            if should_close:
                client.close()
