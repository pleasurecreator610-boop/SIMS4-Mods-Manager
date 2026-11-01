"""
Level 3: Atomic Actions for Dependency Resolution.
Contains single-responsibility, atomic functions and classes for DLC detection,
comment classification, special case lookup, and atomic database lookups with LRU caching.
"""

from collections import OrderedDict
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session, defer

from src.application.dependencies.dependency_normalizer import (
    clean_dependency_title,
    detect_game_dlc_or_base_game,
)
from src.application.dependencies.dependency_special_cases import (
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
)
from src.infrastructure.database.models import CatalogMod
from src.utils.game_dlc_matcher import GameDlcMatcher
from src.utils.mod_matcher import ModMatcher

_LEADING_THE_RE = re.compile(r"(?i)^the\s+")


class DependencyActions:
    """Atomic actions for dependency matching, classification, and lookups."""

    _catalog_match_cache: OrderedDict[Tuple[int, str, str], Tuple[Optional[str], Optional[str], str, str]] = (
        OrderedDict()
    )
    _cache_lock = threading.Lock()
    _MAX_CACHE_SIZE = 512

    @classmethod
    def clear_cache(cls) -> None:
        """Vide le cache LRU de résolution de dépendances sur le catalogue."""
        with cls._cache_lock:
            cls._catalog_match_cache.clear()

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

    def find_special_case(self, title: str, url: str = "", remote_id: str = "") -> Optional[Dict[str, Any]]:
        """Looks up configured special dependency cases (Deaderpool, Scumbumbo, Lumpinou, Wicked.cc, Basemental)."""
        return find_special_dependency_case(title, url=url, remote_id=remote_id)

    def match_catalog_mod(
        self, title: str, session: Session, source: str = "loverslab"
    ) -> Tuple[Optional[str], Optional[str], str, str]:
        """
        Finds matching catalog mod by similarity or exact match with LRU caching.
        Returns (remote_id, page_url, title, source).
        """
        bind_id = id(getattr(session, "bind", session))
        cache_key = (bind_id, (title or "").strip().lower(), (source or "loverslab").lower())

        with self._cache_lock:
            if cache_key in self._catalog_match_cache:
                self._catalog_match_cache.move_to_end(cache_key)
                return self._catalog_match_cache[cache_key]

        match_res = ModMatcher.find_best_catalog_match(title, session, min_threshold=0.70)
        if match_res:
            cat_match, _ = match_res
            res = (cat_match.remote_id, cat_match.page_url, cat_match.title or title, cat_match.source or source)
        else:
            cat_match = (
                session.query(CatalogMod)
                .options(defer(CatalogMod.description), defer(CatalogMod.requirements_text))
                .filter((CatalogMod.title.ilike(title)) | (CatalogMod.remote_id == title))
                .first()
            )
            if cat_match and isinstance(getattr(cat_match, "remote_id", None), str):
                res = (cat_match.remote_id, cat_match.page_url, cat_match.title or title, cat_match.source or source)
            else:
                res = (None, None, title, source)

        with self._cache_lock:
            self._catalog_match_cache[cache_key] = res
            if len(self._catalog_match_cache) > self._MAX_CACHE_SIZE:
                self._catalog_match_cache.popitem(last=False)

        return res

    @staticmethod
    def build_installed_index(
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
    ) -> Tuple[List[Any], Set[str]]:
        """Pre-computes deduplicated installed mods list and canonical fingerprint set in O(N)."""
        seen_ids: Set[int] = set()
        installed_list: List[Any] = []
        installed_fp_set: Set[str] = set()
        for im in (*installed_by_remote.values(), *installed_by_title.values()):
            obj_id = id(im)
            if obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)
            installed_list.append(im)
            im_fp = getattr(im, "_cached_title_fp", None)
            if im_fp is None:
                im_title = getattr(im, "title", None)
                if im_title and isinstance(im_title, str):
                    im_s = _LEADING_THE_RE.sub("", im_title.strip())
                    im_fp = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title(im_s) or im_s)
                else:
                    im_fp = ""
                try:
                    im._cached_title_fp = im_fp
                except Exception:
                    pass
            if im_fp:
                installed_fp_set.add(im_fp)
        return installed_list, installed_fp_set

    def check_installed(
        self,
        source: str,
        remote_id: str,
        title: str,
        installed_by_remote: Dict[Tuple[str, str], Any],
        installed_by_title: Dict[str, Any],
        precomputed_index: Optional[Tuple[List[Any], Set[str]]] = None,
    ) -> bool:
        """Checks whether a mod is currently installed in the user's Sims 4 directory."""
        if remote_id:
            if (source, remote_id) in installed_by_remote:
                return True
            if remote_id in SPECIAL_DEPENDENCY_REMOTE_IDS:
                for _inst_src, inst_rid in installed_by_remote:
                    if inst_rid == remote_id:
                        return True
        if title.lower() in installed_by_title:
            return True

        installed_list, installed_fp_set = precomputed_index or self.build_installed_index(
            installed_by_remote, installed_by_title
        )

        title_str = title if isinstance(title, str) else str(title or "")
        stripped_t = _LEADING_THE_RE.sub("", title_str.strip())
        t_fp = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title(stripped_t) or stripped_t)
        if t_fp and t_fp in installed_fp_set:
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
