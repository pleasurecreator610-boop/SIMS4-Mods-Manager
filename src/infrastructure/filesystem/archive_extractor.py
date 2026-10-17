"""Gestionnaire orienté objet d'archives (ZIP, RAR, 7Z).

Implémente le pattern Strategy pour chaque format avec détection automatique
des signatures de fichiers, extraction sécurisée et création de sauvegardes.
"""

import os
from typing import Callable, Optional
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path

from src.utils.logger import logger


class BaseArchiveHandler(ABC):
    """Interface abstraite pour un gestionnaire de format d'archive."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Détermine si le fichier correspond à ce format."""
        ...

    @abstractmethod
    def extract(
        self,
        path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive dans le répertoire cible et retourne la liste des fichiers."""
        ...



class ZipArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives standard ZIP."""

    def can_handle(self, path: Path) -> bool:
        """Exécute l'opération can handle.

        Args:
            path: Paramètre path.

        Returns:
            Résultat de l'opération can_handle.
        """
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header.startswith(b"PK"):
                return zipfile.is_zipfile(path)
        except Exception:
            pass
        if path.suffix.lower() == ".zip":
            try:
                return zipfile.is_zipfile(path)
            except Exception:
                return False
        return False

    def extract(
        self,
        path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait les fichiers de l'archive ZIP avec notification de progression."""
        with zipfile.ZipFile(path, "r") as z:
            members = z.infolist()
            total = len(members)
            if progress_cb and total > 0:
                for idx, member in enumerate(members):
                    try:
                        z.extract(member, dest_dir, filter="data")  # type: ignore[call-arg]
                    except TypeError:
                        z.extract(member, dest_dir)
                    progress_cb(int(((idx + 1) / total) * 100), member.filename)
            else:
                try:
                    z.extractall(dest_dir, filter="data")  # type: ignore[call-arg]
                except TypeError:
                    z.extractall(dest_dir)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class SevenZipArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives 7Z via py7zr."""

    def can_handle(self, path: Path) -> bool:
        """Exécute l'opération can handle."""
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(6)
            if header.startswith(b"7z\xbc\xaf'\x1c"):
                return True
        except Exception:
            pass
        if path.suffix.lower() == ".7z":
            try:
                import py7zr

                return py7zr.is_7zfile(path)
            except Exception:
                return False
        return False

    def extract(
        self,
        path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive 7Z."""
        import py7zr

        with py7zr.SevenZipFile(path, mode="r") as z:
            z.extractall(path=dest_dir)
        if progress_cb:
            progress_cb(100, path.name)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class RarArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives RAR via rarfile."""

    _tool_configured: bool = False

    @classmethod
    def _ensure_tool_configured(cls) -> None:
        """Tente de localiser un exécutable UnRAR ou 7-Zip sur Windows."""
        if cls._tool_configured:
            return
        cls._tool_configured = True
        try:
            import rarfile
            import shutil

            if shutil.which("unrar") or shutil.which("UnRAR.exe") or shutil.which("7z") or shutil.which("7z.exe"):
                return

            candidates = [
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WinRAR" / "UnRAR.exe",
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WinRAR" / "WinRAR.exe",
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "WinRAR" / "UnRAR.exe",
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe",
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "7-Zip" / "7z.exe",
            ]
            for cand in candidates:
                if cand.exists():
                    rarfile.UNRAR_TOOL = str(cand)
                    logger.info(f"Outil d'extraction RAR auto-configuré: {cand}")
                    return
        except Exception as e:
            logger.debug(f"Configuration automatique de l'outil RAR ignorée: {e}")

    def can_handle(self, path: Path) -> bool:
        """Exécute l'opération can handle."""
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(7)
            if header.startswith(b"Rar!\x1a\x07"):
                return True
        except Exception:
            pass
        if path.suffix.lower() == ".rar":
            try:
                import rarfile

                self._ensure_tool_configured()
                return rarfile.is_rarfile(path)
            except Exception:
                return False
        return False

    def extract(
        self,
        path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive RAR."""
        import rarfile

        self._ensure_tool_configured()
        try:
            with rarfile.RarFile(path) as rf:
                rf.extractall(dest_dir)
        except rarfile.RarCannotExec as e:
            logger.error(f"Outil UnRAR manquant pour extraire {path.name}: {e}")
            raise RuntimeError(
                f"Impossible d'extraire l'archive RAR '{path.name}' : aucun utilitaire UnRAR ou 7-Zip n'a été détecté. "
                "Veuillez installer WinRAR ou 7-Zip."
            ) from e
        if progress_cb:
            progress_cb(100, path.name)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class ArchiveExtractor:
    """Façade unifiée pour la détection et l'extraction d'archives tous formats."""

    def __init__(self) -> None:
        self._handlers: list[BaseArchiveHandler] = [
            ZipArchiveHandler(),
            SevenZipArchiveHandler(),
            RarArchiveHandler(),
        ]

    def is_archive(self, file_path: Path) -> bool:
        """Vérifie si le fichier est une archive supportée valide."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            return False

        # Vérification immédiate de signature binaire pour éviter de confondre avec les packages Sims 4 DBPF
        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
            if magic == b"DBPF":
                return False
        except Exception as e:
            logger.debug(f"Erreur lors du test de signature DBPF sur {file_path}: {e}")

        return any(handler.can_handle(file_path) for handler in self._handlers)

    def extract(
        self,
        archive_path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive avec le gestionnaire adéquat avec mécanisme de repli et progression."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        # 1. Tester les gestionnaires dont la signature correspond
        for handler in self._handlers:
            if handler.can_handle(archive_path):
                try:
                    return handler.extract(archive_path, dest_dir, progress_cb=progress_cb)
                except Exception as e:
                    logger.warning(
                        f"Échec de l'extraction avec {handler.__class__.__name__} sur {archive_path.name}: {e}"
                    )
                    errors.append(f"{handler.__class__.__name__}: {e}")

        # 2. Repli : tenter tous les gestionnaires au cas où la signature était atypique
        for handler in self._handlers:
            try:
                extracted = handler.extract(archive_path, dest_dir, progress_cb=progress_cb)
                if extracted:
                    logger.info(
                        f"Extraction réussie avec le gestionnaire de secours {handler.__class__.__name__} sur {archive_path.name}"
                    )
                    return extracted
            except Exception:
                continue

        error_detail = " | ".join(errors) if errors else "Format d'archive non supporté"
        raise ValueError(f"Impossible d'extraire l'archive '{archive_path.name}': {error_detail}")

    async def extract_async(
        self,
        archive_path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive de manière asynchrone hors de la boucle principale (sans bloquer le GIL)."""
        import asyncio

        return await asyncio.to_thread(self.extract, archive_path, dest_dir, progress_cb)

    def create_backup(self, source_dir: Path, backup_zip_path: Path) -> Path:
        """Crée une archive ZIP de sauvegarde du répertoire source."""
        backup_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(backup_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    z.write(file_path, arcname)
        return backup_zip_path


# Instance singleton réutilisable
_default_extractor = ArchiveExtractor()


def is_archive(file_path: Path) -> bool:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.is_archive(file_path)


def extract_archive(
    archive_path: Path,
    dest_dir: Path,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> list[Path]:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.extract(archive_path, dest_dir, progress_cb=progress_cb)



def create_backup_zip(source_dir: Path, backup_zip_path: Path) -> Path:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.create_backup(source_dir, backup_zip_path)
