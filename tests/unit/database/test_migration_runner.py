"""Tests unitaires pour le MigrationRunner versionné SQLite."""

from sqlalchemy import create_engine, text
from src.infrastructure.database.migrations import MigrationRunner


def test_migration_runner_applies_all_and_idempotent():
    engine = create_engine("sqlite:///:memory:")

    runner = MigrationRunner(engine)
    applied_count = runner.run_pending_migrations()
    assert applied_count >= 3

    # Idempotence: a second run should apply 0 migrations
    applied_again = runner.run_pending_migrations()
    assert applied_again == 0

    applied_versions = runner.get_applied_versions()
    assert 1 in applied_versions
    assert 2 in applied_versions
    assert 3 in applied_versions

    # Verify tables and columns were created
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(catalog_mods)")).fetchall()
        cols = {r[1] for r in res}
        assert "requirements_text" in cols
        assert "requirements_status" in cols
        assert "requirements_mods_json" in cols
