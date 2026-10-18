from src.application.mods.mod_toggle_service import ModToggleManager
from src.database.manager import DatabaseManager
from src.database.models import InstalledMod
from src.application.game.game_service import GameDetector


def test_mod_toggle_enable_disable_lifecycle(tmp_path, monkeypatch):
    db_path = tmp_path / "test_toggle.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(GameDetector, "detect_mods_dir", classmethod(lambda cls, custom=None: mods_dir))

    # Create dummy mod folder and files
    mod_folder = mods_dir / "loverslab_ToggleTest_123"
    mod_folder.mkdir(parents=True, exist_ok=True)
    package_file = mod_folder / "test_item.package"
    package_file.write_bytes(b"DBPF" + b"\x00" * 92)
    script_file = mod_folder / "test_script.ts4script"
    script_file.write_bytes(b"PK\x03\x04" + b"\x00" * 20)

    mod_id = None
    with db_mgr.get_session() as session:
        imod = InstalledMod(
            source="loverslab",
            remote_id="12345",
            title="Toggle Test Mod",
            folder_name="loverslab_ToggleTest_123",
            is_enabled=True,
        )
        session.add(imod)
        session.commit()
        mod_id = imod.id

    # 1. Disable mod
    ok, msg = ModToggleManager.toggle_mod(mod_id, target_state=False)
    assert ok is True
    assert "désactivé" in msg

    disabled_pkg = mod_folder / "test_item.package.disabled"
    disabled_script = mod_folder / "test_script.ts4script.disabled"
    assert disabled_pkg.exists()
    assert disabled_script.exists()
    assert not package_file.exists()
    assert not script_file.exists()

    with db_mgr.get_session() as session:
        m = session.query(InstalledMod).filter_by(id=mod_id).first()
        assert m.is_enabled is False

    # 2. Idempotent check
    ok, msg = ModToggleManager.toggle_mod(mod_id, target_state=False)
    assert ok is True
    assert "already" in msg

    # 3. Re-enable mod
    ok, msg = ModToggleManager.toggle_mod(mod_id, target_state=True)
    assert ok is True
    assert "activé" in msg
    assert package_file.exists()
    assert script_file.exists()
    assert not disabled_pkg.exists()
    assert not disabled_script.exists()

    with db_mgr.get_session() as session:
        m = session.query(InstalledMod).filter_by(id=mod_id).first()
        assert m.is_enabled is True


def test_mod_toggle_errors(tmp_path, monkeypatch):
    db_path = tmp_path / "test_toggle_err.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    # Non-existent mod ID
    ok, msg = ModToggleManager.toggle_mod(999999)
    assert ok is False
    assert "not found" in msg

    # Mod exists in DB, but folder missing on disk
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(GameDetector, "detect_mods_dir", classmethod(lambda cls, custom=None: mods_dir))

    with db_mgr.get_session() as session:
        imod = InstalledMod(
            source="loverslab",
            remote_id="999",
            title="Ghost Mod",
            folder_name="non_existent_folder",
            is_enabled=True,
        )
        session.add(imod)
        session.commit()
        ghost_id = imod.id

    ok, msg = ModToggleManager.toggle_mod(ghost_id, target_state=False)
    assert ok is False
    assert "does not exist on disk" in msg


def test_mod_toggle_replaces_existing_target_without_error(tmp_path):
    from src.application.mods.mod_toggle_actions import ModToggleActions

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    mod_file = mods_dir / "item.package"
    mod_file.write_text("ACTIVE")

    # Simulate existing stale disabled file
    disabled_file = mods_dir / "item.package.disabled"
    disabled_file.write_text("STALE_DISABLED")

    actions = ModToggleActions()
    # Should replace disabled_file without FileExistsError
    new_path, rel_str = actions.toggle_file(mod_file, new_state=False, mods_dir=mods_dir)
    assert new_path == disabled_file
    assert disabled_file.read_text() == "ACTIVE"
    assert not mod_file.exists()

    # Now re-enable with existing active file
    mod_file.write_text("STALE_ACTIVE")
    new_path2, rel_str2 = actions.toggle_file(disabled_file, new_state=True, mods_dir=mods_dir)
    assert new_path2 == mod_file
    assert mod_file.read_text() == "ACTIVE"
    assert not disabled_file.exists()

