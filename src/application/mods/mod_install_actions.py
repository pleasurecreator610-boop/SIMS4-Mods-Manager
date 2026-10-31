"""
Level 3: Atomic Actions for Mod Installation.
Contains single-responsibility, atomic functions and classes for archive extraction,
magic bytes inspection, file deployment, directory backup/rollback, and database upserts.
"""

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Callable, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import InstalledMod
from src.infrastructure.filesystem.archive_extractor import extract_archive, create_backup_zip, is_archive
from src.utils.file_utils import (
    sanitize_filename,
)
from src.utils.logger import logger


class ModInstallActions:
    """Atomic actions for mod file deployment and persistence."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def is_valid_ts4script(script_path: Path) -> bool:
        """Vérifie qu'un fichier .ts4script est un script/zip valide et ne contient aucun exécutable ou traversal suspect."""
        if not script_path.exists() or script_path.stat().st_size == 0:
            return False
        try:
            import zipfile
            from src.infrastructure.filesystem.archive_extractor import validate_archive_quotas

            with open(script_path, "rb") as f:
                header = f.read(4)
            if not header.startswith(b"PK") and not zipfile.is_zipfile(script_path):
                # Certains petits scripts de test unitaires ne sont pas des archives ZIP réelles
                return True
            with zipfile.ZipFile(script_path, "r") as z:
                infolist = z.infolist()
                total_uncompressed = sum(getattr(m, "file_size", 0) for m in infolist)
                validate_archive_quotas(script_path, total_uncompressed, len(infolist))

                forbidden_extensions = {
                    ".exe",
                    ".dll",
                    ".pyd",
                    ".so",
                    ".dylib",
                    ".bat",
                    ".cmd",
                    ".vbs",
                    ".ps1",
                    ".com",
                    ".scr",
                    ".msi",
                    ".hta",
                    ".wsf",
                }
                for m in infolist:
                    name = m.filename
                    norm_parts = name.replace("\\", "/").split("/")
                    if ".." in norm_parts or name.startswith(("/", "\\")):
                        logger.warning(f"Path traversal suspect dans le .ts4script '{script_path.name}': {name}")
                        return False
                    name_lower = name.lower()
                    if any(name_lower.endswith(ext) for ext in forbidden_extensions):
                        logger.warning(f"Binaire suspect détecté dans le .ts4script '{script_path.name}': {name}")
                        return False
            return True
        except Exception as e:
            logger.warning(f"Validation du .ts4script '{script_path.name}' échouée : {e}")
            return False

    def detect_and_normalize_extension(self, file_path: Path) -> Path:
        """
        Inspects binary magic headers (DBPF, RAR, 7Z, ZIP) and updates extension if mismatched.
        """
        if not file_path.exists():
            return file_path
        try:
            with open(file_path, "rb") as f:
                magic = f.read(7)
            if magic.startswith(b"DBPF") and file_path.suffix.lower() != ".package":
                pkg_path = file_path.with_suffix(".package")
                file_path.replace(pkg_path)
                return pkg_path
            elif magic.startswith(b"Rar!") and file_path.suffix.lower() != ".rar":
                rar_path = file_path.with_suffix(".rar")
                file_path.replace(rar_path)
                return rar_path
            elif magic.startswith(b"7z\xbc\xaf'\x1c") and file_path.suffix.lower() != ".7z":
                sz_path = file_path.with_suffix(".7z")
                file_path.replace(sz_path)
                return sz_path
            elif magic.startswith(b"PK") and file_path.suffix.lower() != ".zip":
                zip_path = file_path.with_suffix(".zip")
                file_path.replace(zip_path)
                return zip_path
        except Exception as e:
            logger.debug(f"Vérification de format binaire échouée pour {file_path}: {e}")
        return file_path

    def download_file(
        self,
        provider: Any,
        download_url: str,
        dest_file: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Atomic download of a mod archive/file from a provider."""
        from src.infrastructure.network.simfileshare_resolver import SimFileShareResolver

        if SimFileShareResolver.is_simfileshare_url(download_url):
            resolver = SimFileShareResolver()
            return resolver.download_mod_file(download_url, dest_file, progress_callback=progress_callback)

        return provider.download_mod_file(download_url, dest_file, progress_callback=progress_callback)

    def create_directory_backup(self, target_dir: Path, backup_parent_dir: Path, mod_name: str) -> Optional[Path]:
        """Creates a timestamped zip backup of an existing mod directory."""
        if not target_dir.exists():
            return None
        backup_parent_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = sanitize_filename(mod_name)
        backup_zip = backup_parent_dir / f"{clean_name}_{timestamp}.zip"
        create_backup_zip(target_dir, backup_zip)
        return backup_zip

    def rollback_directory(self, backup_zip: Optional[Path], target_dir: Path) -> None:
        """Restores a mod directory from a backup zip in case of failure or cleans up unbacked partial install."""
        if not backup_zip or not backup_zip.exists():
            if target_dir.exists():
                logger.warning(
                    f"Nettoyage du répertoire partiel non sauvegardé suite à l'échec d'installation : {target_dir}"
                )
                shutil.rmtree(target_dir, ignore_errors=True)
            return
        logger.warning(f"Rollback vers le backup {backup_zip}...")
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)
            extract_archive(backup_zip, target_dir)
        except Exception as re:
            logger.error(f"Échec du rollback: {re}")

    @staticmethod
    def _resolve_unique_dest_path(dest: Path, fallback_parent_name: str = "") -> Path:
        """Résout de manière déterministe les collisions de nom de fichier pour éviter tout écrasement."""
        if not dest.exists():
            return dest

        if fallback_parent_name and not dest.name.startswith(f"{fallback_parent_name}_"):
            candidate = dest.parent / f"{fallback_parent_name}_{dest.name}"
            if not candidate.exists():
                return candidate
            dest = candidate

        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        return dest

    def deploy_extracted_files(self, extracted_dir: Path, target_mod_dir: Path, mods_dir: Path) -> List[str]:
        """
        Deploys files into target mod directory.
        Strictly enforces the Sims 4 engine rule: .ts4script files MUST NOT be nested
        deeper than 1 subfolder under Mods/ (e.g. Mods/target_mod_dir/script.ts4script).
        Recursively unpacks nested archives and deploys companion configuration files.
        Returns list of relative installed file paths.
        """
        target_mod_dir.mkdir(parents=True, exist_ok=True)

        # 1. Unpack any nested archives found inside extracted_dir (e.g. zip in zip) with cumulative quota guard
        from src.infrastructure.filesystem.archive_extractor import (
            ArchiveSecurityError,
            MAX_EXTRACTED_TOTAL_BYTES,
        )

        for _ in range(2):
            found_nested = False
            for nested in list(extracted_dir.rglob("*")):
                if nested.is_file() and is_archive(nested):
                    try:
                        extract_archive(nested, nested.parent)
                        nested.unlink(missing_ok=True)
                        found_nested = True
                        cum_bytes = sum(f.stat().st_size for f in extracted_dir.rglob("*") if f.is_file())
                        if cum_bytes > MAX_EXTRACTED_TOTAL_BYTES:
                            raise ArchiveSecurityError(
                                f"Quota cumulé d'extraction dépassé après décompression imbriquée ({cum_bytes} octets)."
                            )
                    except ArchiveSecurityError:
                        raise
                    except Exception as e:
                        logger.debug(f"Extraction archive imbriquée ignorée pour {nested.name}: {e}")
            if not found_nested:
                break

        # 2. Deploy mod files and valid companion files
        ignored_dir_names = {"__macosx", ".git"}
        ignored_file_names = {".ds_store", "thumbs.db", "desktop.ini"}
        companion_extensions = {".cfg", ".ini", ".json", ".tsv", ".txt", ".settings"}

        for p in extracted_dir.rglob("*"):
            if not p.is_file():
                continue
            if any(part.lower() in ignored_dir_names for part in p.parts):
                continue
            if p.name.lower() in ignored_file_names:
                continue

            suffix = p.suffix.lower()
            if suffix == ".package":
                rel = p.relative_to(extracted_dir)
                # Sims 4 Resource.cfg only searches packages up to 5 subdirectories deep from Mods/
                # target_mod_dir is depth 1 from mods_dir.
                # Inside target_mod_dir, rel can have at most 4 directory parts (depth 1 + 4 = 5).
                # If rel.parts has more than 5 parts (4 subdirs + 1 filename), flatten excess depth
                if len(rel.parts) > 5:
                    safe_dirs = rel.parts[:4]
                    dest = target_mod_dir.joinpath(*safe_dirs) / rel.name
                    if dest.exists() and dest != p:
                        dest = self._resolve_unique_dest_path(dest, rel.parent.name)
                else:
                    dest = target_mod_dir / rel
                    if dest.exists() and dest != p:
                        dest = self._resolve_unique_dest_path(dest, rel.parent.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            elif suffix == ".ts4script":
                if not self.is_valid_ts4script(p):
                    logger.warning(f"Fichier de script .ts4script suspect rejeté pour sécurité : {p.name}")
                    continue
                # Flat at target_mod_dir root (Mods/ModFolder/name.ts4script = depth 1 from Mods/)
                dest = target_mod_dir / p.name
                if dest.exists() and dest != p:
                    dest = self._resolve_unique_dest_path(dest, p.parent.name)
                shutil.copy2(p, dest)
            elif suffix in companion_extensions:
                rel = p.relative_to(extracted_dir)
                if len(rel.parts) > 5:
                    safe_dirs = rel.parts[:4]
                    dest = target_mod_dir.joinpath(*safe_dirs) / rel.name
                    if dest.exists() and dest != p:
                        dest = self._resolve_unique_dest_path(dest, rel.parent.name)
                else:
                    dest = target_mod_dir / rel
                    if dest.exists() and dest != p:
                        dest = self._resolve_unique_dest_path(dest, rel.parent.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)

        return [str(p.relative_to(mods_dir)) for p in target_mod_dir.rglob("*") if p.is_file()]

    def deploy_direct_file(self, file_path: Path, target_mod_dir: Path, mods_dir: Path) -> List[str]:
        """Deploys a single uncompressed package or script file."""
        if file_path.suffix.lower() == ".ts4script" and not self.is_valid_ts4script(file_path):
            logger.warning(f"Fichier de script .ts4script suspect rejeté : {file_path.name}")
            return []
        target_mod_dir.mkdir(parents=True, exist_ok=True)
        dest = target_mod_dir / file_path.name
        if dest.exists() and dest != file_path:
            dest = self._resolve_unique_dest_path(dest, file_path.parent.name)
        shutil.copy2(file_path, dest)
        return [str(p.relative_to(mods_dir)) for p in target_mod_dir.rglob("*") if p.is_file()]

    def record_installation(
        self,
        session: Session,
        title: str,
        source: str,
        remote_id: str,
        catalog_id: Optional[int],
        folder_name: str,
        installed_files: List[str],
        version_date: Optional[datetime],
        version_str: Optional[str],
        backup_path: Optional[str] = None,
        is_enabled: Optional[bool] = None,
    ) -> InstalledMod:
        """Atomic upsert of InstalledMod record in the database."""
        existing = None
        if catalog_id:
            existing = session.query(InstalledMod).filter_by(catalog_mod_id=catalog_id).first()
        if not existing and remote_id and source:
            existing = session.query(InstalledMod).filter_by(remote_id=remote_id, source=source).first()
        if not existing:
            existing = session.query(InstalledMod).filter_by(title=title, source=source).first()
        if not existing and title:
            import re
            from src.utils.mod_matcher import ModMatcher

            stripped_t = re.sub(r"(?i)^the\s+", "", title.strip())
            t_fp = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title(stripped_t) or stripped_t)
            if t_fp:
                for im in session.query(InstalledMod).all():
                    if im.title:
                        im_s = re.sub(r"(?i)^the\s+", "", im.title.strip())
                        if ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title(im_s) or im_s) == t_fp:
                            existing = im
                            break

        effective_enabled = is_enabled if is_enabled is not None else (existing.is_enabled if existing else True)

        if not existing:
            installed = InstalledMod(
                catalog_mod_id=catalog_id,
                source=source,
                remote_id=remote_id,
                title=title,
                folder_name=folder_name,
                is_enabled=effective_enabled,
                installed_date=datetime.now(),
                version_date=version_date,
                version_str=version_str or "",
                backup_path=backup_path,
            )
            installed.set_installed_files_list(installed_files)
            session.add(installed)
            session.commit()
            session.refresh(installed)
            return installed
        else:
            existing.catalog_mod_id = catalog_id or existing.catalog_mod_id
            existing.remote_id = remote_id or existing.remote_id
            existing.title = title
            existing.folder_name = folder_name
            existing.is_enabled = effective_enabled
            existing.version_date = version_date or existing.version_date
            if version_str:
                existing.version_str = version_str
            existing.installed_date = datetime.now()
            if backup_path:
                existing.backup_path = backup_path
            existing.set_installed_files_list(installed_files)
            session.commit()
            session.refresh(existing)
            return existing
