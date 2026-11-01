"""Tests unitaires approfondis pour les optimisations avancées de la couche Base de Données (SQLite / FTS5 / ORM)."""

from datetime import datetime
from sqlalchemy import event, text

from src.domain.models.mod_entity import CatalogModEntity
from src.infrastructure.database.fts_manager import CatalogFtsManager
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod, InstalledMod, compute_title_fingerprint
from src.infrastructure.database.repositories.sqlalchemy_catalog_repository import SqlAlchemyCatalogRepository
from src.utils.mod_matcher import ModMatcher


def test_sqlite_pragmas_foreign_keys_wal_and_optimize(tmp_path):
    """Vérifie l'activation des pragmas SQLite avancés (foreign_keys=ON, WAL, journal_size_limit) et PRAGMA optimize."""
    db_file = tmp_path / "test_pragmas.db"
    db = DatabaseManager(str(db_file))

    with db.engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        j_mode = str(conn.execute(text("PRAGMA journal_mode")).scalar()).lower()
        j_limit = int(conn.execute(text("PRAGMA journal_size_limit")).scalar())

        assert fk == 1
        assert j_mode == "wal"
        assert j_limit == 67108864

    db.optimize()


def test_migration_005_and_auto_title_fingerprint_events(tmp_path):
    """Vérifie la migration 005, les nouveaux index couvrants et le maintien automatique de title_fingerprint."""
    db_file = tmp_path / "test_fp.db"
    db = DatabaseManager(str(db_file))

    with db.get_session() as s:
        cm = CatalogMod(
            source="curseforge",
            remote_id="cf_xml_1",
            title="The XML Injector v4.2 [TS4]",
            author="Scumbumbo",
            page_url="https://www.curseforge.com/sims4/mods/xml-injector",
        )
        im = InstalledMod(
            source="scumbumbo",
            remote_id="scumbumbo_xml_injector",
            title="XML Injector v4.0",
            folder_name="Scumbumbo_XMLInjector",
        )
        s.add_all([cm, im])
        s.commit()

        expected_fp = compute_title_fingerprint("XML Injector")
        assert cm.title_fingerprint == expected_fp
        assert im.title_fingerprint == expected_fp

        # Mise à jour du titre -> recalcul automatique de l'empreinte
        cm.title = "MC Command Center 2026.2.0"
        s.commit()
        assert cm.title_fingerprint == compute_title_fingerprint("MC Command Center")


def test_fts5_rowid_alignment_and_selective_update_trigger(tmp_path):
    """Vérifie l'alignement rowid = id en O(log N) et le non-déclenchement FTS5 sur colonnes non-textuelles."""
    db_file = tmp_path / "test_fts5_opt.db"
    db = DatabaseManager(str(db_file))

    with db.get_session() as s:
        cm = CatalogMod(
            source="lumpinou",
            remote_id="lumpinou_rpo",
            title="Relationship & Pregnancy Overhaul",
            author="Lumpinou",
            description="Complete overhaul of pregnancy and woohoo.",
            page_url="https://www.lumpinoumods.com/rpo",
        )
        s.add(cm)
        s.commit()
        mod_id = cm.id

        # Vérifie que rowid dans catalog_mods_fts est égal à mod_id
        fts_row = s.execute(
            text("SELECT rowid, title FROM catalog_mods_fts WHERE rowid = :id"),
            {"id": mod_id},
        ).fetchone()
        assert fts_row is not None
        assert fts_row[0] == mod_id
        assert "Relationship" in fts_row[1]

        # Mise à jour d'une colonne non-FTS (last_scraped_at / requirements_status)
        cm.last_scraped_at = datetime.now()
        cm.requirements_status = "RESOLVED"
        s.commit()

        # Recherche FTS5 via search_mod_ids et search_candidate_ids_any_token
        ids_exact = CatalogFtsManager.search_mod_ids(s, "Pregnancy Overhaul")
        assert ids_exact is not None and mod_id in ids_exact

        ids_any = CatalogFtsManager.search_candidate_ids_any_token(s, ["pregnancy", "nonexistenttoken"])
        assert ids_any is not None and mod_id in ids_any

        # Mise à jour d'une colonne FTS (title) -> déclenche le trigger sélectif
        cm.title = "WooHoo Wellness Collection"
        s.commit()
        ids_updated = CatalogFtsManager.search_mod_ids(s, "Wellness")
        assert ids_updated is not None and mod_id in ids_updated


