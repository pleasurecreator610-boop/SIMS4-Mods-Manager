"""
Level 2: Flow Coordinator for Mod Installation.
Coordinates execution sequences, loops through dependencies,
and controls atomic install steps with rollback guarantees.
"""

from datetime import datetime
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.api.schemas.catalog import CatalogInstallRequest, CatalogInstallResponse, DependencyItem
from src.application.mods.mod_install_actions import ModInstallActions
from src.core.config import AppConfig
from src.database.manager import DatabaseManager
from src.database.models import CatalogMod, InstalledMod
from src.utils.archive import extract_archive, is_archive
from src.utils.file_utils import generate_unique_mod_folder_name
from src.utils.logger import logger


class ModInstallCoordinator:
    """Coordinates sequencing, loops, and error boundaries for mod installations."""

    def __init__(
        self,
        actions: Optional[ModInstallActions] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.actions = actions or ModInstallActions(db_manager)
        self.db = db_manager or DatabaseManager.get_instance()

    def coordinate_file_install(
        self,
        file_path: Path,
        mods_dir: Path,
        catalog_mod: Optional[CatalogMod] = None,
        source: str = "manual",
        custom_title: Optional[str] = None,
        version_date: Optional[datetime] = None,
        version_str: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Coordinates full file installation:
        1. Normalizes binary extension.
        2. Resolves or generates target mod folder name.
        3. Creates automatic backup if replacing existing install.
        4. Extracts or copies files.
        5. Deploys files respecting the .ts4script depth rule.
        6. Persists InstalledMod record.
        7. Performs rollback if any step fails.
        """
        config = AppConfig.load()
        file_path = self.actions.detect_and_normalize_extension(file_path)

        title = custom_title or (catalog_mod.title if catalog_mod else file_path.stem)
        source_name = source or (catalog_mod.source if catalog_mod else "manual")
        remote_id = catalog_mod.remote_id if catalog_mod else ""
        catalog_id = catalog_mod.id if catalog_mod else None

        with self.db.get_session() as session:
            existing_installed = None
            if catalog_id:
                existing_installed = session.query(InstalledMod).filter_by(catalog_mod_id=catalog_id).first()
            if not existing_installed and remote_id and source_name:
                existing_installed = (
                    session.query(InstalledMod).filter_by(remote_id=remote_id, source=source_name).first()
                )
            if not existing_installed:
                existing_installed = session.query(InstalledMod).filter_by(title=title, source=source_name).first()

            if existing_installed and existing_installed.folder_name:
                safe_folder_name = existing_installed.folder_name
            else:
                safe_folder_name = generate_unique_mod_folder_name(
                    source_name or "manual", title or file_path.stem, mods_dir
                )

            target_mod_dir = mods_dir / (safe_folder_name or "unknown_mod")

            backup_file_path = None
            if existing_installed and target_mod_dir.exists() and config.auto_backup:
                backup_file_path = self.actions.create_directory_backup(
                    target_dir=target_mod_dir,
                    backup_parent_dir=AppConfig.get_backups_dir(),
                    mod_name=safe_folder_name,
                )

            # Preserve existing user configs (e.g. MCCC, WickedWhims, Tool configs)
            preserved_configs: Dict[str, bytes] = {}
            if target_mod_dir.exists():
                cfg_exts = {".cfg", ".ini", ".settings"}
                for cfg_file in target_mod_dir.rglob("*"):
                    if cfg_file.is_file() and (
                        cfg_file.suffix.lower() in cfg_exts
                        or "settings" in cfg_file.name.lower()
                        or "config" in cfg_file.name.lower()
                    ):
                        try:
                            rel_k = str(cfg_file.relative_to(target_mod_dir))
                            preserved_configs[rel_k] = cfg_file.read_bytes()
                        except Exception as ce:
                            logger.debug(f"Lecture config existant ignorée: {ce}")

            temp_extract_dir = None
            try:
                if progress_callback:
                    progress_callback(50, "Extraction et déploiement des fichiers...", f"{title}")

                if is_archive(file_path):
                    temp_extract_dir = Path(tempfile.mkdtemp(prefix="sims4_extract_"))
                    extract_archive(file_path, temp_extract_dir)

                    if target_mod_dir.exists():
                        shutil.rmtree(target_mod_dir, ignore_errors=True)

                    installed_files = self.actions.deploy_extracted_files(
                        extracted_dir=temp_extract_dir,
                        target_mod_dir=target_mod_dir,
                        mods_dir=mods_dir,
                    )
                else:
                    if target_mod_dir.exists():
                        shutil.rmtree(target_mod_dir, ignore_errors=True)
                    installed_files = self.actions.deploy_direct_file(
                        file_path=file_path, target_mod_dir=target_mod_dir, mods_dir=mods_dir
                    )

                # Restore any preserved user configs that were not present in the new version archive
                for rel_k, cfg_bytes in preserved_configs.items():
                    restored_dest = target_mod_dir / rel_k
                    if not restored_dest.exists():
                        try:
                            restored_dest.parent.mkdir(parents=True, exist_ok=True)
                            restored_dest.write_bytes(cfg_bytes)
                            rel_from_mods = str(restored_dest.relative_to(mods_dir))
                            if rel_from_mods not in installed_files:
                                installed_files.append(rel_from_mods)
                            logger.info(f"Configuration utilisateur préservée et restaurée : {rel_k}")
                        except Exception as re:
                            logger.debug(f"Restauration config ignorée pour {rel_k}: {re}")

                if not installed_files:
                    raise ValueError("Aucun fichier de mod valide (.package ou .ts4script) trouvé dans l'archive.")

                self.actions.record_installation(
                    session=session,
                    title=title,
                    source=source_name,
                    remote_id=remote_id,
                    catalog_id=catalog_id,
                    folder_name=safe_folder_name,
                    installed_files=installed_files,
                    version_date=version_date,
                    version_str=version_str,
                    backup_path=str(backup_file_path) if backup_file_path else None,
                )

                if progress_callback:
                    progress_callback(100, "Installation terminée avec succès !", f"{title}")

                return True, f"Mod '{title}' installé avec succès dans '{safe_folder_name}'."
            except Exception as e:
                logger.error(f"Erreur lors de l'installation de '{title}': {e}", exc_info=True)
                self.actions.rollback_directory(backup_file_path, target_mod_dir)
                return False, f"Échec de l'installation: {e}"
            finally:
                if temp_extract_dir and temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def coordinate_dependency_installations(
        self,
        missing_dependencies: List[DependencyItem],
        install_func: Callable[[CatalogInstallRequest, Optional[Callable]], CatalogInstallResponse],
        allow_partial: bool,
        mod_title: str,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        visited_remotes: Optional[Set[Tuple[str, str]]] = None,
    ) -> Tuple[bool, List[str], List[DependencyItem], Optional[str]]:
        """
        Coordinates iteration over dependencies to install them sequentially.
        Supports transitive dependencies while preventing infinite circular loops.
        Returns (success, installed_names, not_detected_items, error_message).
        """
        installed_deps: List[str] = []
        not_detected_deps: List[DependencyItem] = []
        total_missing = len(missing_dependencies)
        visited = visited_remotes if visited_remotes is not None else set()

        for idx, dep in enumerate(missing_dependencies, start=1):
            dep_source = dep.source or "loverslab"
            dep_remote_id = dep.remote_id or ""
            dep_title = dep.title or f"Mod #{dep_remote_id}"
            dep_url = dep.url

            dep_key = (dep_source, dep_remote_id)
            if dep_remote_id and dep_key in visited:
                logger.info(f"[INSTALL-DEP] Dépendance déjà en cours ou cycle détecté pour '{dep_title}' (#{dep_remote_id})")
                continue
            if dep_remote_id:
                visited.add(dep_key)

            if not dep_url and dep_remote_id:
                with self.db.get_session() as s:
                    c_dep = s.query(CatalogMod).filter_by(source=dep_source, remote_id=dep_remote_id).first()
                    if c_dep and c_dep.page_url:
                        dep_url = c_dep.page_url
                if not dep_url and dep_source == "loverslab":
                    dep_url = f"https://www.loverslab.com/files/file/{dep_remote_id}/"

            if progress_callback:
                pct = int(10 + (idx - 1) / max(total_missing, 1) * 35)
                progress_callback(
                    pct,
                    f"Installation dépendance ({idx}/{total_missing}) : {dep_title}...",
                    f"ID #{dep_remote_id}",
                )

            if not dep_url:
                logger.error(f"[INSTALL-DEP] ❌ URL introuvable pour '{dep_title}' (#{dep_remote_id}).")
                continue

            dep_payload = CatalogInstallRequest(
                source=dep_source,
                remote_id=dep_remote_id,
                page_url=dep_url,
                title=dep_title,
                install_dependencies=True,
            )
            dep_res = install_func(dep_payload, progress_callback)
            if dep_res.success:
                installed_deps.append(dep_title)
            else:
                err_msg = f"Échec de l'installation de la dépendance requise '{dep_title}': {dep_res.message}"
                logger.error(f"[INSTALL-DEP] ❌ {err_msg}")
                if allow_partial:
                    not_detected_deps.append(
                        DependencyItem(
                            source=dep_source,
                            remote_id=dep_remote_id,
                            title=dep_title,
                            url=dep_url or "",
                            status="NOT_DETECTED_FINISHED",
                        )
                    )
                else:
                    return False, installed_deps, not_detected_deps, err_msg

        return True, installed_deps, not_detected_deps, None
