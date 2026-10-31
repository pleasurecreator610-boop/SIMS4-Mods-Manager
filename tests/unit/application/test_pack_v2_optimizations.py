"""Tests unitaires couvrant le Pack d'Optimisations V2 et la réorganisation DRY :
- Recyclage (Object Pooling) de ModCard et ResponsiveCardGrid.update_pool
- Parsing DBPF zero-copy (mmap) et persistance SQLite DbpfPackageCache dans ConflictDetectorService
- Scraping incrémental (Delta Sync) avec arrêt précoce après 2 pages consécutives inchangées
- Mutualisation DRY de BaseSourceProvider et BaseIPSForumProvider
"""

from __future__ import annotations

from pathlib import Path
import struct
from typing import Any, Dict, List, Tuple

from plugins.loverslab.provider import LoversLabProvider
from plugins.nsfwmods.provider import NSFWModsProvider
from src.application.catalog.catalog_sync_actions import CatalogSyncActions
from src.application.catalog.catalog_sync_coordinator import CatalogSyncCoordinator
from src.application.catalog.sync_tracker import SyncTracker
from src.application.mods.conflict_detector_service import ConflictDetectorService
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import DbpfPackageCache
from src.infrastructure.filesystem.dbpf_parser import DbpfParser
from src.providers.base import BaseSourceProvider
from src.providers.common.ips_base import BaseIPSForumProvider
from src.ui.components.mod_card import ModCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid


def _create_synthetic_dbpf_package(path: Path, tgi_list: List[Tuple[int, int, int]]) -> None:
    """Crée un fichier .package DBPF 2.1 synthétique valide contenant les clés TGI fournies."""
    # Construire l'index Sims 4 (flags = 0 -> Type 4B, Group 4B, Instance 8B, Offset 4B, Size 4B, Decomp 4B, Comp 4B)
    index_bytes = bytearray(struct.pack("<I", 0))
    for r_type, r_group, r_inst in tgi_list:
        index_bytes.extend(
            struct.pack(
                "<IIQIIII",
                r_type,
                r_group,
                r_inst,
                96,  # file_offset
                16,  # file_size
                16,  # decompressed_size
                0,  # compression flags
            )
        )

    header = bytearray(96)
    struct.pack_into("<4sII", header, 0, b"DBPF", 2, 1)
    struct.pack_into("<I", header, 40, len(tgi_list))  # index_record_count
    struct.pack_into("<I", header, 44, 96)  # index_pos_low
    struct.pack_into("<I", header, 48, len(index_bytes))
    struct.pack_into("<Q", header, 64, 96)  # index_pos_64

    path.write_bytes(bytes(header) + bytes(index_bytes))


def test_mod_card_update_data_and_grid_object_pooling(qapp) -> None:
    """Vérifie que ResponsiveCardGrid.update_pool recycle les instances ModCard existantes sans les recréer."""
    grid = ResponsiveCardGrid(min_card_width=250, spacing=14)

    batch_1 = [
        {"title": f"Mod Alpha {i}", "author": "CreatorA", "category": "Scripts", "source": "loverslab"}
        for i in range(5)
    ]

    grid.update_pool(
        items_data=batch_1,
        factory_fn=lambda m: ModCard(m),
        update_fn=lambda card, m: card.update_data(m),
    )

    assert len(grid.cards) == 5
    assert grid.pool_size == 5
    first_batch_instances = [id(c) for c in grid.cards]
    assert grid.cards[0].title_label.text() == "Mod Alpha 0"

    # Second lot de 3 éléments : les 3 premières instances doivent être recyclées in-place
    batch_2 = [
        {"title": f"Mod Beta {i}", "author": "CreatorB", "category": "CAS", "source": "curseforge"} for i in range(3)
    ]

    grid.update_pool(
        items_data=batch_2,
        factory_fn=lambda m: ModCard(m),
        update_fn=lambda card, m: card.update_data(m),
    )

    assert len(grid.cards) == 3
    assert grid.pool_size == 5  # Le pool conserve les 5 widgets alloués
    assert [id(c) for c in grid.cards] == first_batch_instances[:3]
    assert grid.cards[0].title_label.text() == "Mod Beta 0"
    assert "CreatorB" in grid.cards[0].meta_label.text()