def test_mod_matcher_o_log_n_fingerprint_and_fts5_lookup(tmp_path):
    """Vérifie que ModMatcher.find_best_catalog_match résout via title_fingerprint et FTS5."""
    db_file = tmp_path / "test_matcher_opt.db"
    db = DatabaseManager(str(db_file))

    with db.get_session() as s:
        cm1 = CatalogMod(
            source="littlemssam",
            remote_id="lms_1",
            title="LittleMsSam - More Buyable Venues v2.5",
            author="LittleMsSam",
            page_url="https://lms-mods.com/more-buyable-venues",
        )
        cm2 = CatalogMod(
            source="sixamcc",
            remote_id="sixam_1",
            title="Boho Minimalist Bedroom Pack",
            author="SixamCC",
            page_url="https://sixam.cc/boho-bedroom",
        )
        s.add_all([cm1, cm2])
        s.commit()

        # 1. Match direct par title_fingerprint (indépendamment du préfixe auteur ou version)
        match_fp = ModMatcher.find_best_catalog_match("More Buyable Venues v1.0", s)
        assert match_fp is not None
        assert match_fp[0].remote_id == "lms_1"
        assert match_fp[1] >= 0.95

        # 2. Match par pré-sélection FTS5 (titre partiel / variantes de tokens)
        match_fts = ModMatcher.find_best_catalog_match("Boho Minimalist Bedroom", s)
        assert match_fts is not None
        assert match_fts[0].remote_id == "sixam_1"


def test_save_batch_eliminates_n_plus_1_queries(tmp_path):
    """Vérifie que SqlAlchemyCatalogRepository.save_batch exécute un nombre constant de SELECT quel que soit N."""
    db_file = tmp_path / "test_batch.db"
    db = DatabaseManager(str(db_file))
    repo = SqlAlchemyCatalogRepository(db)

    entities = [
        CatalogModEntity(
            source="gamebanana",
            remote_id=f"gb_{i}",
            title=f"GameBanana Test Mod {i}",
            author="CreatorGB",
            category="Gameplay",
            page_url=f"https://gamebanana.com/mods/{i}",
        )
        for i in range(30)
    ]

    select_queries: list[str] = []

    def _count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.strip().upper().startswith("SELECT"):
            select_queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _count_selects)
    try:
        saved = repo.save_batch(entities)
        assert saved == 30
        # 1 seul SELECT groupé pour les 30 entités (au lieu de 30 SELECT unitaires N+1)
        assert len(select_queries) <= 2

        select_queries.clear()
        # Deuxième appel (mise à jour des 30 entités existantes)
        for ent in entities:
            ent.title = f"{ent.title} Updated"
        updated = repo.save_batch(entities)
        assert updated == 30
        assert len(select_queries) <= 2
    finally:
        event.remove(db.engine, "before_cursor_execute", _count_selects)

    assert repo.count() == 30


