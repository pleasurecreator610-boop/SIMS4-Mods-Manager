"""
Level 2: Flow Coordinator for Dependency Resolution.
Coordinates loop traversal over raw requirements, calls atomic classification
actions, determines resolution status, and handles deduplication.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.api.schemas.catalog import DependencyItem
from src.application.dependencies.dependency_actions import DependencyActions
from src.application.dependencies.dependency_special_cases import (
    SPECIAL_DEPENDENCY_CASES,
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
)
from src.database.models import CatalogMod, InstalledMod
from src.utils.mod_matcher import ModMatcher


class DependencyCoordinator:
    """Coordinates looping and classification across dependency lists."""

    def __init__(self, actions: Optional[DependencyActions] = None):
        self.actions = actions or DependencyActions()

    def resolve_single_dependency(
        self,
        dep: Dict[str, Any],
        session: Session,
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
        is_syncing: bool,
        catalog_remote_ids: Optional[Set[str]] = None,
        requirements_overrides: Optional[Dict[str, str]] = None,
    ) -> DependencyItem:
        """Resolves a single raw dependency item into a typed DependencyItem DTO."""
        source = dep.get("source", "loverslab")
        r_id = str(dep.get("remote_id") or "")
        title = dep.get("title", "")
        url = dep.get("url", "")
        clean_t = self.actions.clean_title(title)

        # 1. Check user override (Mod vs Comment)
        if self.actions.is_comment_override(title, clean_t, requirements_overrides):
            return DependencyItem(
                source=source,
                remote_id=r_id,
                title=title,
                url=url,
                is_installed=False,
                status="COMMENT_NOISE",
                is_game_dlc=False,
                dlc_name=None,
                dlc_code=None,
                is_comment=True,
            )

        # 2. Check official Game DLC / Base Game
        is_base, is_detected_dlc, det_dlc_name, det_dlc_code = self.actions.detect_dlc_or_base(clean_t)
        if is_base:
            return DependencyItem(
                source="game_dlc",
                remote_id="BASE_GAME",
                title="The Sims 4 (Jeu de base)",
                url="",
                is_installed=True,
                status="INSTALLED",
                is_game_dlc=True,
                dlc_name="The Sims 4",
                dlc_code="BASE_GAME",
                is_comment=False,
            )

        is_dlc = dep.get("is_game_dlc", False) or dep.get("status") == "GAME_DLC" or (not is_base and clean_t and is_detected_dlc)
        dlc_name = dep.get("dlc_name") or det_dlc_name or title
        dlc_code = dep.get("dlc_code") or det_dlc_code

        if is_dlc:
            is_installed = self.actions.check_dlc_installed(dlc_code)
            display_title = f"The Sims 4 : {dlc_name}" if not title.lower().startswith("the sims 4") else title
            return DependencyItem(
                source="game_dlc",
                remote_id=dlc_code or "",
                title=display_title,
                url="",
                is_installed=is_installed,
                status="GAME_DLC",
                is_game_dlc=True,
                dlc_name=dlc_name or title,
                dlc_code=dlc_code,
                is_comment=False,
            )

        # 3. If remote_id is missing, search catalog by title or alias
        if not r_id and title:
            special_case = self.actions.find_special_case(title)
            if special_case:
                r_id = special_case["remote_id"]
                url = special_case["url"]
                title = special_case["title"]
                source = special_case.get("source", source)
            else:
                m_rid, m_url, m_title, m_source = self.actions.match_catalog_mod(title, session, source)
                if m_rid:
                    r_id = m_rid
                    url = m_url
                    title = m_title
                    source = m_source

        # 4. Check installed status
        is_installed = self.actions.check_installed(
            source=source,
            remote_id=r_id,
            title=title,
            installed_by_remote=installed_by_remote,
            installed_by_title=installed_by_title,
        )

        # 5. Determine status
        if is_installed:
            status = "INSTALLED"
        elif r_id:
            exists_in_catalog = self.actions.catalog_contains_remote_id(
                source=source, remote_id=r_id, session=session, catalog_remote_ids=catalog_remote_ids
            )
            if exists_in_catalog:
                status = "DETECTED_NOT_INSTALLED"
            elif is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"
        else:
            if is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"

        return DependencyItem(
            source=source,
            remote_id=r_id,
            title=title,
            url=url,
            is_installed=is_installed,
            status=status,
            is_game_dlc=False,
            dlc_name=None,
            dlc_code=None,
        )

    def resolve_all_dependencies(
        self,
        raw_deps: List[Any],
        session: Session,
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
        is_syncing: bool,
        catalog_remote_ids: Optional[Set[str]] = None,
        requirements_overrides: Optional[Dict[str, str]] = None,
        deduplicate: bool = True,
    ) -> List[DependencyItem]:
        """
        Coordinates looping over raw requirements, calls resolve_single_dependency,
        and applies deduplication while preserving ordering.
        """
        items: List[DependencyItem] = []

        for dep in raw_deps:
            dep_dict = dep if isinstance(dep, dict) else {"title": str(dep)}
            item = self.resolve_single_dependency(
                dep=dep_dict,
                session=session,
                installed_by_remote=installed_by_remote,
                installed_by_title=installed_by_title,
                is_syncing=is_syncing,
                catalog_remote_ids=catalog_remote_ids,
                requirements_overrides=requirements_overrides,
            )
            items.append(item)

        if not deduplicate:
            return items

        # Deduplicate and merge resolved dependency items
        deduped: List[DependencyItem] = []
        seen_ids: Dict[Tuple[str, str], int] = {}
        seen_fps: Dict[str, int] = {}

        for item in items:
            s = item.source
            r = item.remote_id
            clean_t = ModMatcher.clean_mod_title(item.title) if item.title else ""
            fp = ModMatcher.canonical_fingerprint(clean_t) if clean_t else ""

            existing_idx = None
            if item.is_game_dlc:
                dlc_k = f"dlc:{item.dlc_code or item.dlc_name or item.title}".lower()
                if dlc_k in seen_fps:
                    existing_idx = seen_fps[dlc_k]
                else:
                    seen_fps[dlc_k] = len(deduped)
            else:
                if r and (s, r) in seen_ids:
                    existing_idx = seen_ids[(s, r)]
                elif fp and fp in seen_fps:
                    existing_idx = seen_fps[fp]

            if existing_idx is not None:
                existing = deduped[existing_idx]
                if item.is_installed and not existing.is_installed:
                    existing.is_installed = True
                    existing.status = "INSTALLED"
                if not existing.remote_id and item.remote_id:
                    existing.remote_id = item.remote_id
                if not existing.url and item.url:
                    existing.url = item.url
                if r:
                    seen_ids[(s, r)] = existing_idx
                if fp:
                    seen_fps[fp] = existing_idx
            else:
                idx = len(deduped)
                if not item.is_game_dlc:
                    if r:
                        seen_ids[(s, r)] = idx
                    if fp:
                        seen_fps[fp] = idx
                deduped.append(item)

        return deduped

    def find_dependent_installed_mods(
        self, installed_mod_id: int, session: Session
    ) -> List[Dict[str, Any]]:
        """Identifies installed mods that declare a dependency on installed_mod_id."""
        target = session.query(InstalledMod).filter_by(id=installed_mod_id).first()
        if not target:
            return []

        target_remote_id = str(target.remote_id or "")
        target_source = target.source or "loverslab"
        target_title_lower = target.title.strip().lower()

        target_special = find_special_dependency_case(target.title)
        if not target_special and target_remote_id in SPECIAL_DEPENDENCY_REMOTE_IDS:
            for sc in SPECIAL_DEPENDENCY_CASES:
                if sc.get("remote_id") == target_remote_id:
                    target_special = sc
                    break

        other_installed = session.query(InstalledMod).filter(InstalledMod.id != installed_mod_id).all()
        if not other_installed:
            return []

        cat_ids = [m.catalog_mod_id for m in other_installed if m.catalog_mod_id]
        cat_by_id = {}
        if cat_ids:
            for c in session.query(CatalogMod).filter(CatalogMod.id.in_(cat_ids)).all():
                cat_by_id[c.id] = c

        keys = [(m.source, m.remote_id) for m in other_installed if m.remote_id]
        cat_by_key = {}
        if keys:
            conditions = [and_(CatalogMod.source == s, CatalogMod.remote_id == r) for s, r in keys]
            for c in session.query(CatalogMod).filter(or_(*conditions)).all():
                cat_by_key[(c.source, c.remote_id)] = c

        dependent_mods = []

        for other in other_installed:
            cat = None
            if other.source and other.remote_id:
                cat = cat_by_key.get((other.source, other.remote_id))
            if not cat and other.catalog_mod_id:
                cat = cat_by_id.get(other.catalog_mod_id)

            if not cat:
                continue

            req_mods = cat.get_requirements_mods_list()
            depends_on_target = False

            for req in req_mods:
                r_id = str(req.get("remote_id") or "")
                r_source = req.get("source", "loverslab")
                r_title = (req.get("title") or "").strip()

                if target_remote_id and r_id and r_id == target_remote_id and r_source == target_source:
                    depends_on_target = True
                    break

                if target_special:
                    req_special = find_special_dependency_case(r_title)
                    if req_special and req_special.get("remote_id") == target_special.get("remote_id"):
                        depends_on_target = True
                        break
                    if r_id and r_id == target_special.get("remote_id"):
                        depends_on_target = True
                        break

                if r_title and r_title.lower() == target_title_lower:
                    depends_on_target = True
                    break
                if r_title and ModMatcher.match_score(r_title, target.title) >= 0.85:
                    depends_on_target = True
                    break

            if not depends_on_target and cat.requirements_text and target_special:
                for alias in target_special.get("aliases", []):
                    if alias.lower() in cat.requirements_text.lower():
                        depends_on_target = True
                        break

            if depends_on_target:
                dependent_mods.append(
                    {
                        "id": other.id,
                        "title": other.title,
                        "folder_name": other.folder_name,
                    }
                )

        return dependent_mods
