"""Service applicatif de détection des conflits binaires DBPF entre mods installés.

Analyse l'ensemble des fichiers .package présents dans le dossier Mods des Sims 4
et identifie les collisions de ressources TGI (Type, Group, Instance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.infrastructure.filesystem.dbpf_parser import DbpfParser

from src.utils.logger import logger


@dataclass
class ModConflictItem:
    """Représente une collision de ressource entre plusieurs mods."""

    tgi: str
    resource_type_name: str
    conflicting_packages: List[str]
    is_translation_override: bool = False


@dataclass
class ModConflictReport:
    """Rapport complet de détection des conflits du dossier Mods."""

    total_packages_scanned: int = 0
    total_resources_indexed: int = 0
    conflict_count: int = 0
    translation_override_count: int = 0
    conflicts: List[ModConflictItem] = field(default_factory=list)


class ConflictDetectorService:
    """Service d'analyse et de diagnostic des conflits de mods."""

    def __init__(self, parser: Optional[type[DbpfParser]] = None) -> None:
        self.parser = parser or DbpfParser

    def detect_conflicts(self, mods_dir: Path) -> ModConflictReport:
        """Parcourt le dossier Mods et détecte toutes les collisions TGI entre .package distincts."""
        report = ModConflictReport()
        if not mods_dir.exists() or not mods_dir.is_dir():
            return report

        # Trouver tous les fichiers .package non désactivés (en ignorant les sous-dossiers .disabled)
        package_files = [
            p for p in mods_dir.rglob("*.package")
            if not any(part.endswith(".disabled") for part in p.parts)
        ]
        report.total_packages_scanned = len(package_files)

        # Table d'indexation inversée : TGI -> (nom de ressource, is_translation, liste des chemins relatifs)
        tgi_map: Dict[str, tuple[str, bool, List[str]]] = {}
        total_resources = 0

        for pkg in package_files:
            try:
                rel_path = str(pkg.relative_to(mods_dir)).replace("\\", "/")
                entries = self.parser.parse_index(pkg)
                total_resources += len(entries)

                # Éviter de compter les doublons internes à un même fichier
                seen_in_pkg = set()
                for entry in entries:
                    key_str = entry.key.tgi_str
                    if key_str in seen_in_pkg:
                        continue
                    seen_in_pkg.add(key_str)

                    is_stbl = (entry.key.type_id == 0x220557DA)
                    if key_str not in tgi_map:
                        tgi_map[key_str] = (entry.key.resource_type_name, is_stbl, [rel_path])
                    else:
                        tgi_map[key_str][2].append(rel_path)
            except Exception as e:
                logger.warning(f"Erreur ignorée lors du scan du package {pkg}: {e}")

        report.total_resources_indexed = total_resources

        # Filtrer uniquement les ressources présentes dans au moins 2 packages distincts
        conflicts: List[ModConflictItem] = []
        translation_override_count = 0
        for tgi_str, (res_name, is_stbl, packages) in tgi_map.items():
            if len(packages) > 1:
                if is_stbl:
                    translation_override_count += 1
                conflicts.append(
                    ModConflictItem(
                        tgi=tgi_str,
                        resource_type_name=res_name,
                        conflicting_packages=sorted(packages),
                        is_translation_override=is_stbl,
                    )
                )

        # Trier en mettant d'abord les vrais conflits de tuning/ressources, puis par nombre de packages
        report.conflicts = sorted(
            conflicts,
            key=lambda c: (not c.is_translation_override, len(c.conflicting_packages)),
            reverse=True,
        )
        report.conflict_count = len(report.conflicts)
        report.translation_override_count = translation_override_count

        logger.info(
            f"Analyse des conflits DBPF terminée : {report.total_packages_scanned} packages analysés, "
            f"{report.total_resources_indexed} ressources indexées, {report.conflict_count} collision(s) détectée(s) "
            f"dont {report.translation_override_count} remplacement(s) de traduction."
        )

        return report

    @staticmethod
    def resolve_conflict(
        mods_dir: Path, package_rel_path: str, action: str = "disable"
    ) -> tuple[bool, str, Optional[str]]:
        """Active ou désactive un package individuel pour résoudre un conflit DBPF."""
        from src.application.game.game_service import GameDetector

        if GameDetector.is_game_running():
            return False, "Le jeu Les Sims 4 est en cours d'exécution.", None

        if not mods_dir.exists():
            return False, "Dossier Mods introuvable.", None

        rel_clean = package_rel_path.strip().replace("\\", "/")
        if not rel_clean or rel_clean.startswith(("/", "..")) or "/../" in rel_clean:
            return False, "Chemin de package invalide.", None

        target = (mods_dir / rel_clean).resolve()
        resolved_mods = mods_dir.resolve()
        if target != resolved_mods and resolved_mods not in target.parents:
            return False, "Accès refusé hors du dossier Mods.", None

        if action == "disable":
            if not target.exists():
                return False, f"Fichier '{target.name}' introuvable.", None
            if not target.name.endswith(".package"):
                return False, "Seuls les fichiers .package peuvent être désactivés pour conflit.", None
            new_target = target.with_name(f"{target.name}.disabled")
            try:
                target.rename(new_target)
                new_rel = str(new_target.relative_to(mods_dir)).replace("\\", "/")
                logger.info(f"Conflit résolu : package '{target.name}' renommé en '{new_target.name}'")
                return True, f"Package désactivé avec succès : {new_target.name}", new_rel
            except Exception as e:
                return False, f"Impossible de désactiver le package : {e}", None

        elif action == "enable":
            if not target.exists():
                return False, f"Fichier '{target.name}' introuvable.", None
            if not target.name.endswith(".package.disabled"):
                return False, "Seuls les fichiers .package.disabled peuvent être réactivés.", None
            new_target = target.with_name(target.name[:-9])
            try:
                target.rename(new_target)
                new_rel = str(new_target.relative_to(mods_dir)).replace("\\", "/")
                logger.info(f"Conflit résolu : package '{target.name}' réactivé en '{new_target.name}'")
                return True, f"Package réactivé avec succès : {new_target.name}", new_rel
            except Exception as e:
                return False, f"Impossible de réactiver le package : {e}", None

        return False, f"Action inconnue '{action}'. Utilisez 'disable' ou 'enable'.", None

