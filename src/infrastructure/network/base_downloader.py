"""Classe de base abstraite et utilitaires de streaming pour les téléchargeurs réseau."""

from __future__ import annotations

import hashlib
import ipaddress
import shutil
import time
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Tuple

from src.utils.logger import logger

# Quota maximal de téléchargement par mod (4 Gio)
MAX_DOWNLOAD_FILE_SIZE: int = 4 * 1024 * 1024 * 1024  # 4 GiB

FORBIDDEN_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud metadata (AWS, GCP, Azure)
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_safe_download_url(url: str, allow_local_for_testing: bool = True) -> Tuple[bool, str]:
    """Valide qu'une URL cible est sécurisée contre les attaques SSRF (Server-Side Request Forgery)."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Schéma d'URL interdit '{parsed.scheme}'. Seuls http et https sont autorisés."

        hostname = parsed.hostname
        if not hostname:
            return False, "Nom d'hôte manquant dans l'URL."

        # Vérifier si l'hôte est une adresse IP
        try:
            ip = ipaddress.ip_address(hostname)
            if not allow_local_for_testing:
                for net in FORBIDDEN_IP_NETWORKS:
                    if ip in net:
                        return False, f"Accès interdit aux adresses IP privées ou de métadonnées ({ip})."
        except ValueError:
            if hostname.lower() in ("localhost", "metadata.google.internal") and not allow_local_for_testing:
                return False, f"Hôte restreint non autorisé '{hostname}'."

        return True, ""
    except Exception as e:
        return False, f"URL invalide : {e}"


class BaseDownloader(ABC):
    """Classe de base abstraite pour le téléchargement robuste de fichiers et d'archives."""

    @abstractmethod
    def download_mod_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        """Télécharge un mod depuis une URL distante vers une destination locale."""
        ...

    @staticmethod
    def stream_to_file(
        response,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        phase_label: str = "Téléchargement",
        chunk_size: int = 65536,
        compute_sha256: bool = True,
    ) -> Tuple[bool, str, Optional[str]]:
        """Écrit un flux HTTP vers le disque avec calcul de vitesse, progression et hash SHA-256."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        total_size = int(response.headers.get("Content-Length") or 0)

        # Contrôle du quota de taille maximale (protection contre déni de service / saturation disque)
        if total_size > MAX_DOWNLOAD_FILE_SIZE:
            err = f"Fichier trop volumineux ({total_size // (1024 * 1024)} Mo > {MAX_DOWNLOAD_FILE_SIZE // (1024 * 1024)} Mo autorisés)."
            logger.error(err)
            return False, err, None

        # Taille de chunk adaptative pour booster la vitesse sur les fichiers volumineux
        if total_size > 100 * 1024 * 1024 and chunk_size == 65536:
            chunk_size = 524288  # 512 Ko
        elif total_size > 20 * 1024 * 1024 and chunk_size == 65536:
            chunk_size = 131072  # 128 Ko

        # Vérification de l'espace disque disponible
        if total_size > 0:
            free_bytes = shutil.disk_usage(dest_path.parent).free
            if free_bytes < (total_size + 10 * 1024 * 1024):
                err = f"Espace disque insuffisant ({free_bytes // (1024 * 1024)} Mo disponibles, {total_size // (1024 * 1024)} Mo requis)."
                logger.error(err)
                return False, err, None

        downloaded = 0
        start_time = time.time()
        last_log_time = start_time
        sha256_hasher = hashlib.sha256() if compute_sha256 else None

        try:
            with open(dest_path, "wb") as f:
                if hasattr(response, "iter_content"):
                    chunk_iterator = response.iter_content(chunk_size=chunk_size)
                elif hasattr(response, "iter_bytes"):
                    chunk_iterator = response.iter_bytes(chunk_size=chunk_size)
                else:
                    data = response.content
                    f.write(data)
                    if sha256_hasher:
                        sha256_hasher.update(data)
                    return True, "Téléchargement terminé.", sha256_hasher.hexdigest() if sha256_hasher else None

                for chunk in chunk_iterator:
                    if not chunk:
                        continue
                    f.write(chunk)
                    if sha256_hasher:
                        sha256_hasher.update(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed = max(now - start_time, 0.001)
                    speed_mbps = (downloaded / elapsed) / (1024 * 1024)

                    if now - last_log_time >= 0.2:
                        last_log_time = now
                        if total_size > 0:
                            percent = min(int((downloaded / total_size) * 100), 100)
                            rem_bytes = max(total_size - downloaded, 0)
                            rem_sec = (rem_bytes / (downloaded / elapsed)) if downloaded > 0 else 0
                            eta_str = f"{int(rem_sec)}s restante(s)" if rem_sec < 3600 else f"{int(rem_sec / 60)}m"
                            detail_str = (
                                f"{downloaded // (1024 * 1024)} Mo / {total_size // (1024 * 1024)} Mo "
                                f"({speed_mbps:.1f} Mo/s) — {eta_str}"
                            )
                        else:
                            percent = -1
                            detail_str = f"{downloaded // (1024 * 1024)} Mo ({speed_mbps:.1f} Mo/s)"

                        if progress_callback:
                            progress_callback(percent, phase_label, detail_str)

            if total_size > 0 and downloaded < total_size:
                err = f"Téléchargement incomplet ({downloaded}/{total_size} octets)."
                logger.error(err)
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except Exception:
                        pass
                return False, err, None

            digest = sha256_hasher.hexdigest() if sha256_hasher else None
            return True, "Téléchargement terminé avec succès.", digest

        except Exception as e:
            logger.error(f"Erreur d'écriture durant le streaming de téléchargement : {e}")
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            return False, f"Erreur de flux réseau : {e}", None
