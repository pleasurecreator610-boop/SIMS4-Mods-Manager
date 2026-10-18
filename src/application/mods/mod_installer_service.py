import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable

from src.core.config import AppConfig
from src.database.models import CatalogMod, InstalledMod
from src.database.manager import DatabaseManager
from src.application.game.game_service import GameDetector
from src.utils.logger import logger
from src.application.mods.mod_install_orchestrator import perform_mod_install

from src.utils.file_utils import (
    sanitize_mod_folder_name,
    generate_unique_mod_folder_name,
    sanitize_filename,
)

__all__ = [
    "ModInstaller",
    "perform_mod_install",
    "sanitize_mod_folder_name",
    "generate_unique_mod_folder_name",
    "sanitize_filename",
]


class ModInstaller:
    """Handles mod installation, extraction, ts4script depth fixing, backups, uninstallation, and scanning."""

    @classmethod
    def install_mod_from_file(
        cls,
        file_path: Path,
        catalog_mod: Optional[CatalogMod] = None,
        source: str = "manual",
        custom_title: Optional[str] = None,
        version_date: Optional[datetime] = None,
        version_str: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Installs a mod from a downloaded file (archive or direct package/script) via ModInstallCoordinator."""
        if GameDetector.is_game_running():
            return (
                False,
                "Le jeu Les Sims 4 est actuellement en cours d'exécution. Veuillez fermer le jeu avant d'installer des mods.",
            )

        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir:
            return False, "Dossier Mods de Sims 4 introuvable. Veuillez vérifier vos paramètres."

        from src.application.mods.mod_install_coordinator import ModInstallCoordinator

        coordinator = ModInstallCoordinator()
        return coordinator.coordinate_file_install(
            file_path=file_path,
            mods_dir=mods_dir,
            catalog_mod=catalog_mod,
            source=source,
            custom_title=custom_title,
            version_date=version_date,
            version_str=version_str,
            progress_callback=progress_callback,
        )

    @classmethod
    def _fix_ts4script_depth(cls, mod_dir: Path, mods_root: Path) -> None:
        """Moves any .ts4script files found in deep subfolders directly to mod_dir."""
        for script_file in list(mod_dir.rglob("*.ts4script")):
            if script_file.parent != mod_dir:
                dest = mod_dir / script_file.name
                if dest.exists() and dest != script_file:
                    dest = mod_dir / f"{script_file.stem}_{sanitize_filename(script_file.parent.name)}.ts4script"
                logger.info(f"Relocating .ts4script from depth > 1 to: {dest}")
                shutil.move(str(script_file), str(dest))

    @classmethod
    def uninstall_mod(cls, installed_mod_id: int) -> Tuple[bool, str]:
        """Removes the mod folder and its database record."""
        if GameDetector.is_game_running():
            return False, "Le jeu Les Sims 4 est actuellement en cours d'exécution. Veuillez fermer le jeu avant de désinstaller des mods."

        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            mod = session.query(InstalledMod).filter_by(id=installed_mod_id).first()
            if not mod:
                return False, "Mod introuvable dans la base de données."

            folder_name = (mod.folder_name or "").strip()
            if not folder_name or folder_name in [".", "..", "/", "\\"]:
                logger.error(f"Nom de dossier de mod invalide pour la désinstallation: '{folder_name}'")
                return False, "Nom de dossier de mod invalide."

            if mods_dir:
                mods_dir_resolved = mods_dir.resolve()
                target_dir = (mods_dir / folder_name).resolve()

                # Safety check: target_dir must be a strict subfolder of mods_dir, never mods_dir itself
                if target_dir == mods_dir_resolved or mods_dir_resolved not in target_dir.parents:
                    logger.error(f"Tentative de suppression non autorisée hors de Mods/ : {target_dir}")
                    return False, "Opération annulée : le chemin cible est invalide ou pointe hors du dossier Mods."

                if not target_dir.exists():
                    alt = None
                    if folder_name.endswith(".disabled"):
                        candidate = (mods_dir / folder_name[:-9]).resolve()
                        if candidate.exists():
                            alt = candidate
                    else:
                        candidate = (mods_dir / f"{folder_name}.disabled").resolve()
                        if candidate.exists():
                            alt = candidate
                    if alt and (alt == mods_dir_resolved or mods_dir_resolved in alt.parents):
                        target_dir = alt

                if target_dir.exists():
                    try:
                        if target_dir.is_dir():
                            shutil.rmtree(target_dir)
                            logger.info(f"Removed mod directory: {target_dir}")
                        else:
                            target_dir.unlink()
                            logger.info(f"Removed mod file: {target_dir}")
                    except Exception as e:
                        logger.error(f"Failed to delete mod folder or file: {e}")
                        return False, f"Impossible de supprimer le mod: {e}"

            session.delete(mod)
            session.commit()

        return True, "Mod désinstallé avec succès."

    @classmethod
    def verify_and_cleanup_installed_mods(cls) -> List[str]:
        """
        Scans all InstalledMod records in the database and verifies that their physical folder
        or files still exist in the Sims 4 Mods directory.
        """
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return []

        removed_titles = []
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            installed = session.query(InstalledMod).all()
            for mod in installed:
                mod_folder = mods_dir / (mod.folder_name or "")
                exists = False
                if mod_folder.is_dir() and any(mod_folder.glob("*")):
                    exists = True
                elif mod_folder.is_file():
                    exists = True
                else:
                    # Check if loose mod file or folder was renamed to/from .disabled
                    if mod.folder_name and mod.folder_name.endswith(".disabled"):
                        alt = mods_dir / mod.folder_name[:-9]
                        if alt.is_file() or (alt.is_dir() and any(alt.glob("*"))):
                            exists = True
                    elif mod.folder_name:
                        alt = mods_dir / f"{mod.folder_name}.disabled"
                        if alt.is_file() or (alt.is_dir() and any(alt.glob("*"))):
                            exists = True

                if not exists:
                    logger.info(
                        f"Mod supprimé du disque détecté, nettoyage de la BDD : '{mod.title}' ({mod.folder_name})"
                    )
                    removed_titles.append(mod.title or "")
                    session.delete(mod)

            if removed_titles:
                session.commit()
                logger.info(
                    f"Nettoyage BDD terminé : {len(removed_titles)} mod(s) désinstallé(s) manuellement retiré(s)."
                )
        return removed_titles

    @classmethod
    def start_background_installed_mods_verifier(cls) -> None:
        """Starts an asynchronous daemon thread at startup to verify and clean up deleted mods."""

        def _worker():
            time.sleep(2.0)
            try:
                cls.verify_and_cleanup_installed_mods()
            except Exception as e:
                logger.debug(f"Erreur vérification mods installés en tâche de fond : {e}")

        from src.core.concurrency.thread_pool_manager import ThreadPoolManager

        ThreadPoolManager.get_instance().submit_io(_worker)

    @classmethod
    def scan_existing_mods(cls) -> List[Dict[str, Any]]:
        """Scans the Sims 4 Mods directory for manually placed mods and indexes them."""
        cls.verify_and_cleanup_installed_mods()

        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return []

        found_mods = []
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            existing_by_folder = {m.folder_name: m for m in session.query(InstalledMod).all()}
            for item in mods_dir.iterdir():
                is_dir = item.is_dir() and not item.name.startswith(".")
                is_mod_file = (
                    item.is_file()
                    and not item.name.startswith(".")
                    and item.name.lower() not in {"resource.cfg", "desktop.ini", "thumbs.db", ".ds_store"}
                    and (
                        item.suffix.lower() in [".package", ".ts4script"]
                        or item.name.lower().endswith((".package.disabled", ".ts4script.disabled"))
                    )
                )

                if not (is_dir or is_mod_file):
                    continue

                folder_name = item.name
                if is_dir:
                    files = [str(p.relative_to(mods_dir)) for p in item.rglob("*") if p.is_file()]
                    if not files:
                        continue
                    if folder_name.lower().endswith(".disabled"):
                        is_enabled = False
                    else:
                        is_enabled = not all(f.endswith(".disabled") for f in files)
                else:
                    files = [str(item.relative_to(mods_dir))]
                    is_enabled = not item.name.lower().endswith(".disabled")

                clean_fn = folder_name[:-9] if folder_name.endswith(".disabled") else folder_name
                alt_fn = folder_name[:-9] if folder_name.endswith(".disabled") else f"{folder_name}.disabled"
                existing = existing_by_folder.get(folder_name) or existing_by_folder.get(clean_fn) or existing_by_folder.get(alt_fn)

                if not existing:
                    stripped_name = re.sub(r"_\d{3,4}$", "", folder_name)
                    if stripped_name.lower().endswith(".disabled"):
                        stripped_name = stripped_name[:-9]
                    if is_mod_file:
                        for ext in [".package", ".ts4script"]:
                            if stripped_name.lower().endswith(ext):
                                stripped_name = stripped_name[: -len(ext)]

                    for prefix in ["loverslab_", "patreon_", "manual_"]:
                        if stripped_name.lower().startswith(prefix):
                            stripped_name = stripped_name[len(prefix) :]
                            break

                    clean_search = stripped_name.replace("_", " ").strip()
                    matched_cat = (
                        session.query(CatalogMod).filter(CatalogMod.title.ilike(f"%{clean_search}%")).first()
                    )
                    if not matched_cat and len(clean_search.split()) > 1:
                        first_word = clean_search.split()[0]
                        if len(first_word) >= 4:
                            matched_cat = (
                                session.query(CatalogMod).filter(CatalogMod.title.ilike(f"%{first_word}%")).first()
                            )

                    record = InstalledMod(
                        catalog_mod_id=matched_cat.id if matched_cat else None,
                        source=matched_cat.source if matched_cat else "manual",
                        remote_id=matched_cat.remote_id if matched_cat else "",
                        title=matched_cat.title if matched_cat else clean_search,
                        folder_name=folder_name,
                        installed_date=datetime.fromtimestamp(item.stat().st_mtime),
                        is_enabled=is_enabled,
                    )
                    record.set_installed_files_list(files)
                    session.add(record)
                    found_mods.append({"title": record.title, "folder": folder_name, "status": "added"})
                else:
                    existing.folder_name = folder_name
                    existing.set_installed_files_list(files)
                    existing.is_enabled = is_enabled
                    found_mods.append({"title": existing.title, "folder": folder_name, "status": "updated"})

            session.commit()

        return found_mods
