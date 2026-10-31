"""Tests unitaires pour le cache mémoire LRU des requêtes du catalogue."""

import time
from src.infrastructure.cache.catalog_cache import CatalogQueryCache


def test_catalog_cache_make_key():
    """Vérifie la génération déterministe de clé de cache."""
    k1 = CatalogQueryCache.make_key(search="hair", page=1, limit=50)
    k2 = CatalogQueryCache.make_key(limit=50, search="hair", page=1)
    assert k1 == k2


def test_catalog_cache_set_get_invalidate():
    """Vérifie le stockage, la récupération et l'invalidation du cache."""
    cache = CatalogQueryCache(maxsize=10, ttl_seconds=60.0)

    key = "test_key_1"
    payload = {"items": [1, 2, 3], "total": 3}

    assert cache.get(key) is None
    cache.set(key, payload)
    assert cache.get(key) == payload

    cache.invalidate()
    assert cache.get(key) is None


def test_catalog_cache_ttl_expiration():
    """Vérifie que les clés expirent correctement après dépassement du TTL."""
    cache = CatalogQueryCache(maxsize=10, ttl_seconds=0.1)

    key = "expiring_key"
    cache.set(key, "data")
    assert cache.get(key) == "data"

    time.sleep(0.15)
    assert cache.get(key) is None


def test_catalog_cache_lru_eviction():
    """Vérifie l'éviction LRU lorsque la capacité maximale est atteinte."""
    cache = CatalogQueryCache(maxsize=2, ttl_seconds=60.0)

    cache.set("k1", "v1")
    cache.set("k2", "v2")

    # Accès à k1 pour le rendre récemment utilisé
    assert cache.get("k1") == "v1"

    # Ajout d'un 3ème élément : k2 doit être évincé
    cache.set("k3", "v3")

    assert cache.get("k1") == "v1"
    assert cache.get("k3") == "v3"
    assert cache.get("k2") is None
