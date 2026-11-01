"""Système de migration de schéma versionné pour SQLite.

Gère l'application ordonnée et atomique des évolutions de base de données
via la table interne `_schema_migrations`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.infrastructure.database.models import Base, compute_title_fingerprint
from src.utils.logger import logger
from src.utils.mod_type_classifier import ModTypeClassifier


@dataclass
class Migration:
    """Représente une étape de migration de schéma avec numéro de version et fonction d'exécution."""

    version: int
    name: str
    up_fn: Callable[[Engine], None]


def _migration_001_initial_schema(engine: Engine) -> None:
    """Crée l'ensemble des tables déclaratives de base si elles n'existent pas."""
    Base.metadata.create_all(engine)


def _migration_002_add_requirements_columns(engine: Engine) -> None:
    """Ajoute les colonnes de gestion des dépendances sur catalog_mods si absentes."""
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(catalog_mods)")).fetchall()
        col_names = {r[1] for r in res}
        if "requirements_text" not in col_names:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_text TEXT"))
        if "requirements_status" not in col_names:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_status VARCHAR(50) DEFAULT 'NONE'"))
        if "requirements_mods_json" not in col_names:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_mods_json TEXT DEFAULT '[]'"))
        if "requirements_overrides_json" not in col_names:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_overrides_json TEXT DEFAULT '{}'"))
        conn.commit()


def _migration_003_fts_and_performance_indices(engine: Engine) -> None:
    """Crée les index de performance composites nécessaires si absents."""
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_source_remote ON catalog_mods (source, remote_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_source_updated ON catalog_mods (source, updated_date)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_installed_source_remote ON installed_mods (source, remote_id)")
        )
        conn.commit()


def _migration_004_add_dbpf_package_cache(engine: Engine) -> None:
    """Crée la table de cache persistant dbpf_package_cache si absente."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dbpf_package_cache (
                    file_path VARCHAR(500) PRIMARY KEY,
                    mtime FLOAT NOT NULL,
                    file_size INTEGER NOT NULL,
                    resource_count INTEGER DEFAULT 0,
                    tgi_json TEXT DEFAULT '[]'
                )
                """
            )
        )
        conn.commit()


def _migration_005_title_fingerprint_and_covering_indexes(engine: Engine) -> None:
    """Ajoute title_fingerprint indexé et les index composites couvrants avec backfill automatique."""
    with engine.connect() as conn:
        cat_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(catalog_mods)")).fetchall()}
        if "title_fingerprint" not in cat_cols:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN title_fingerprint VARCHAR(150) DEFAULT ''"))

        inst_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(installed_mods)")).fetchall()}
        if "title_fingerprint" not in inst_cols:
            conn.execute(text("ALTER TABLE installed_mods ADD COLUMN title_fingerprint VARCHAR(150) DEFAULT ''"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_catalog_title_fp ON catalog_mods (title_fingerprint)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_installed_title_fp ON installed_mods (title_fingerprint)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_catalog_updated_id ON catalog_mods (updated_date, id)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_catalog_patreon_source ON catalog_mods (patreon_status, source)")
        )

        # Backfill automatique des empreintes manquantes
        cat_rows = conn.execute(
            text("SELECT id, title FROM catalog_mods WHERE title_fingerprint IS NULL OR title_fingerprint = ''")
        ).fetchall()
        if cat_rows:
            conn.execute(
                text("UPDATE catalog_mods SET title_fingerprint = :fp WHERE id = :id"),
                [{"id": r[0], "fp": compute_title_fingerprint(r[1])} for r in cat_rows],
            )

        inst_rows = conn.execute(
            text("SELECT id, title FROM installed_mods WHERE title_fingerprint IS NULL OR title_fingerprint = ''")
        ).fetchall()
        if inst_rows:
            conn.execute(
                text("UPDATE installed_mods SET title_fingerprint = :fp WHERE id = :id"),
                [{"id": r[0], "fp": compute_title_fingerprint(r[1])} for r in inst_rows],
            )

        conn.commit()


def _migration_006_mod_type_column_and_index(engine: Engine) -> None:
    """Ajoute la colonne mod_type pré-calculée et l'index composite idx_catalog_mod_type_updated avec backfill."""
    with engine.connect() as conn:
        cat_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(catalog_mods)")).fetchall()}
        if "mod_type" not in cat_cols:
            conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN mod_type VARCHAR(40) DEFAULT 'other'"))

        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_catalog_mod_type_updated ON catalog_mods (mod_type, updated_date, id)")
        )

        rows = conn.execute(
            text("SELECT id, title, category, tags FROM catalog_mods WHERE mod_type IS NULL OR mod_type = '' OR mod_type = 'other'")
        ).fetchall()
        if rows:
            conn.execute(
                text("UPDATE catalog_mods SET mod_type = :mt WHERE id = :id"),
                [
                    {
                        "id": r[0],
                        "mt": ModTypeClassifier.classify_mod(r[1], r[2], r[3]),
                    }
                    for r in rows
                ],
            )
        conn.commit()


REGISTRY: List[Migration] = [
    Migration(1, "initial_schema", _migration_001_initial_schema),
    Migration(2, "add_requirements_columns", _migration_002_add_requirements_columns),
    Migration(3, "fts_and_performance_indices", _migration_003_fts_and_performance_indices),
    Migration(4, "add_dbpf_package_cache", _migration_004_add_dbpf_package_cache),
    Migration(5, "title_fingerprint_and_covering_indexes", _migration_005_title_fingerprint_and_covering_indexes),
    Migration(6, "mod_type_column_and_index", _migration_006_mod_type_column_and_index),
]


class MigrationRunner:
    """Exécute les migrations de schéma incrémentales sur le moteur SQLite."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _ensure_migrations_table(self) -> None:
        """Garantit l'existence de la table de suivi des migrations."""
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS _schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.commit()

    def get_applied_versions(self) -> set[int]:
        """Retourne l'ensemble des numéros de versions déjà appliquées."""
        self._ensure_migrations_table()
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT version FROM _schema_migrations ORDER BY version ASC")).fetchall()
            return {r[0] for r in rows}

    def run_pending_migrations(self) -> int:
        """Applique toutes les migrations en attente dans l'ordre croissant."""
        self._ensure_migrations_table()
        applied = self.get_applied_versions()
        count = 0

        for mig in sorted(REGISTRY, key=lambda m: m.version):
            if mig.version not in applied:
                logger.info(f"[MIGRATION] Application de la migration {mig.version:03d}_{mig.name}...")
                mig.up_fn(self.engine)
                with self.engine.connect() as conn:
                    conn.execute(
                        text("INSERT INTO _schema_migrations (version, name, applied_at) VALUES (:v, :n, :t)"),
                        {"v": mig.version, "n": mig.name, "t": datetime.now()},
                    )
                    conn.commit()
                count += 1
                logger.info(f"[MIGRATION] Migration {mig.version:03d}_{mig.name} appliquée avec succès.")

        return count
