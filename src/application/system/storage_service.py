"""Service applicatif de gestion de l'espace disque et de maintenance du stockage."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from src.core.config import AppConfig
from src.utils.logger import logger
from src.api.schemas.settings import StorageStatsResponse, StorageCleanupResponse


class StorageService:
    """Analyse l'espace disque utilisé par l'application et effectue des purges sécurisées."""

    @staticmethod
    def _dir_stats(directory: Path) -> Tuple[int, int]:
        """Calcule la taille totale en octets et le nombre de fichiers d'un dossier."""
        if not directory.exists() or not directory.is_dir():
            return 0, 0
        total_bytes = 0
        total_files = 0
        try:
            for p in directory.rglob("*"):
                if p.is_file():
                    try:
                        total_bytes += p.stat().st_size
                        total_files += 1
                    except OSError:
                        pass
        except Exception as e:
            logger.debug(f"Erreur calcul taille {directory}: {e}")
        return total_bytes, total_files

    @classmethod
    def get_storage_stats(cls) -> StorageStatsResponse:
        """Calcule et retourne la répartition de l'espace disque."""
        backups_dir = AppConfig.get_backups_dir()
        cache_dir = AppConfig.get_cache_dir()
        downloads_dir = AppConfig.get_app_dir() / "downloads"

        b_bytes, b_count = cls._dir_stats(backups_dir)
        c_bytes, c_count = cls._dir_stats(cache_dir)
        d_bytes, d_count = cls._dir_stats(downloads_dir)

        total_bytes = b_bytes + c_bytes + d_bytes

        return StorageStatsResponse(
            backups_size_bytes=b_bytes,
            backups_count=b_count,
            cache_size_bytes=c_bytes,
            cache_count=c_count,
            downloads_size_bytes=d_bytes,
            downloads_count=d_count,
            total_size_bytes=total_bytes,
        )

    @classmethod
    def cleanup_storage(
        cls,
        clean_downloads: bool = True,
        clean_cache: bool = True,
    ) -> StorageCleanupResponse:
        """Purge les archives résiduelles et les vignettes pour libérer de l'espace disque."""
        deleted_count = 0
        freed_bytes = 0

        # 1. Nettoyage du dossier temporaire de téléchargements
        if clean_downloads:
            downloads_dir = AppConfig.get_app_dir() / "downloads"
            if downloads_dir.exists() and downloads_dir.is_dir():
                for f in list(downloads_dir.rglob("*")):
                    if f.is_file():
                        try:
                            size = f.stat().st_size
                            f.unlink()
                            deleted_count += 1
                            freed_bytes += size
                        except Exception as e:
                            logger.debug(f"Impossible de supprimer {f}: {e}")

        # 2. Nettoyage du cache de miniatures
        if clean_cache:
            cache_dir = AppConfig.get_cache_dir()
            if cache_dir.exists() and cache_dir.is_dir():
                for f in list(cache_dir.rglob("*")):
                    if f.is_file():
                        try:
                            size = f.stat().st_size
                            f.unlink()
                            deleted_count += 1
                            freed_bytes += size
                        except Exception as e:
                            logger.debug(f"Impossible de supprimer {f}: {e}")

            # Vidage du cache RAM
            try:
                from src.ui.components.image_cache import ImageCache

                ImageCache.clear()
            except Exception:
                pass

        freed_mb = freed_bytes / (1024 * 1024)
        msg = f"Nettoyage terminé : {deleted_count} fichier(s) supprimé(s), {freed_mb:.1f} Mo libéré(s)."
        logger.info(msg)

        return StorageCleanupResponse(
            success=True,
            message=msg,
            deleted_files_count=deleted_count,
            freed_bytes=freed_bytes,
        )
