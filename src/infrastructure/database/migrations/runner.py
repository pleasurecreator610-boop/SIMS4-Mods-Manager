"""Système de migration de schéma versionné pour SQLite.

Gère l'application ordonnée et atomique des évolutions de base de données
via la table interne `_schema_migrations`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.infrastructure.database.models import Base
from src.utils.logger import logger


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
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_source_remote ON catalog_mods (source, remote_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_source_updated ON catalog_mods (source, updated_date)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_installed_source_remote ON installed_mods (source, remote_id)")
        )
        conn.commit()


REGISTRY: List[Migration] = [
    Migration(1, "initial_schema", _migration_001_initial_schema),
    Migration(2, "add_requirements_columns", _migration_002_add_requirements_columns),
    Migration(3, "fts_and_performance_indices", _migration_003_fts_and_performance_indices),
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
