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

from src.database.manager import DatabaseManager
from src.database.models import InstalledMod
from src.utils.archive import extract_archive, create_backup_zip, is_archive
from src.utils.file_utils import (
    sanitize_filename,
)
from src.utils.logger import logger


class ModInstallActions:
    """Atomic actions for mod file deployment and persistence."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

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
        return provider.download_mod_file(download_url, dest_file, progress_callback=progress_callback)

    def create_directory_backup(
        self, target_dir: Path, backup_parent_dir: Path, mod_name: str
    ) -> Optional[Path]:
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
        """Restores a mod directory from a backup zip in case of failure."""
        if not backup_zip or not backup_zip.exists():
            return
        logger.warning(f"Rollback vers le backup {backup_zip}...")
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)
            extract_archive(backup_zip, target_dir)
        except Exception as re:
            logger.error(f"Échec du rollback: {re}")

    def deploy_extracted_files(
        self, extracted_dir: Path, target_mod_dir: Path, mods_dir: Path
    ) -> List[str]:
        """
        Deploys files into target mod directory.
        Strictly enforces the Sims 4 engine rule: .ts4script files MUST NOT be nested
        deeper than 1 subfolder under Mods/ (e.g. Mods/target_mod_dir/script.ts4script).
        Recursively unpacks nested archives and deploys companion configuration files.
        Returns list of relative installed file paths.
        """
        target_mod_dir.mkdir(parents=True, exist_ok=True)

        # 1. Unpack any nested archives found inside extracted_dir (e.g. zip in zip)
        for _ in range(2):
            found_nested = False
            for nested in list(extracted_dir.rglob("*")):
                if nested.is_file() and is_archive(nested):
                    try:
                        nested_dest = nested.parent / f"_nested_{nested.stem}"
                        extract_archive(nested, nested_dest)
                        nested.unlink(missing_ok=True)
                        found_nested = True
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
                dest = target_mod_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            elif suffix == ".ts4script":
                # Flat at target_mod_dir root (Mods/ModFolder/name.ts4script = depth 1 from Mods/)
                dest = target_mod_dir / p.name
                shutil.copy2(p, dest)
            elif suffix in companion_extensions:
                rel = p.relative_to(extracted_dir)
                dest = target_mod_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)

        return [str(p.relative_to(mods_dir)) for p in target_mod_dir.rglob("*") if p.is_file()]

    def deploy_direct_file(
        self, file_path: Path, target_mod_dir: Path, mods_dir: Path
    ) -> List[str]:
        """Deploys a single uncompressed package or script file."""
        target_mod_dir.mkdir(parents=True, exist_ok=True)
        dest = target_mod_dir / file_path.name
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
    ) -> InstalledMod:
        """Atomic upsert of InstalledMod record in the database."""
        existing = None
        if catalog_id:
            existing = session.query(InstalledMod).filter_by(catalog_mod_id=catalog_id).first()
        if not existing and remote_id and source:
            existing = session.query(InstalledMod).filter_by(remote_id=remote_id, source=source).first()
        if not existing:
            existing = session.query(InstalledMod).filter_by(title=title, source=source).first()

        if not existing:
            installed = InstalledMod(
                catalog_mod_id=catalog_id,
                source=source,
                remote_id=remote_id,
                title=title,
                folder_name=folder_name,
                is_enabled=True,
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
            existing.is_enabled = True
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
