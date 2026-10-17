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


@dataclass
class ModConflictReport:
    """Rapport complet de détection des conflits du dossier Mods."""

    total_packages_scanned: int = 0
    total_resources_indexed: int = 0
    conflict_count: int = 0
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

        # Trouver tous les fichiers .package non désactivés
        package_files = [p for p in mods_dir.rglob("*.package") if not p.name.endswith(".disabled")]
        report.total_packages_scanned = len(package_files)

        # Table d'indexation inversée : TGI -> liste des chemins relatifs
        tgi_map: Dict[str, tuple[str, List[str]]] = {}
        total_resources = 0

        for pkg in package_files:
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

                if key_str not in tgi_map:
                    tgi_map[key_str] = (entry.key.resource_type_name, [rel_path])
                else:
                    tgi_map[key_str][1].append(rel_path)

        report.total_resources_indexed = total_resources

        # Filtrer uniquement les ressources présentes dans au moins 2 packages distincts
        conflicts: List[ModConflictItem] = []
        for tgi_str, (res_name, packages) in tgi_map.items():
            if len(packages) > 1:
                conflicts.append(
                    ModConflictItem(
                        tgi=tgi_str,
                        resource_type_name=res_name,
                        conflicting_packages=sorted(packages),
                    )
                )

        report.conflicts = sorted(conflicts, key=lambda c: len(c.conflicting_packages), reverse=True)
        report.conflict_count = len(report.conflicts)

        logger.info(
            f"Analyse des conflits DBPF terminée : {report.total_packages_scanned} packages analysés, "
            f"{report.total_resources_indexed} ressources indexées, {report.conflict_count} conflit(s) détecté(s)."
        )

        return report