def test_migration_006_mod_type_column_and_index_plan(tmp_path):
    """Vérifie la migration 006, le calcul automatique de mod_type et l'utilisation de idx_catalog_mod_type_updated."""
    from src.infrastructure.database.catalog_queries import build_catalog_query
    from src.infrastructure.database.migrations import MigrationRunner

    db_file = tmp_path / "test_mod_type.db"
    db = DatabaseManager(str(db_file))

    runner = MigrationRunner(db.engine)
    assert 6 in runner.get_applied_versions()

    with db.get_session() as s:
        m_anim = CatalogMod(
            source="loverslab",
            remote_id="ll_anim_1",
            title="GreyNaya Animations Pack",
            category="Animations - WickedWhims",
            page_url="https://www.loverslab.com/files/file/1-anim/",
        )
        m_cloth = CatalogMod(
            source="patreon",
            remote_id="pat_cloth_1",
            title="Summer Silk Dress Collection",
            category="Patreon",
            tags=["clothing", "dress"],
            page_url="https://www.patreon.com/posts/1",
        )
        m_script = CatalogMod(
            source="deaderpool",
            remote_id="deaderpool_mccc",
            title="MC Command Center Gameplay Overhaul",
            category="Gameplay",
            page_url="https://deaderpool-mccc.com",
        )
        s.add_all([m_anim, m_cloth, m_script])
        s.commit()

        assert m_anim.mod_type == "animation"
        assert m_cloth.mod_type == "clothing"
        assert m_script.mod_type == "gameplay_script"

        # Vérifie que build_catalog_query filtre par mod_type via la colonne indexée
        q = build_catalog_query(s, mod_type="clothing")
        results = q.all()
        assert len(results) == 1
        assert results[0].remote_id == "pat_cloth_1"

        # Vérifie dans EXPLAIN QUERY PLAN que idx_catalog_mod_type_updated est utilisé
        plan_rows = s.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM catalog_mods "
                "WHERE mod_type = 'animation' ORDER BY updated_date DESC, id DESC LIMIT 20"
            )
        ).fetchall()
        plan_str = " ".join(str(r) for r in plan_rows)
        assert "idx_catalog_mod_type_updated" in plan_str


def test_installed_mods_service_fingerprint_enrichment_and_direct_update(tmp_path):
    """Vérifie l'enrichissement O(log N) des mods manuels via title_fingerprint et l'UPDATE direct de set_enabled."""
    from src.application.mods.installed_mods_service import InstalledModsService
    from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
        SqlAlchemyInstalledModRepository,
    )

    db_file = tmp_path / "test_installed_opt.db"
    db = DatabaseManager(str(db_file))
    cat_repo = SqlAlchemyCatalogRepository(db)
    inst_repo = SqlAlchemyInstalledModRepository(db)

    with db.get_session() as s:
        cm = CatalogMod(
            source="lumpinou",
            remote_id="lumpinou_rpo",
            title="The Relationship & Pregnancy Overhaul v3.0",
            author="Lumpinou",
            thumbnail_url="https://www.lumpinoumods.com/rpo.png",
            page_url="https://www.lumpinoumods.com/rpo",
            version_str="3.0",
        )
        # Mod installé manuellement sans catalog_mod_id ni remote_id
        im = InstalledMod(
            source="manual",
            remote_id="",
            catalog_mod_id=None,
            title="Relationship & Pregnancy Overhaul v2.5",
            folder_name="Lumpinou_RPO",
            version_str="2.5",
            is_enabled=True,
        )
        s.add_all([cm, im])
        s.commit()
        im_id = im.id

    service = InstalledModsService(installed_repo=inst_repo, catalog_repo=cat_repo)
    resp = service.list_installed_mods()
    assert resp.total == 1
    item = resp.items[0]
    assert item.author == "Lumpinou"
    assert item.thumbnail_url == "https://www.lumpinoumods.com/rpo.png"
    assert item.has_update is True

    # Vérifie que set_enabled exécute un UPDATE direct sans SELECT
    statements: list[str] = []

    def _capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.strip().upper())

    event.listen(db.engine, "before_cursor_execute", _capture_sql)
    try:
        ok = inst_repo.set_enabled(im_id, False)
        assert ok is True
        selects = [st for st in statements if st.startswith("SELECT")]
        updates = [st for st in statements if st.startswith("UPDATE")]
        assert len(selects) == 0
        assert len(updates) == 1
    finally:
        event.remove(db.engine, "before_cursor_execute", _capture_sql)

    assert inst_repo.count() == 1


