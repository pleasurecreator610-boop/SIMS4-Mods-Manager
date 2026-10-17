"""
Level 3: Atomic Actions for Mod Updates.
Contains single-responsibility, atomic functions and classes for version comparison,
date checks, and catalog entity resolution.
"""

from datetime import datetime
import re
from typing import Any, Optional, Union

from src.database.models import CatalogMod, InstalledMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity
from src.infrastructure.database.repositories.sqlalchemy_catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
    SqlAlchemyInstalledModRepository,
)


def is_newer_version(candidate_ver: str, current_ver: str) -> Optional[bool]:
    """
    Compares two version strings. Returns True if candidate_ver > current_ver,
    False if candidate_ver <= current_ver, or None if they cannot be parsed.
    """
    c_clean = re.sub(r"^[vV\s]+", "", candidate_ver.strip())
    cur_clean = re.sub(r"^[vV\s]+", "", current_ver.strip())
    if not c_clean or not cur_clean:
        return None
    if c_clean == cur_clean:
        return False

    # Try packaging.version
    try:
        from packaging.version import parse as parse_version

        v_cand = parse_version(c_clean)
        v_cur = parse_version(cur_clean)
        return v_cand > v_cur
    except Exception:
        pass

    # Fallback to numeric segment comparison: e.g. "1.2.3" vs "1.2"
    try:
        parts_c = [int(p) for p in re.findall(r"\d+", c_clean)]
        parts_cur = [int(p) for p in re.findall(r"\d+", cur_clean)]
        if parts_c and parts_cur:
            max_len = max(len(parts_c), len(parts_cur))
            parts_c += [0] * (max_len - len(parts_c))
            parts_cur += [0] * (max_len - len(parts_cur))
            return parts_c > parts_cur
    except Exception:
        pass

    return None


def _normalize_date(d: Any) -> Optional[datetime]:
    """Helper to convert str or datetime into naive UTC-comparable datetime."""
    if not d:
        return None
    if isinstance(d, datetime):
        return d.replace(tzinfo=None)
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


class ModUpdateActions:
    """Atomic actions for comparing versions and resolving catalog references."""

    def __init__(
        self,
        installed_repo: Optional[IInstalledModRepository] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
    ):
        self._installed_repo = installed_repo or SqlAlchemyInstalledModRepository()
        self._catalog_repo = catalog_repo or SqlAlchemyCatalogRepository()

    def compare_update_availability(
        self,
        installed_mod: Union[InstalledMod, InstalledModEntity],
        catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
    ) -> bool:
        """Determines if a newer version is available in catalog."""
        if not catalog_mod:
            return False

        updated_dt = _normalize_date(getattr(catalog_mod, "updated_date", None))
        version_dt = _normalize_date(getattr(installed_mod, "version_date", None))
        installed_dt = _normalize_date(getattr(installed_mod, "installed_date", None))
        version_str = getattr(catalog_mod, "version_str", "") or ""
        installed_version_str = getattr(installed_mod, "version_str", "") or ""

        # 1. Semantic version string comparison
        if version_str and installed_version_str:
            newer = is_newer_version(version_str, installed_version_str)
            if newer is not None:
                return newer

        # 2. Explicit version date comparison
        if updated_dt and version_dt:
            return updated_dt > version_dt

        # 3. Known catalog date vs installed_date:
        # If the mod was installed on or after the catalog update was published, it is NOT an update.
        if updated_dt:
            if installed_dt and installed_dt >= updated_dt:
                return False
            if not version_dt and not installed_dt:
                return True
            if installed_dt and updated_dt > installed_dt:
                return True

        return False

    def resolve_catalog_entry(
        self, installed_mod: InstalledModEntity
    ) -> Optional[CatalogModEntity]:
        """Resolves catalog entity via repository interfaces."""
        cat_mod: Optional[CatalogModEntity] = None

        if installed_mod.remote_id and installed_mod.source:
            cat_mod = self._catalog_repo.get_by_source_and_remote_id(
                source=installed_mod.source,
                remote_id=installed_mod.remote_id,
            )
            if cat_mod and installed_mod.catalog_mod_id != cat_mod.id:
                installed_mod.catalog_mod_id = cat_mod.id
                self._installed_repo.save(installed_mod)

        if not cat_mod and installed_mod.catalog_mod_id:
            candidate = self._catalog_repo.get_by_id(installed_mod.catalog_mod_id)
            if candidate:
                if installed_mod.remote_id and (
                    candidate.remote_id != installed_mod.remote_id or candidate.source != installed_mod.source
                ):
                    installed_mod.catalog_mod_id = None
                    self._installed_repo.save(installed_mod)
                else:
                    cat_mod = candidate

        return cat_mod

    def resolve_catalog_mod_session(
        self, session, installed_mod: InstalledMod
    ) -> Optional[CatalogMod]:
        """Resolves catalog mod via an active SQLAlchemy session."""
        cat_mod = None
        if installed_mod.remote_id and installed_mod.source:
            cat_mod = (
                session.query(CatalogMod).filter_by(source=installed_mod.source, remote_id=installed_mod.remote_id).first()
            )
            if cat_mod and installed_mod.catalog_mod_id != cat_mod.id:
                installed_mod.catalog_mod_id = cat_mod.id
                session.commit()

        if not cat_mod and installed_mod.catalog_mod_id:
            candidate = session.query(CatalogMod).filter_by(id=installed_mod.catalog_mod_id).first()
            if candidate:
                if installed_mod.remote_id and (
                    candidate.remote_id != installed_mod.remote_id or candidate.source != installed_mod.source
                ):
                    installed_mod.catalog_mod_id = None
                    session.commit()
                else:
                    cat_mod = candidate

        return cat_mod
