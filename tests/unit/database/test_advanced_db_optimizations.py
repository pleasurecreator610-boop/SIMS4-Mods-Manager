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
