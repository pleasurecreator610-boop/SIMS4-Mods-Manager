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

# Seuils de sécurité contre les décompressions abusives (Zip Bomb / OOM / saturation disque)
MAX_EXTRACTED_TOTAL_BYTES: int = 8 * 1024 * 1024 * 1024  # 8 Gio
MAX_ARCHIVE_FILE_COUNT: int = 10_000
MAX_COMPRESSION_RATIO: float = 100.0

# Extensions exécutables ou scripts interdits à l'extraction dans le dossier Mods des Sims 4
DANGEROUS_EXTENSIONS: set[str] = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".application",
    ".gadget", ".msi", ".msp", ".vbs", ".vbe", ".js", ".jse", ".ws",
    ".wsf", ".wsc", ".wsh", ".ps1", ".ps1xml", ".ps2", ".ps2xml",
    ".psc1", ".psc2", ".msh", ".msh1", ".msh2", ".mshxml", ".msh1xml",
    ".msh2xml", ".reg", ".dll",
}


class ArchiveSecurityError(ValueError):
    """Exception levée lorsqu'une archive viole une règle de sécurité (Zip Bomb ou Path Traversal)."""


def validate_archive_quotas(
    archive_path: Path,
    total_uncompressed_bytes: int,
    file_count: int,
) -> None:
    """Valide les quotas d'extraction contre les décompressions explosives (Zip Bombs)."""
    if file_count > MAX_ARCHIVE_FILE_COUNT:
        logger.warning(
            f"Extraction bloquée : nombre d'entrées ({file_count} > {MAX_ARCHIVE_FILE_COUNT}) pour {archive_path.name}"
        )
        raise ArchiveSecurityError(
            f"L'archive contient un nombre excessif de fichiers ({file_count} > {MAX_ARCHIVE_FILE_COUNT})."
        )

    if total_uncompressed_bytes > MAX_EXTRACTED_TOTAL_BYTES:
        logger.warning(
            f"Extraction bloquée : volume décompressé trop volumineux ({total_uncompressed_bytes} octets) pour {archive_path.name}"
        )
        raise ArchiveSecurityError(
            f"L'archive dépasse la taille décompressée autorisée ({total_uncompressed_bytes // (1024 * 1024)} Mo > {MAX_EXTRACTED_TOTAL_BYTES // (1024 * 1024)} Mo)."
        )

    try:
        compressed_size = archive_path.stat().st_size
    except Exception:
        compressed_size = 0

    if compressed_size > 0 and total_uncompressed_bytes > 10 * 1024 * 1024:
        ratio = total_uncompressed_bytes / compressed_size
        if ratio > MAX_COMPRESSION_RATIO:
            logger.warning(
                f"Zip Bomb suspectée : ratio {ratio:.1f}:1 dépasse le seuil {MAX_COMPRESSION_RATIO}:1 pour {archive_path.name}"
            )
            raise ArchiveSecurityError(
                f"Ratio de décompression anormal détecté ({ratio:.1f}:1). Extraction bloquée pour sécurité."
            )


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
        """Extrait les fichiers de l'archive ZIP de façon sécurisée (anti-Zip Slip) avec notification de progression."""
        resolved_dest = dest_dir.resolve()
        with zipfile.ZipFile(path, "r") as z:
            members = z.infolist()
            safe_members = []
            for m in members:
                if Path(m.filename).suffix.lower() in DANGEROUS_EXTENSIONS:
                    logger.warning(f"Exécutable ou script non autorisé bloqué dans l'archive ZIP : {m.filename}")
                    continue
                target_path = (dest_dir / m.filename).resolve()
                if target_path == resolved_dest or resolved_dest in target_path.parents:
                    safe_members.append(m)
                else:
                    logger.warning(f"Zip Slip bloqué pour le fichier : {m.filename}")

            total = len(safe_members)
            total_uncompressed = sum(getattr(m, "file_size", 0) for m in safe_members)
            validate_archive_quotas(path, total_uncompressed, total)

            for idx, member in enumerate(safe_members):
                try:
                    z.extract(member, dest_dir, filter="data")  # type: ignore[call-arg]
                except TypeError:
                    z.extract(member, dest_dir)
                if progress_cb and total > 0:
                    progress_cb(int(((idx + 1) / total) * 100), member.filename)
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
        """Extrait l'archive 7Z de façon sécurisée (anti-Path Traversal)."""
        import py7zr

        resolved_dest = dest_dir.resolve()
        with py7zr.SevenZipFile(path, mode="r") as z:
            names = z.getnames()
            total_entries = len(names)
            total_bytes = 0
            try:
                info = z.archiveinfo()
                total_bytes = getattr(info, "uncompressed", 0) or 0
            except Exception:
                total_bytes = 0
            validate_archive_quotas(path, total_bytes, total_entries)

            for name in names:
                target_path = (dest_dir / name).resolve()
                if target_path != resolved_dest and resolved_dest not in target_path.parents:
                    logger.warning(f"7Z path traversal bloqué pour le fichier : {name}")
                    raise ArchiveSecurityError(f"Évasion de chemin interdite dans l'archive 7Z : {name}")
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
        """Extrait l'archive RAR de façon sécurisée (anti-Path Traversal)."""
        import rarfile

        self._ensure_tool_configured()
        try:
            resolved_dest = dest_dir.resolve()
            with rarfile.RarFile(path) as rf:
                infolist = rf.infolist()
                total_rar_bytes = sum(getattr(m, "file_size", 0) for m in infolist)
                validate_archive_quotas(path, total_rar_bytes, len(infolist))

                for m in infolist:
                    target_path = (dest_dir / m.filename).resolve()
                    if target_path != resolved_dest and resolved_dest not in target_path.parents:
                        logger.warning(f"RAR path traversal bloqué pour le fichier : {m.filename}")
                        raise ArchiveSecurityError(f"Évasion de chemin interdite dans l'archive RAR : {m.filename}")
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

    def _sanitize_extracted_dir(self, dest_dir: Path) -> list[Path]:
        """Élimine tout fichier exécutable ou script système dangereux extrait par inadvertance."""
        for p in list(dest_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in DANGEROUS_EXTENSIONS:
                try:
                    p.unlink()
                    logger.warning(f"Fichier dangereux neutralisé et supprimé : {p.name}")
                except Exception:
                    pass
        return [p for p in dest_dir.rglob("*") if p.is_file()]

    def extract(
        self,
        archive_path: Path,
        dest_dir: Path,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> list[Path]:
        """Extrait l'archive avec le gestionnaire adéquat avec mécanisme de repli, progression et assainissement."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        # 1. Tester les gestionnaires dont la signature correspond
        for handler in self._handlers:
            if handler.can_handle(archive_path):
                try:
                    handler.extract(archive_path, dest_dir, progress_cb=progress_cb)
                    return self._sanitize_extracted_dir(dest_dir)
                except ArchiveSecurityError:
                    raise
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
                    return self._sanitize_extracted_dir(dest_dir)
            except ArchiveSecurityError:
                raise
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
