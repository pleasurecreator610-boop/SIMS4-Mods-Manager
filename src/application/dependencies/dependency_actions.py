"""
Level 3: Atomic Actions for Dependency Resolution.
Contains single-responsibility, atomic functions and classes for DLC detection,
comment classification, special case lookup, and atomic database lookups.
"""

from typing import Any, Dict, Optional, Set, Tuple
from sqlalchemy.orm import Session, defer

from src.application.dependencies.dependency_normalizer import (
    clean_dependency_title,
    detect_game_dlc_or_base_game,
)
from src.application.dependencies.dependency_special_cases import (
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
)
from src.database.models import CatalogMod
from src.utils.game_dlc_matcher import GameDlcMatcher
from src.utils.mod_matcher import ModMatcher


class DependencyActions:
    """Atomic actions for dependency matching, classification, and lookups."""

    def clean_title(self, title: str) -> str:
        """Cleans and standardizes raw dependency title string."""
        return clean_dependency_title(title or "")

    def is_comment_override(self, title: str, clean_t: str, requirements_overrides: Optional[Dict[str, str]]) -> bool:
        """Checks if a dependency title has been explicitly overridden as a comment/noise."""
        if not requirements_overrides:
            return False
        t_fp = ModMatcher.canonical_fingerprint(title)
        c_fp = ModMatcher.canonical_fingerprint(clean_t)
        for ov_key, ov_val in requirements_overrides.items():
            ov_fp = ModMatcher.canonical_fingerprint(ov_key)
            if (
                title == ov_key or clean_t == ov_key or (ov_fp and (ov_fp == t_fp or ov_fp == c_fp))
            ) and ov_val == "COMMENT":
                return True
        return False

    def detect_dlc_or_base(self, clean_t: str) -> Tuple[bool, bool, Optional[str], Optional[str]]:
        """
        Detects whether a cleaned title corresponds to the base game or an official EA DLC.
        Returns (is_base, is_dlc, dlc_name, dlc_code).
        """
        return detect_game_dlc_or_base_game(clean_t)

    def check_dlc_installed(self, dlc_code: Optional[str]) -> bool:
        """Checks if an official Game DLC pack is installed in the game."""
        in_game = GameDlcMatcher.is_dlc_installed_in_game(dlc_code)
        return bool(in_game) if in_game is not None else False

    def find_special_case(self, title: str) -> Optional[Dict[str, Any]]:
        """Looks up configured special dependency cases (e.g. WickedWhims)."""
        return find_special_dependency_case(title)

    def match_catalog_mod(
        self, title: str, session: Session, source: str = "loverslab"
    ) -> Tuple[Optional[str], Optional[str], str, str]:
        """
        Finds matching catalog mod by similarity or exact match.
        Returns (remote_id, page_url, title, source).
        """
        match_res = ModMatcher.find_best_catalog_match(title, session, min_threshold=0.70)
        if match_res:
            cat_match, _ = match_res
            return cat_match.remote_id, cat_match.page_url, cat_match.title or title, cat_match.source or source

        cat_match = (
            session.query(CatalogMod)
            .options(defer(CatalogMod.description), defer(CatalogMod.requirements_text))
            .filter((CatalogMod.title.ilike(title)) | (CatalogMod.remote_id == title))
            .first()
        )
        if cat_match:
            return cat_match.remote_id, cat_match.page_url, cat_match.title or title, cat_match.source or source

        return None, None, title, source

    def check_installed(
        self,
        source: str,
        remote_id: str,
        title: str,
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
    ) -> bool:
        """Checks whether a mod is currently installed in the user's Sims 4 directory."""
        if remote_id and (source, remote_id) in installed_by_remote:
            return True
        if title.lower() in installed_by_title:
            return True

        installed_list = list(installed_by_remote.values()) + list(installed_by_title.values())
        t_fp = ModMatcher.canonical_fingerprint(title)
        for im in installed_list:
            if im.title and ModMatcher.canonical_fingerprint(im.title) == t_fp:
                return True

        im_match = ModMatcher.find_best_installed_match(title, installed_list, min_threshold=0.85)
        return bool(im_match)

    def catalog_contains_remote_id(
        self, source: str, remote_id: str, session: Session, catalog_remote_ids: Optional[Set[Tuple[str, str]]]
    ) -> bool:
        """Verifies if remote_id exists in catalog or in special cases."""
        if remote_id in SPECIAL_DEPENDENCY_REMOTE_IDS:
            return True
        if catalog_remote_ids is not None:
            return (source, remote_id) in catalog_remote_ids
        return session.query(CatalogMod.id).filter_by(source=source, remote_id=remote_id).first() is not None
