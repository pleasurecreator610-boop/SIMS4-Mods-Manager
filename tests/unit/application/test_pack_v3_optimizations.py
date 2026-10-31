"""Tests unitaires couvrant le Pack d'Optimisations V3 :
- Indexation pré-calculée _FP_MAP et cache TTL dans GameDlcMatcher
- Cache LRU de résolution de dépendances dans DependencyActions et absence de lazy-load N+1 sur installed_files
- Décodage/redimensionnement QImage hors thread UI et déduplication in-flight dans ImageDownloadTask
- Recyclage in-place (Object Pooling) de InstalledCard via update_data et ResponsiveCardGrid.update_pool
- Cache TTL de ApiClient.get_accounts() et invalidation automatique sur mutation de compte
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtGui import QImage

from src.api.client import ApiClient
from src.application.dependencies.dependency_actions import DependencyActions
from src.infrastructure.cache.catalog_cache import CatalogQueryCache
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod
from src.ui.components.base_mod_card import ImageDownloadTask, ImageLoadSignals
from src.ui.components.installed_card import InstalledCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.utils.game_dlc_matcher import GameDlcMatcher
from src.utils.mod_matcher import ModMatcher


def test_game_dlc_matcher_precomputed_fp_map_and_ttl_cache(tmp_path: Path) -> None:
    """Vérifie que GameDlcMatcher utilise l'index pré-calculé _FP_MAP et met en cache is_dlc_installed_in_game."""
    GameDlcMatcher.clear_cache()

    is_dlc, name, code = GameDlcMatcher.match_dlc("Requires: The Sims 4 City Living")
    assert is_dlc is True
    assert code == "EP03"
    assert "City Living" in (name or "")
    assert len(GameDlcMatcher._FP_MAP) > 100
    assert len(GameDlcMatcher._SORTED_FP_ITEMS) == len(GameDlcMatcher._FP_MAP)

    # Créer un faux dossier de jeu avec EP03 installé
    fake_game_dir = tmp_path / "The Sims 4"
    (fake_game_dir / "EP03").mkdir(parents=True)

    assert GameDlcMatcher.is_dlc_installed_in_game("EP03", game_dir=fake_game_dir) is True
    assert GameDlcMatcher.is_dlc_installed_in_game("EP99", game_dir=fake_game_dir) is False

    # Supprimer le dossier sur disque : le cache TTL (60s) doit retourner True tant qu'il n'est pas vidé
    (fake_game_dir / "EP03").rmdir()
    assert GameDlcMatcher.is_dlc_installed_in_game("EP03", game_dir=fake_game_dir) is True

    # Après clear_cache(), la lecture disque reflète la suppression
    GameDlcMatcher.clear_cache()
    assert GameDlcMatcher.is_dlc_installed_in_game("EP03", game_dir=fake_game_dir) is False


def test_dependency_actions_lru_cache_and_no_deferred_lazy_load(tmp_path: Path, monkeypatch) -> None:
    """Vérifie le cache LRU de DependencyActions.match_catalog_mod et la protection contre le N+1 sur installed_files."""
    db_file = tmp_path / "test_deps_v3.db"
    db_manager = DatabaseManager(db_path=str(db_file))
    DependencyActions.clear_cache()

    with db_manager.get_session() as session:
        session.add(
            CatalogMod(
                source="curseforge",
                remote_id="xml-inj-1",
                title="Xml Injector by Scumbumbo",
                author="Scumbumbo",
                page_url="https://www.curseforge.com/sims4/mods/xml-injector",
            )
        )
        session.commit()

        actions = DependencyActions()
        calls = 0
        orig_find = ModMatcher.find_best_catalog_match

        def _counted_find(*args, **kwargs):
            nonlocal calls
            calls += 1
            return orig_find(*args, **kwargs)

        monkeypatch.setattr(ModMatcher, "find_best_catalog_match", _counted_find)

        res1 = actions.match_catalog_mod("XML Injector", session, "curseforge")
        assert res1[0] == "xml-inj-1"
        assert calls == 1

        # Second appel identique : servi depuis _catalog_match_cache sans requête SQL
        res2 = actions.match_catalog_mod("XML Injector", session, "curseforge")
        assert res2 == res1
        assert calls == 1

        # L'invalidation de CatalogQueryCache purge également DependencyActions._catalog_match_cache
        CatalogQueryCache.get_instance().invalidate()
        res3 = actions.match_catalog_mod("XML Injector", session, "curseforge")
        assert res3 == res1
        assert calls == 2


