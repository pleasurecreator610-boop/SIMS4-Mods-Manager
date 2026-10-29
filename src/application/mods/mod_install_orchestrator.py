"""
Level 1: Orchestrator for Mod Installation.
Declares and orchestrates downloading, dependency cascades,
file installations, and result payload formatting.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from src.api.schemas.catalog import CatalogInstallRequest, CatalogInstallResponse, DependencyItem
from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.application.game.game_service import GameDetector
from src.application.mods.mod_install_actions import ModInstallActions
from src.application.mods.mod_install_coordinator import ModInstallCoordinator
from src.core.config import AppConfig
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod, InstalledMod
from src.providers import ProviderRegistry
from src.utils.dependency_noise_rules import is_likely_comment_or_noise
from src.utils.logger import logger


class ModInstallOrchestrator:
    """High-level orchestrator for installing mods from catalog or files."""

    def __init__(
        self,
        coordinator: Optional[ModInstallCoordinator] = None,
        actions: Optional[ModInstallActions] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.actions = actions or ModInstallActions(self.db)
        self.coordinator = coordinator or ModInstallCoordinator(self.actions, self.db)

    def orchestrate_catalog_install(
        self,
        payload: CatalogInstallRequest,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> CatalogInstallResponse:
        """
        Orchestrates full catalog mod installation workflow:
        1. Queries/loads CatalogMod entity.
        2. Inspects and installs missing dependencies in cascade via coordinator.
        3. Downloads mod archive from provider.
        4. Delegates extraction, deployment, and DB persistence to coordinator.
        5. Formats response DTO.
        """
        if GameDetector.is_game_running():
            return CatalogInstallResponse(
                success=False,
                message="Le jeu Les Sims 4 est actuellement en cours d'exécution. Veuillez fermer le jeu avant d'installer des mods.",
            )

        cat_mod = None
        with self.db.get_session() as session:
            if payload.catalog_mod_id:
                cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
            elif payload.source and payload.remote_id:
                cat_mod = (
                    session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()
                )

        source: str = str((cat_mod.source if cat_mod and cat_mod.source else None) or (payload.source or "loverslab"))
        page_url = cat_mod.page_url if cat_mod else payload.page_url
        mod_title: str = str((cat_mod.title if cat_mod and cat_mod.title else None) or (payload.title or "Mod"))
        remote_id: str = str(
            (cat_mod.remote_id if cat_mod and cat_mod.remote_id else None) or (payload.remote_id or "unknown")
        )
        version_date = cat_mod.updated_date if cat_mod else payload.updated_date

        if not page_url:
            return CatalogInstallResponse(success=False, message="Page URL ou identifiant du mod introuvable.")

        from src.application.mods.active_installation_registry import ActiveInstallationRegistry

        registry = ActiveInstallationRegistry.get_instance()
        acquired, active_event = registry.register_install(source, remote_id, mod_title)
        if not acquired:
            logger.info(f"[INSTALL-MAIN] Installation déjà en cours pour '{mod_title}' ({remote_id}), attente...")
            if progress_callback:
                progress_callback(10, f"Installation de '{mod_title}' déjà active, attente...", "")
            wait_ok, wait_msg = registry.wait_for_active_install(source, remote_id, mod_title)
            return CatalogInstallResponse(success=wait_ok, message=wait_msg)

        installed_dependencies: List[str] = []
        not_detected_deps: List[DependencyItem] = []

        install_ok = False
        install_msg = ""
        try:
            # 1. Dependency Resolution & Installation Cascade
            if payload.install_dependencies:
                req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []
                req_status = cat_mod.requirements_status if cat_mod else "NONE"

                if (not req_mods or req_status in [None, "NONE"]) and page_url:
                    try:
                        provider = ProviderRegistry.get_provider(source)
                        if provider:
                            logger.info(
                                f"[INSTALL-DEP] Analyse préalable des dépendances pour '{mod_title}' ({page_url})..."
                            )
                            det = provider.get_mod_details(page_url)
                            det_dict: dict[str, Any] = (
                                det.model_dump()
                                if hasattr(det, "model_dump")
                                else (det if isinstance(det, dict) else {})
                            )
                            req_mods = det_dict.get("requirements_mods", [])
                            req_status = det_dict.get("requirements_status", "NONE")
                            if cat_mod:
                                with self.db.get_session() as s:
                                    cm = s.query(CatalogMod).filter_by(id=cat_mod.id).first()
                                    if cm:
                                        cm.requirements_text = det_dict.get("requirements_text")
                                        cm.requirements_status = req_status
                                        cm.set_requirements_mods_list(req_mods)
                                        s.commit()
                    except Exception as e:
                        logger.warning(f"[INSTALL-DEP] Impossible d'analyser les prérequis pour '{mod_title}': {e}")

                with self.db.get_session() as session:
                    all_inst = session.query(InstalledMod).all()
                    installed_by_remote = {
                        (im.source or "unknown", im.remote_id): im for im in all_inst if im.remote_id
                    }
                    installed_by_title = {im.title.lower(): im for im in all_inst if im.title}

                    resolved_deps = resolve_mod_dependencies(
                        req_mods,
                        session,
                        installed_by_remote,
                        installed_by_title,
                    )

                missing_dependencies = [
                    d
                    for d in resolved_deps
                    if not d.is_installed
                    and d.status != "INSTALLED"
                    and not d.is_game_dlc
                    and d.status != "GAME_DLC"
                    and not d.is_comment
                    and d.status not in ["COMMENT_NOISE", "COMMENT"]
                    and not is_likely_comment_or_noise(d.title)
                ]
                not_detected_deps = [
                    d for d in missing_dependencies if d.status == "NOT_DETECTED_FINISHED" or not d.remote_id
                ]
                if not_detected_deps:
                    missing_dependencies = [d for d in missing_dependencies if d not in not_detected_deps]

                ok, inst_deps, not_det, err_msg = self.coordinator.coordinate_dependency_installations(
                    missing_dependencies=missing_dependencies,
                    install_func=self.orchestrate_catalog_install,
                    allow_partial=payload.allow_partial,
                    mod_title=mod_title,
                    progress_callback=progress_callback,
                )
                installed_dependencies.extend(inst_deps)
                not_detected_deps.extend(not_det)

                if not ok:
                    install_msg = f"Installation interrompue : {err_msg}"
                    return CatalogInstallResponse(
                        success=False,
                        message=install_msg,
                        installed_dependencies=installed_dependencies,
                    )

            # 2. Main Mod Download & Installation (with Cross-Platform Deduplication Check)
            import re
            from src.utils.mod_matcher import ModMatcher

            stripped_t = re.sub(r"(?i)^the\s+", "", mod_title.strip())
            target_fp = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title(stripped_t) or stripped_t)
            if target_fp:
                config = AppConfig.load()
                mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
                with self.db.get_session() as s:
                    for im in s.query(InstalledMod).all():
                        if (im.source or "").lower() != source.lower() and im.title:
                            im_stripped = re.sub(r"(?i)^the\s+", "", im.title.strip())
                            im_fp = ModMatcher.canonical_fingerprint(
                                ModMatcher.clean_mod_title(im_stripped) or im_stripped
                            )
                            if im_fp == target_fp and im.folder_name and mods_dir:
                                disk_dir = mods_dir / im.folder_name
                                if disk_dir.exists():
                                    install_ok = True
                                    install_msg = (
                                        f"Mod '{mod_title}' déjà installé via '{im.source}' "
                                        f"dans '{im.folder_name}' (non-collision inter-plateformes)."
                                    )
                                    logger.info(f"[INSTALL-MAIN] {install_msg}")
                                    return CatalogInstallResponse(
                                        success=True,
                                        message=install_msg,
                                        installed_dependencies=installed_dependencies,
                                    )

            provider = ProviderRegistry.get_provider(source)
            if not provider:
                install_msg = f"Fournisseur source '{source}' non supporté."
                return CatalogInstallResponse(success=False, message=install_msg)

            if progress_callback:
                progress_callback(2, "Analyse de la page du mod...", f"Source : {source}")

            details = provider.get_mod_details(page_url)
            details_dict: dict[str, Any] = (
                details.model_dump()
                if hasattr(details, "model_dump")
                else (details if isinstance(details, dict) else {})
            )
            download_urls = details_dict.get("download_urls", [])
            if not download_urls:
                ext_links = details_dict.get("external_links", [])
                if ext_links:
                    install_msg = f"Téléchargement externe requis : {', '.join(ext_links[:2])}"
                    return CatalogInstallResponse(success=False, message=install_msg)
                install_msg = "Aucun lien de téléchargement trouvé pour ce mod."
                return CatalogInstallResponse(success=False, message=install_msg)

            dl_info = download_urls[0]
            dl_url = dl_info["url"] if isinstance(dl_info, dict) else dl_info

            downloads_dir = AppConfig.get_app_dir() / "downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            filename = f"mod_{remote_id}.zip"
            dest_file = downloads_dir / filename

            if progress_callback:
                progress_callback(5, "Démarrage du téléchargement...", f"{filename}")

            ok, msg = self.actions.download_file(provider, dl_url, dest_file, progress_callback=progress_callback)
            if not ok:
                install_msg = f"Échec du téléchargement: {msg}"
                return CatalogInstallResponse(success=False, message=install_msg)

            file_to_install = Path(msg) if Path(msg).exists() else dest_file
            file_to_install = self.actions.detect_and_normalize_extension(file_to_install)

            v_date = version_date if isinstance(version_date, datetime) else None
            if not v_date and details_dict.get("updated_date"):
                raw_d = details_dict.get("updated_date")
                if isinstance(raw_d, datetime):
                    v_date = raw_d
                elif isinstance(raw_d, str):
                    try:
                        v_date = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass

            config = AppConfig.load()
            mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
            if not mods_dir:
                install_msg = "Dossier Mods de Sims 4 introuvable. Veuillez vérifier vos paramètres."
                return CatalogInstallResponse(success=False, message=install_msg)

            from src.application.mods.mod_installer_service import ModInstaller

            install_ok, install_msg = ModInstaller.install_mod_from_file(
                file_path=file_to_install,
                catalog_mod=cat_mod,
                source=source,
                custom_title=mod_title,
                version_date=v_date,
                version_str=str(details_dict.get("version_str", "") or ""),
                progress_callback=progress_callback,
            )

            try:
                file_to_install.unlink(missing_ok=True)
                dest_file.unlink(missing_ok=True)
            except Exception:
                pass

            return CatalogInstallResponse(
                success=install_ok,
                message=install_msg,
                installed_dependencies=installed_dependencies,
            )
        except Exception as e:
            install_ok = False
            install_msg = f"Exception inattendue lors de l'installation de '{mod_title}': {e}"
            logger.error(install_msg, exc_info=True)
            return CatalogInstallResponse(success=False, message=install_msg)
        finally:
            registry.complete_install(source, remote_id, mod_title, success=install_ok, message=install_msg)

    def orchestrate_file_install(
        self,
        file_path: Path,
        catalog_mod: Optional[CatalogMod] = None,
        source: str = "manual",
        custom_title: Optional[str] = None,
        version_date: Optional[datetime] = None,
        version_str: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Orchestrates installing a mod directly from a local archive or file."""
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir:
            return False, "Dossier Mods de Sims 4 introuvable. Veuillez vérifier vos paramètres."

        return self.coordinator.coordinate_file_install(
            file_path=file_path,
            mods_dir=mods_dir,
            catalog_mod=catalog_mod,
            source=source,
            custom_title=custom_title,
            version_date=version_date,
            version_str=version_str,
            progress_callback=progress_callback,
        )


def perform_mod_install(
    payload: CatalogInstallRequest,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> CatalogInstallResponse:
    """Main entry point for mod catalog installation."""
    orchestrator = ModInstallOrchestrator()
    return orchestrator.orchestrate_catalog_install(payload=payload, progress_callback=progress_callback)
