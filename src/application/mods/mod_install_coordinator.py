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
from src.utils.dependency_noise_rules import is_likely_comment_or_noise
from src.application.mods.mod_toggle_actions import ModToggleActions
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
        from src.application.game.game_service import GameDetector

        if GameDetector.is_game_running():
            return (
                False,
                "Le jeu Les Sims 4 est actuellement en cours d'exécution. Veuillez fermer le jeu avant d'installer des mods.",
            )

        config = AppConfig.load()
        file_path = self.actions.detect_and_normalize_extension(file_path)

        title: str = custom_title or (
            (catalog_mod.title if catalog_mod and catalog_mod.title else None) or file_path.stem
        )
        source_name: str = source or ((catalog_mod.source if catalog_mod and catalog_mod.source else None) or "manual")
        remote_id: str = catalog_mod.remote_id if catalog_mod and catalog_mod.remote_id else ""
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

            # Detect if previously installed mod was in disabled state
            is_mod_previously_disabled = False
            if existing_installed:
                if not existing_installed.is_enabled:
                    is_mod_previously_disabled = True
                elif existing_installed.folder_name and existing_installed.folder_name.endswith(".disabled"):
                    is_mod_previously_disabled = True

            if existing_installed and existing_installed.folder_name:
                safe_folder_name = existing_installed.folder_name
            else:
                safe_folder_name = generate_unique_mod_folder_name(
                    source_name or "manual", title or file_path.stem, mods_dir
                )

            # Reconcile folder name with disabled state
            if is_mod_previously_disabled:
                if not safe_folder_name.endswith(".disabled"):
                    safe_folder_name = f"{safe_folder_name}.disabled"
            else:
                if safe_folder_name.endswith(".disabled"):
                    safe_folder_name = safe_folder_name[:-9]

            target_mod_dir = mods_dir / (safe_folder_name or "unknown_mod")

            # Resolve physical folder on disk (could currently exist with or without .disabled)
            existing_disk_dir: Optional[Path] = None
            cand1 = target_mod_dir
            clean_base = safe_folder_name[:-9] if safe_folder_name.endswith(".disabled") else safe_folder_name
            cand2 = mods_dir / (clean_base if safe_folder_name.endswith(".disabled") else f"{clean_base}.disabled")

            if cand1.exists():
                existing_disk_dir = cand1
            elif cand2.exists():
                existing_disk_dir = cand2

            backup_file_path = None
            if existing_installed and existing_disk_dir and existing_disk_dir.exists() and config.auto_backup:
                backup_file_path = self.actions.create_directory_backup(
                    target_dir=existing_disk_dir,
                    backup_parent_dir=AppConfig.get_backups_dir(),
                    mod_name=safe_folder_name,
                )

            # Preserve existing user configs (e.g. MCCC, WickedWhims, Tool configs)
            preserved_configs: Dict[str, bytes] = {}
            if existing_disk_dir and existing_disk_dir.exists():
                cfg_exts = {".cfg", ".ini", ".settings"}
                for cfg_file in existing_disk_dir.rglob("*"):
                    if cfg_file.is_file() and (
                        cfg_file.suffix.lower() in cfg_exts
                        or "settings" in cfg_file.name.lower()
                        or "config" in cfg_file.name.lower()
                    ):
                        try:
                            rel_k = str(cfg_file.relative_to(existing_disk_dir))
                            if rel_k.endswith(".disabled"):
                                rel_k = rel_k[:-9]
                            preserved_configs[rel_k] = cfg_file.read_bytes()
                        except Exception as ce:
                            logger.debug(f"Lecture config existant ignorée: {ce}")

            # Clean up prior disk directory if it had a different name from target_mod_dir
            if existing_disk_dir and existing_disk_dir.exists() and existing_disk_dir != target_mod_dir:
                shutil.rmtree(existing_disk_dir, ignore_errors=True)

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

                # If mod was previously disabled, maintain its disabled state
                if is_mod_previously_disabled:
                    toggle_actions = ModToggleActions()
                    toggle_actions.toggle_folder_files(target_mod_dir, new_state=False, mods_dir=mods_dir)
                    installed_files = [str(p.relative_to(mods_dir)) for p in target_mod_dir.rglob("*") if p.is_file()]

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
                    is_enabled=not is_mod_previously_disabled,
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
            if dep.is_game_dlc or dep.status == "GAME_DLC":
                logger.info(f"[INSTALL-DEP] Ignoré (DLC officiel non téléchargeable) : '{dep.title}'")
                continue
            if dep.is_comment or dep.status in ["COMMENT_NOISE", "COMMENT"] or is_likely_comment_or_noise(dep.title):
                logger.info(f"[INSTALL-DEP] Ignoré (commentaire ou note) : '{dep.title}'")
                continue

            dep_source = dep.source or "loverslab"
            dep_remote_id = dep.remote_id or ""
            dep_title = dep.title or f"Mod #{dep_remote_id}"
            dep_url = dep.url

            dep_key = (dep_source, dep_remote_id)
            if dep_remote_id and dep_key in visited:
                logger.info(
                    f"[INSTALL-DEP] Dépendance déjà en cours ou cycle détecté pour '{dep_title}' (#{dep_remote_id})"
                )
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

            from src.application.mods.active_installation_registry import ActiveInstallationRegistry

            registry = ActiveInstallationRegistry.get_instance()
            # Double check if the dependency was installed while we were processing previous items
            with self.db.get_session() as s:
                already = None
                if dep_remote_id and dep_source:
                    already = s.query(InstalledMod).filter_by(remote_id=dep_remote_id, source=dep_source).first()
                if not already and dep_title:
                    already = s.query(InstalledMod).filter_by(title=dep_title).first()
                if already:
                    logger.info(f"[INSTALL-DEP] Dépendance '{dep_title}' déjà installée en base, passage.")
                    installed_deps.append(dep_title)
                    continue

            # Try to register this installation as active or wait if another thread is already installing it
            acquired, active_event = registry.register_install(dep_source, dep_remote_id, dep_title)
            if not acquired:
                if progress_callback:
                    pct = int(10 + (idx - 1) / max(total_missing, 1) * 35)
                    progress_callback(
                        pct,
                        f"Dépendance partagée '{dep_title}' en cours d'installation, attente...",
                        f"ID #{dep_remote_id}",
                    )
                wait_ok, wait_msg = registry.wait_for_active_install(
                    dep_source, dep_remote_id, dep_title, timeout=180.0
                )
                if wait_ok:
                    installed_deps.append(dep_title)
                    continue
                else:
                    err_msg = f"Échec de l'installation de la dépendance partagée '{dep_title}': {wait_msg}"
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
                        continue
                    else:
                        return False, installed_deps, not_detected_deps, err_msg

            # We acquired the lock: perform the installation and notify waiting threads upon completion
            try:
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
                    registry.complete_install(
                        dep_source, dep_remote_id, dep_title, success=True, message=dep_res.message
                    )
                else:
                    err_msg = f"Échec de l'installation de la dépendance requise '{dep_title}': {dep_res.message}"
                    logger.error(f"[INSTALL-DEP] ❌ {err_msg}")
                    registry.complete_install(dep_source, dep_remote_id, dep_title, success=False, message=err_msg)
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
            except Exception as e:
                registry.complete_install(dep_source, dep_remote_id, dep_title, success=False, message=str(e))
                if allow_partial:
                    logger.error(
                        f"[INSTALL-DEP] ❌ Exception lors de l'installation de la dépendance '{dep_title}': {e}"
                    )
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
                    return (
                        False,
                        installed_deps,
                        not_detected_deps,
                        f"Échec de l'installation de la dépendance requise '{dep_title}': {e}",
                    )

        return True, installed_deps, not_detected_deps, None