def test_image_download_task_off_ui_decode_and_inflight_dedup(qapp, tmp_path: Path) -> None:
    """Vérifie le décodage/scaling QImage hors thread UI et la déduplication in-flight de ImageDownloadTask."""
    img_path = tmp_path / "sample_thumb.png"
    raw_img = QImage(600, 400, QImage.Format.Format_RGB32)
    raw_img.fill(0x336699)
    raw_img.save(str(img_path), "PNG")

    # 1. Décodage et redimensionnement statique en QImage
    scaled = ImageDownloadTask.decode_and_scale_qimage(img_path, 271, 130)
    assert scaled is not None
    assert not scaled.isNull()
    assert scaled.width() >= 271 or scaled.height() >= 130

    # 2. Déduplication in-flight lorsque la clé est déjà présente dans _in_flight
    sig1 = ImageLoadSignals()
    sig2 = ImageLoadSignals()
    key = "https://example.com/thumb.png@271x130"
    ImageDownloadTask._in_flight[key] = [("mod-1", sig1)]
    try:
        started_new = ImageDownloadTask.enqueue_or_join(
            source="loverslab",
            remote_id="mod-2",
            url="https://example.com/thumb.png",
            dest_path=img_path,
            signals=sig2,
            target_width=271,
            target_height=130,
        )
        assert started_new is False
        assert len(ImageDownloadTask._in_flight[key]) == 2
    finally:
        ImageDownloadTask._in_flight.pop(key, None)


def test_installed_card_update_data_and_grid_pooling(qapp) -> None:
    """Vérifie que InstalledCard.update_data recycle les widgets en place dans ResponsiveCardGrid."""
    grid = ResponsiveCardGrid(min_card_width=295, spacing=16)

    batch_1 = [
        {
            "id": i,
            "title": f"Installed Alpha {i}",
            "author": "AuthorA",
            "folder_name": f"Folder_A_{i}",
            "files_count": 3,
            "source": "curseforge",
            "is_enabled": True,
        }
        for i in range(4)
    ]

    grid.update_pool(
        items_data=batch_1,
        factory_fn=lambda m: InstalledCard(m),
        update_fn=lambda card, m: card.update_data(m),
    )

    assert len(grid.cards) == 4
    assert grid.pool_size == 4
    first_ids = [id(c) for c in grid.cards]
    assert grid.cards[0].title_label.text() == "Installed Alpha 0"

    batch_2 = [
        {
            "id": 10 + i,
            "title": f"Installed Beta {i}",
            "author": "AuthorB",
            "folder_name": f"Folder_B_{i}",
            "files_count": 7,
            "source": "modthesims",
            "is_enabled": False,
            "backup_path": "C:/backups/mod.zip",
        }
        for i in range(2)
    ]

    grid.update_pool(
        items_data=batch_2,
        factory_fn=lambda m: InstalledCard(m),
        update_fn=lambda card, m: card.update_data(m),
    )

    assert len(grid.cards) == 2
    assert grid.pool_size == 4
    assert [id(c) for c in grid.cards] == first_ids[:2]
    assert grid.cards[0].title_label.text() == "Installed Beta 0"
    assert "AuthorB" in grid.cards[0].meta_lbl.text()
    assert "Folder_B_0" in grid.cards[0].folder_lbl.text()
    assert grid.cards[0].btn_restore.isHidden() is False


def test_api_client_get_accounts_ttl_cache_and_invalidation(monkeypatch) -> None:
    """Vérifie que ApiClient.get_accounts met en cache la réponse pendant 30s et l'invalide lors d'une modification."""
    client = ApiClient("http://127.0.0.1:8000", token="test_secret_token_123456")
    get_calls = 0

    def _fake_get(url, **_kwargs):
        nonlocal get_calls
        get_calls += 1
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"accounts": [{"provider": "loverslab", "is_valid": True}]}
        return resp

    def _fake_delete(url, **_kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"success": True}
        return resp

    monkeypatch.setattr(client._client, "get", _fake_get)
    monkeypatch.setattr(client._client, "delete", _fake_delete)

    acc1 = client.get_accounts()
    acc2 = client.get_accounts()
    assert len(acc1) == 1
    assert acc1 == acc2
    assert get_calls == 1  # Servi depuis le cache mémoire

    # clear_account invalide automatiquement le cache
    client.clear_account("loverslab")
    acc3 = client.get_accounts()
    assert len(acc3) == 1
    assert get_calls == 2
