"""
ActiveInstallationRegistry: Thread-safe centralized singleton tracking in-flight mod and dependency installations.
Prevents duplicate concurrent downloads and file race collisions when multiple mods share the same dependencies.
Supports reentrancy on the same thread to allow cascading dependencies without self-deadlock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.utils.logger import logger


@dataclass
class ActiveInstallEntry:
    """Represents an active in-flight installation task."""

    key: Tuple[str, str]  # (source, remote_id)
    title: str
    event: threading.Event = field(default_factory=threading.Event)
    started_at: datetime = field(default_factory=datetime.now)
    initiator_thread_id: int = field(default_factory=threading.get_ident)
    depth: int = 1
    success: bool = False
    message: str = ""


class ActiveInstallationRegistry:
    """Thread-safe registry for orchestrating concurrent installations and deduplicating shared dependencies."""

    _instance: Optional[ActiveInstallationRegistry] = None
    _class_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_by_key: Dict[Tuple[str, str], ActiveInstallEntry] = {}
        self._active_by_title: Dict[str, ActiveInstallEntry] = {}
        self._completed_cache: Dict[Tuple[str, str], Tuple[bool, str]] = {}
        self._completed_by_title: Dict[str, Tuple[bool, str]] = {}

    @classmethod
    def get_instance(cls) -> ActiveInstallationRegistry:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = ActiveInstallationRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resets the singleton state (useful for test isolation)."""
        with cls._class_lock:
            if cls._instance is not None:
                with cls._instance._lock:
                    for entry in cls._instance._active_by_key.values():
                        entry.event.set()
                    cls._instance._active_by_key.clear()
                    cls._instance._active_by_title.clear()
                    cls._instance._completed_cache.clear()
                    cls._instance._completed_by_title.clear()
                    if hasattr(cls._instance, "_locked_folders"):
                        cls._instance._locked_folders.clear()
            cls._instance = None

    def acquire_folder_lock(self, folder_name: str) -> bool:
        """Verrouille un nom de dossier de mod pour empêcher les écritures concurrentes."""
        clean = folder_name.strip().lower()
        with self._lock:
            if not hasattr(self, "_locked_folders"):
                self._locked_folders: set[str] = set()
            if clean in self._locked_folders:
                return False
            self._locked_folders.add(clean)
            return True

    def release_folder_lock(self, folder_name: str) -> None:
        """Libère le verrou d'un dossier de mod."""
        clean = folder_name.strip().lower()
        with self._lock:
            if hasattr(self, "_locked_folders"):
                self._locked_folders.discard(clean)

    def _normalize_title(self, title: str) -> str:
        if not title:
            return ""
        import re
        from src.utils.mod_matcher import ModMatcher

        stripped = re.sub(r"(?i)^the\s+", "", title.strip())
        cleaned = ModMatcher.clean_mod_title(stripped) or stripped
        return ModMatcher.canonical_fingerprint(cleaned) or stripped.lower()

    def register_install(
        self,
        source: str,
        remote_id: str,
        title: str = "",
    ) -> Tuple[bool, threading.Event]:
        """
        Registers an installation as active.
        Returns:
            (True, event) if this thread successfully acquired or re-entered the active installation right.
            (False, existing_event) if another thread is already installing this item.
        """
        key = (source.lower().strip() if source else "unknown", str(remote_id).strip())
        norm_title = self._normalize_title(title)
        current_thread = threading.get_ident()

        with self._lock:
            # Check by key first
            if key[1] and key in self._active_by_key:
                entry = self._active_by_key[key]
                if entry.initiator_thread_id == current_thread:
                    entry.depth += 1
                    logger.debug(
                        f"[ActiveRegistry] Réentrance autorisée pour thread {current_thread} sur {key} (depth={entry.depth})"
                    )
                    return True, entry.event
                logger.info(
                    f"[ActiveRegistry] Installation déjà active pour la clé {key} (thread {entry.initiator_thread_id})."
                )
                return False, entry.event

            # Check by normalized title
            if norm_title and norm_title in self._active_by_title:
                entry = self._active_by_title[norm_title]
                if entry.initiator_thread_id == current_thread:
                    entry.depth += 1
                    logger.debug(
                        f"[ActiveRegistry] Réentrance autorisée pour thread {current_thread} sur '{norm_title}' (depth={entry.depth})"
                    )
                    return True, entry.event
                logger.info(
                    f"[ActiveRegistry] Installation déjà active pour le titre '{norm_title}' (thread {entry.initiator_thread_id})."
                )
                return False, entry.event

            entry = ActiveInstallEntry(key=key, title=title, depth=1)
            if key[1]:
                self._active_by_key[key] = entry
            if norm_title:
                self._active_by_title[norm_title] = entry

            logger.debug(
                f"[ActiveRegistry] Enregistrement d'une nouvelle installation active: {key} ('{title}') par thread {current_thread}"
            )
            return True, entry.event

    def is_active(self, source: str, remote_id: str, title: str = "") -> bool:
        """Returns True if the item is currently being installed by any thread."""
        key = (source.lower().strip() if source else "unknown", str(remote_id).strip())
        norm_title = self._normalize_title(title)

        with self._lock:
            if key[1] and key in self._active_by_key:
                return True
            if norm_title and norm_title in self._active_by_title:
                return True
            return False

    def wait_for_active_install(
        self,
        source: str,
        remote_id: str,
        title: str = "",
        timeout: float = 180.0,
    ) -> Tuple[bool, str]:
        """
        Waits for an active installation initiated by another thread to complete.
        Returns:
            (success, message)
        """
        key = (source.lower().strip() if source else "unknown", str(remote_id).strip())
        norm_title = self._normalize_title(title)
        current_thread = threading.get_ident()

        event: Optional[threading.Event] = None
        entry: Optional[ActiveInstallEntry] = None

        with self._lock:
            if key[1] and key in self._active_by_key:
                entry = self._active_by_key[key]
                event = entry.event
            elif norm_title and norm_title in self._active_by_title:
                entry = self._active_by_title[norm_title]
                event = entry.event
            elif key in self._completed_cache:
                return self._completed_cache[key]
            elif norm_title and norm_title in self._completed_by_title:
                return self._completed_by_title[norm_title]

        if not event or not entry:
            logger.debug(f"[ActiveRegistry] Aucune installation active trouvée à attendre pour {key} ('{title}').")
            return False, "Aucune installation active en cours."

        # Anti-deadlock guard: never self-wait
        if entry.initiator_thread_id == current_thread:
            logger.debug(
                f"[ActiveRegistry] Thread {current_thread} a tenté d'attendre sa propre tâche sur {key}, reprise immédiate."
            )
            return True, "Attente sur soi-même ignorée (réentrance)"

        logger.info(
            f"[ActiveRegistry] En attente de la fin de l'installation de '{title or remote_id}' par le thread {entry.initiator_thread_id} (timeout={timeout}s)..."
        )
        finished = event.wait(timeout=timeout)

        if not finished:
            logger.warning(
                f"[ActiveRegistry] Timeout ({timeout}s) dépassé en attendant l'installation de '{title or remote_id}'."
            )
            return False, f"Timeout ({timeout}s) dépassé lors de l'attente de la dépendance."

        logger.info(
            f"[ActiveRegistry] Installation partagée terminée pour '{title or remote_id}' (succès={entry.success})."
        )
        return entry.success, entry.message

    def complete_install(
        self,
        source: str,
        remote_id: str,
        title: str = "",
        success: bool = True,
        message: str = "",
    ) -> None:
        """
        Marks an active installation as completed, accounting for reentrancy depth.
        Releases waiting threads only when top-level depth reaches 0.
        """
        key = (source.lower().strip() if source else "unknown", str(remote_id).strip())
        norm_title = self._normalize_title(title)
        current_thread = threading.get_ident()

        with self._lock:
            entry = None
            if key[1] and key in self._active_by_key:
                entry = self._active_by_key[key]
            elif norm_title and norm_title in self._active_by_title:
                entry = self._active_by_title[norm_title]

            if entry:
                if entry.initiator_thread_id == current_thread:
                    entry.depth -= 1
                    if entry.depth > 0:
                        logger.debug(
                            f"[ActiveRegistry] Libération partielle réentrante pour {key} (depth={entry.depth})"
                        )
                        return

                if entry.key[1]:
                    self._active_by_key.pop(entry.key, None)
                if key[1]:
                    self._active_by_key.pop(key, None)
                entry_norm_title = self._normalize_title(entry.title)
                if entry_norm_title:
                    self._active_by_title.pop(entry_norm_title, None)
                if norm_title:
                    self._active_by_title.pop(norm_title, None)

                entry.success = success
                entry.message = message
                entry.event.set()
                if key[1]:
                    self._completed_cache[key] = (success, message)
                if entry_norm_title:
                    self._completed_by_title[entry_norm_title] = (success, message)
                if norm_title:
                    self._completed_by_title[norm_title] = (success, message)
                logger.debug(f"[ActiveRegistry] Complétion signalée pour {key} ('{title}'): succès={success}")
            else:
                if key[1]:
                    self._completed_cache[key] = (success, message)
                if norm_title:
                    self._completed_by_title[norm_title] = (success, message)
                logger.debug(f"[ActiveRegistry] Complétion pour clé non répertoriée {key}")
