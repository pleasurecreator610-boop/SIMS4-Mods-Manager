"""Service applicatif de détection des conflits binaires DBPF entre mods installés.

Analyse l'ensemble des fichiers .package présents dans le dossier Mods des Sims 4
et identifie les collisions de ressources TGI (Type, Group, Instance).
Intègre un cache persistant SQLite (DbpfPackageCache) indexé par (file_path, mtime, file_size).
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import threading
from typing import Dict, List, Optional, Tuple

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
    """Service d'analyse et de diagnostic des conflits de mods avec cache SQLite persistant."""

    # Cache mtime/taille thread-safe partagé : path_str -> (mtime, size, list[(tgi_str, res_name, is_stbl)])
    _cache: dict[str, tuple[float, int, list[tuple[str, str, bool]]]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, parser: Optional[type[DbpfParser]] = None) -> None:
        self.parser = parser or DbpfParser
        self._dirty_entries: dict[str, tuple[float, int, list[tuple[str, str, bool]]]] = {}

    def _hydrate_cache_from_db(self, package_files: List[Path]) -> None:
        """Précharge les entrées d'index DBPF connues depuis SQLite en une seule requête."""
        if not package_files:
            return
        try:
            from src.infrastructure.database.manager import DatabaseManager
            from src.infrastructure.database.models import DbpfPackageCache

            db = DatabaseManager.get_instance()
            path_keys = [str(p.resolve()) for p in package_files]
            with self._cache_lock:
                missing_keys = [k for k in path_keys if k not in self._cache]
            if not missing_keys:
                return

            with db.get_session() as session:
                rows = session.query(DbpfPackageCache).filter(DbpfPackageCache.file_path.in_(missing_keys)).all()
                with self._cache_lock:
                    for row in rows:
                        try:
                            raw_list = row.get_tgi_list()
                            parsed_items = [(str(item[0]), str(item[1]), bool(item[2])) for item in raw_list]
                            self._cache[row.file_path] = (float(row.mtime), int(row.file_size), parsed_items)
                        except Exception:
                            continue
        except Exception as e:
            logger.debug(f"Chargement du cache DBPF SQLite ignoré : {e}")

    def _flush_dirty_cache_to_db(self) -> None:
        """Persiste en lot dans SQLite les nouveaux index de packages scannés."""
        with self._cache_lock:
            if not self._dirty_entries:
                return
            to_persist = dict(self._dirty_entries)
            self._dirty_entries.clear()

        try:
            from src.infrastructure.database.manager import DatabaseManager
            from src.infrastructure.database.models import DbpfPackageCache

            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                existing_rows = (
                    session.query(DbpfPackageCache)
                    .filter(DbpfPackageCache.file_path.in_(list(to_persist.keys())))
                    .all()
                )
                existing_map = {r.file_path: r for r in existing_rows}

                for path_key, (mtime, size, parsed_items) in to_persist.items():
                    serialized = json.dumps(parsed_items)
                    row = existing_map.get(path_key)
                    if row is not None:
                        row.mtime = mtime
                        row.file_size = size
                        row.resource_count = len(parsed_items)
                        row.tgi_json = serialized
                    else:
                        session.add(
                            DbpfPackageCache(
                                file_path=path_key,
                                mtime=mtime,
                                file_size=size,
                                resource_count=len(parsed_items),
                                tgi_json=serialized,
                            )
                        )
                session.commit()
        except Exception as e:
            logger.debug(f"Persistance du cache DBPF SQLite ignorée : {e}")

    def _parse_package_safe(self, pkg: Path, mods_dir: Path) -> Tuple[str, List[Tuple[str, str, bool]], int]:
        """Parse un package individuel avec mise en cache mtime/taille mémoire + SQLite."""
        try:
            rel_path = str(pkg.relative_to(mods_dir)).replace("\\", "/")
        except Exception:
            rel_path = pkg.name

        try:
            stat = pkg.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            path_key = str(pkg.resolve())

            with self._cache_lock:
                cached = self._cache.get(path_key)
                if cached is not None and abs(cached[0] - mtime) < 1e-4 and cached[1] == size:
                    return rel_path, cached[2], len(cached[2])

            entries = self.parser.parse_index(pkg)
            seen_in_pkg = set()
            parsed_items: List[Tuple[str, str, bool]] = []
            for entry in entries:
                key_str = entry.key.tgi_str
                if key_str in seen_in_pkg:
                    continue
                seen_in_pkg.add(key_str)
                is_stbl = entry.key.type_id == 0x220557DA
                parsed_items.append((key_str, entry.key.resource_type_name, is_stbl))

            with self._cache_lock:
                self._cache[path_key] = (mtime, size, parsed_items)
                self._dirty_entries[path_key] = (mtime, size, parsed_items)

            return rel_path, parsed_items, len(entries)
        except Exception as e:
            logger.warning(f"Erreur ignorée lors du scan du package {pkg}: {e}")
            return rel_path, [], 0

    @staticmethod
    def _scan_enabled_packages(mods_dir: Path) -> List[Path]:
        """Parcours rapide via os.scandir élaguant immédiatement les dossiers .disabled et cachés."""
        packages: List[Path] = []
        stack = [str(mods_dir)]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            name = entry.name
                            if name.startswith(".") or name.lower().endswith(".disabled"):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False) and name.lower().endswith(".package"):
                                packages.append(Path(entry.path))
                        except OSError:
                            continue
            except OSError:
                continue
        return packages

    def detect_conflicts(self, mods_dir: Path) -> ModConflictReport:
        """Parcourt le dossier Mods et détecte toutes les collisions TGI entre .package distincts."""
        report = ModConflictReport()
        if not mods_dir.exists() or not mods_dir.is_dir():
            return report

        package_files = self._scan_enabled_packages(mods_dir)
        report.total_packages_scanned = len(package_files)

        # Hydrater le cache mémoire depuis SQLite si disponible
        self._hydrate_cache_from_db(package_files)

        tgi_map: Dict[str, tuple[str, bool, List[str]]] = {}
        total_resources = 0

        max_workers = min(16, (os.cpu_count() or 4) + 4)
        if len(package_files) <= 4:
            results = [self._parse_package_safe(pkg, mods_dir) for pkg in package_files]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._parse_package_safe, pkg, mods_dir) for pkg in package_files]
                results = [f.result() for f in futures]

        # Persister les nouveaux index scannés dans SQLite
        self._flush_dirty_cache_to_db()

        for rel_path, parsed_items, res_count in results:
            total_resources += res_count
            for key_str, res_name, is_stbl in parsed_items:
                if key_str not in tgi_map:
                    tgi_map[key_str] = (res_name, is_stbl, [rel_path])
                else:
                    tgi_map[key_str][2].append(rel_path)

        report.total_resources_indexed = total_resources

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