def test_conflict_detector_chunked_hydration_upsert_and_orphan_purge(tmp_path, monkeypatch):
    """Vérifie l'UPSERT natif ON CONFLICT DO UPDATE, le chunking > 400 clés et la purge d'orphelins DBPF."""
    from src.application.mods.conflict_detector_service import ConflictDetectorService
    from src.infrastructure.database.models import DbpfPackageCache

    db_file = tmp_path / "test_dbpf_opt.db"
    db = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "_instance", db)

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    pkg1 = mods_dir / "mod_a.package"
    pkg2 = mods_dir / "mod_b.package"
    pkg1.write_bytes(b"DBPF_DUMMY_A")
    pkg2.write_bytes(b"DBPF_DUMMY_B")

    detector = ConflictDetectorService()
    with detector._cache_lock:
        detector._cache.clear()

    key1 = str(pkg1.resolve())
    key2 = str(pkg2.resolve())
    detector._dirty_entries[key1] = (1000.0, 12, [("0x1:0x2:0x3", "Tuning", False)])
    detector._dirty_entries[key2] = (1000.0, 12, [("0x4:0x5:0x6", "SimData", False)])
    detector._flush_dirty_cache_to_db()

    # Mise à jour via UPSERT ON CONFLICT(file_path) DO UPDATE
    detector._dirty_entries[key1] = (2000.0, 24, [("0x1:0x2:0x3", "Tuning", False), ("0x7:0x8:0x9", "STBL", True)])
    detector._flush_dirty_cache_to_db()

    with db.get_session() as s:
        row1 = s.query(DbpfPackageCache).filter_by(file_path=key1).first()
        assert row1 is not None
        assert row1.file_size == 24
        assert row1.resource_count == 2

    # Test hydratation par lots (> 450 chemins simulés)
    with detector._cache_lock:
        detector._cache.clear()
    fake_paths = [pkg1, pkg2] + [mods_dir / f"fake_{i}.package" for i in range(450)]
    detector._hydrate_cache_from_db(fake_paths)
    assert key1 in detector._cache
    assert detector._cache[key1][1] == 24

    # Suppression de pkg2 -> purge automatique des orphelins
    pkg2.unlink()
    purged = detector.prune_orphan_cache_entries([pkg1], mods_dir=mods_dir)
    assert purged == 1
    with db.get_session() as s:
        assert s.query(DbpfPackageCache).filter_by(file_path=key2).first() is None
        assert s.query(DbpfPackageCache).filter_by(file_path=key1).first() is not None


def test_save_batch_and_upsert_mods_batch_intra_batch_dedup(tmp_path):
    """Vérifie que les doublons intra-lot (source, remote_id) sont fusionnés sans IntegrityError."""
    from src.application.catalog.catalog_sync_actions import CatalogSyncActions

    db_file = tmp_path / "test_dedup_batch.db"
    db = DatabaseManager(str(db_file))
    repo = SqlAlchemyCatalogRepository(db)
    actions = CatalogSyncActions(db)

    # 1. Doublon intra-lot dans CatalogSyncActions.upsert_mods_batch
    with db.get_session() as s:
        new_c, upd_c = actions.upsert_mods_batch(
            s,
            [
                {
                    "source": "curseforge",
                    "remote_id": "dup_100",
                    "title": "Duplicate Mod Initial",
                    "author": "AuthorA",
                    "page_url": "https://www.curseforge.com/sims4/mods/dup-100",
                },
                {
                    "source": "curseforge",
                    "remote_id": "dup_100",
                    "title": "Duplicate Mod Enriched",
                    "author": "AuthorA",
                    "thumbnail_url": "https://www.curseforge.com/thumb.png",
                    "page_url": "https://www.curseforge.com/sims4/mods/dup-100",
                },
            ],
            default_category="Gameplay",
        )
        assert new_c == 1
        assert upd_c == 0

    found = repo.get_by_source_and_remote_id("curseforge", "dup_100")
    assert found is not None
    assert found.title == "Duplicate Mod Enriched"
    assert found.thumbnail_url == "https://www.curseforge.com/thumb.png"

    # 2. Doublon intra-lot dans SqlAlchemyCatalogRepository.save_batch
    saved = repo.save_batch(
        [
            CatalogModEntity(
                source="modthesims",
                remote_id="mts_dup_1",
                title="MTS Mod v1",
                page_url="https://modthesims.info/d/1",
            ),
            CatalogModEntity(
                source="modthesims",
                remote_id="mts_dup_1",
                title="MTS Mod v2",
                page_url="https://modthesims.info/d/1",
            ),
        ]
    )
    assert saved == 2
    mts_mod = repo.get_by_source_and_remote_id("modthesims", "mts_dup_1")
    assert mts_mod is not None
    assert mts_mod.title == "MTS Mod v2"

