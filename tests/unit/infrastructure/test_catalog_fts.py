"""Tests unitaires pour le moteur de recherche plein-texte SQLite FTS5."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database.models import Base, CatalogMod
from src.infrastructure.database.fts_manager import CatalogFtsManager


@pytest.fixture
def fts_db():
    """Crée une base SQLite en mémoire avec la table catalog_mods et FTS5."""
    from sqlalchemy.pool import StaticPool

    # Réinitialise le statut d'initialisation pour le test
    CatalogFtsManager._initialized = False

    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    ok = CatalogFtsManager.initialize(engine)
    assert ok is True
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()


def test_fts5_sanitize_query():
    """Valide le nettoyage de requêtes pour la syntaxe MATCH de FTS5."""
    assert CatalogFtsManager.sanitize_query("") is None
    assert CatalogFtsManager.sanitize_query("   ") is None
    sanitized = CatalogFtsManager.sanitize_query('Wicked "Whims" [v4]!')
    assert sanitized is not None
    assert '"Wicked"*' in sanitized
    assert '"Whims"*' in sanitized
    assert '"v4"*' in sanitized


def test_fts5_triggers_insert_and_search(fts_db):
    """Vérifie que l'insertion d'un mod dans catalog_mods synchronise automatiquement FTS5."""
    session, _ = fts_db

    mod1 = CatalogMod(
        source="curseforge",
        remote_id="cf_101",
        title="WickedWhims Complete Package",
        author="TURBODRIVER",
        category="Gameplay",
        page_url="https://curseforge.com/sims4/101",
        tags=["18+", "Animations", "Romance"],
        description="A major overhaul mod for Sims 4 romance.",
    )
    mod2 = CatalogMod(
        source="modthesims",
        remote_id="mts_202",
        title="XML Injector v4",
        author="Scumbumbo",
        category="Game Mods",
        page_url="https://modthesims.info/202",
        tags=["Core", "Script"],
        description="Allows modders to inject custom interactions.",
    )
    session.add_all([mod1, mod2])
    session.commit()

    # Recherche 'wicked'
    matched_ids = CatalogFtsManager.search_mod_ids(session, "wicked")
    assert matched_ids is not None
    assert mod1.id in matched_ids
    assert mod2.id not in matched_ids

    # Recherche par auteur 'Scumbumbo'
    matched_ids_author = CatalogFtsManager.search_mod_ids(session, "scumbumbo")
    assert matched_ids_author is not None
    assert mod2.id in matched_ids_author
    assert mod1.id not in matched_ids_author

    # Recherche par tag 'Script'
    matched_ids_tag = CatalogFtsManager.search_mod_ids(session, "script")
    assert matched_ids_tag is not None
    assert mod2.id in matched_ids_tag


def test_fts5_triggers_delete_and_update(fts_db):
    """Vérifie que la mise à jour et la suppression répercutent correctement sur FTS5."""
    session, _ = fts_db

    mod = CatalogMod(
        source="loverslab",
        remote_id="ll_303",
        title="Original Title Alpha",
        author="AuthorX",
        category="Animations",
        page_url="https://loverslab.com/303",
        tags=["Alpha"],
    )
    session.add(mod)
    session.commit()

    # Doit être trouvé avec Alpha
    res1 = CatalogFtsManager.search_mod_ids(session, "Alpha")
    assert mod.id in res1

    # Modification du titre
    mod.title = "Updated Title Beta"
    session.commit()

    res_beta = CatalogFtsManager.search_mod_ids(session, "Beta")
    assert mod.id in res_beta

    # Suppression
    session.delete(mod)
    session.commit()

    res_deleted = CatalogFtsManager.search_mod_ids(session, "Beta")
    assert res_deleted is not None
    assert mod.id not in res_deleted
