"""
Cache mémoire LRU thread-safe pour les requêtes de recherche et filtrage du catalogue.
Évite le re-calcul SQL répété lors des navigations d'onglets et de pagination.
Invalidé automatiquement lors des écritures (upsert, install, delete).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class CatalogQueryCache:
    """Cache LRU avec TTL et invalidation globale."""

    _instance: Optional["CatalogQueryCache"] = None
    _lock = threading.Lock()

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 300.0):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._cache_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CatalogQueryCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CatalogQueryCache()
        return cls._instance

    @staticmethod
    def make_key(*args: Any, **kwargs: Any) -> str:
        """Génère une clé de cache déterministe à partir des paramètres de requête."""
        raw_parts = [str(a) for a in args]
        raw_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "|".join(raw_parts)

    def get(self, key: str) -> Optional[Any]:
        """Retourne la valeur mise en cache ou None si absente ou expirée."""
        with self._cache_lock:
            if key not in self._cache:
                return None
            val, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, value: Any) -> None:
        """Enregistre une valeur dans le cache avec éviction LRU si plein."""
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time() + self.ttl_seconds)
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def invalidate(self) -> None:
        """Purger le cache lors de toute modification de données."""
        with self._cache_lock:
            self._cache.clear()