def test_dbpf_mmap_parser_and_sqlite_persistent_conflict_cache(tmp_path: Path, monkeypatch) -> None:
    """Vérifie le parsing DBPF via mmap et la persistance SQLite DbpfPackageCache dans ConflictDetectorService."""
    db_file = tmp_path / "test_conflicts.db"
    db_manager = DatabaseManager(db_path=str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_manager))

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    pkg_a = mods_dir / "ModA.package"
    pkg_b = mods_dir / "ModB.package"
    shared_tgi = (0x03B33DDF, 0x00000000, 0x1122334455667788)
    _create_synthetic_dbpf_package(pkg_a, [shared_tgi, (0x034AEECB, 0, 0x9999)])
    _create_synthetic_dbpf_package(pkg_b, [shared_tgi])

    # 1. Vérifier que DbpfParser.parse_index (mmap) extrait bien les clés
    entries_a = DbpfParser.parse_index(pkg_a)
    assert len(entries_a) == 2
    assert entries_a[0].key.instance_id == 0x1122334455667788

    # 2. Premier scan : parse et persiste dans SQLite DbpfPackageCache
    ConflictDetectorService._cache.clear()
    service = ConflictDetectorService()
    report_1 = service.detect_conflicts(mods_dir)
    assert report_1.total_packages_scanned == 2
    assert report_1.conflict_count == 1
    assert report_1.conflicts[0].conflicting_packages == ["ModA.package", "ModB.package"]

    with db_manager.get_session() as session:
        cached_rows = session.query(DbpfPackageCache).all()
        assert len(cached_rows) == 2

    # 3. Vider le cache mémoire et vérifier que le second scan hydrate depuis SQLite sans appeler parse_index
    ConflictDetectorService._cache.clear()
    parse_calls = 0

    class FailingParser(DbpfParser):
        @classmethod
        def parse_index(cls, file_path: Path):
            nonlocal parse_calls
            parse_calls += 1
            return super().parse_index(file_path)

    service_cached = ConflictDetectorService(parser=FailingParser)
    report_2 = service_cached.detect_conflicts(mods_dir)
    assert parse_calls == 0
    assert report_2.conflict_count == 1


def test_delta_scraping_early_stop_in_background_mode(tmp_path: Path, monkeypatch) -> None:
    """Vérifie que CatalogSyncCoordinator s'arrête après 2 pages consécutives inchangées en mode background."""
    db_file = tmp_path / "test_delta_sync.db"
    db_manager = DatabaseManager(db_path=str(db_file))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    actions = CatalogSyncActions(db_manager=db_manager)
    coordinator = CatalogSyncCoordinator(actions=actions, db_manager=db_manager)

    # Pré-insérer les mods des pages 1, 2, 3 pour qu'ils soient déjà connus et inchangés
    with db_manager.get_session() as session:
        for page_idx in range(1, 6):
            actions.upsert_mods_batch(
                session=session,
                mods_data=[
                    {
                        "source": "loverslab",
                        "remote_id": f"mod-{page_idx}",
                        "title": f"Existing Mod {page_idx}",
                        "author": "Author",
                        "page_url": f"https://example.com/mod-{page_idx}",
                    }
                ],
                default_category="Gameplay",
            )

    scraped_pages: List[int] = []

    class DummyProvider:
        provider_name = "loverslab"

        def scrape_category_page(self, category: Dict[str, Any], page: int = 1):
            scraped_pages.append(page)
            return (
                [
                    {
                        "source": "loverslab",
                        "remote_id": f"mod-{page}",
                        "title": f"Existing Mod {page}",
                        "author": "Author",
                        "page_url": f"https://example.com/mod-{page}",
                    }
                ],
                5,
            )

    category = {"id": "10", "name": "Gameplay", "default_pages": 5}
    SyncTracker.start(max_pages=5)

    # En mode background, le scraping doit s'arrêter dès la page 2 (2 pages consécutives sans nouveauté ni modif)
    coordinator.sync_category(
        category=category,
        provider=DummyProvider(),
        max_pages=5,
        tracker=SyncTracker,
        is_background=True,
    )
    assert scraped_pages == [1, 2]
    assert SyncTracker.pages_completed == 5

    # En mode manuel (is_background=False), toutes les 5 pages sont parcourues
    scraped_pages.clear()
    SyncTracker.start(max_pages=5)
    coordinator.sync_category(
        category=category,
        provider=DummyProvider(),
        max_pages=5,
        tracker=SyncTracker,
        is_background=False,
    )
    assert scraped_pages == [1, 2, 3, 4, 5]


def test_dry_inheritance_base_providers() -> None:
    """Vérifie que LoversLabProvider et NSFWModsProvider héritent tous deux de BaseIPSForumProvider et BaseSourceProvider."""
    assert issubclass(LoversLabProvider, BaseIPSForumProvider)
    assert issubclass(NSFWModsProvider, BaseIPSForumProvider)
    assert issubclass(BaseIPSForumProvider, BaseSourceProvider)
