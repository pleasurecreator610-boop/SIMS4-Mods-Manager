"""
Tests unitaires pour les garde-fous de sécurité, l'intégrité du système de fichiers
et les nouvelles fonctionnalités de gestion des mods.
"""

import io
import zipfile

from src.application.game.game_launcher import GameLauncher
from src.application.mods.mod_install_actions import ModInstallActions
from src.application.mods.mod_install_coordinator import ModInstallCoordinator
from src.application.mods.mod_installer_service import ModInstaller
from src.application.mods.mod_update_actions import is_newer_version
from src.database.models import InstalledMod
from src.ui.components.installed_card import InstalledCard


def test_uninstall_mod_rejects_empty_or_malicious_folder(tmp_path, monkeypatch):
    """
    BUG-01 Test: Ensure uninstall_mod NEVER deletes the parent mods_dir
    when folder_name is empty, dot, slash or a traversal path.
    """
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "important_keep.package").write_text("DO_NOT_DELETE")

    from src.application.game.game_detector import GameDetector
    monkeypatch.setattr(GameDetector, "detect_mods_dir", classmethod(lambda cls, custom=None: mods_dir))

    from src.database.manager import DatabaseManager
    db = DatabaseManager.get_instance()

    with db.get_session() as s:
        # 1. Mod with empty folder name
        m1 = InstalledMod(title="Dangerous Mod Empty", folder_name="", source="manual")
        # 2. Mod with dot folder name
        m2 = InstalledMod(title="Dangerous Mod Dot", folder_name=".", source="manual")
        # 3. Mod with parent traversal
        m3 = InstalledMod(title="Dangerous Mod Traversal", folder_name="../", source="manual")
        s.add_all([m1, m2, m3])
        s.commit()
        id1, id2, id3 = m1.id, m2.id, m3.id

    # Test uninstall attempt on empty folder_name
    ok1, msg1 = ModInstaller.uninstall_mod(id1)
    assert ok1 is False
    assert (mods_dir / "important_keep.package").exists()
    assert mods_dir.exists()

    # Test uninstall attempt on dot folder_name
    ok2, msg2 = ModInstaller.uninstall_mod(id2)
    assert ok2 is False
    assert (mods_dir / "important_keep.package").exists()
    assert mods_dir.exists()

    # Test uninstall attempt on traversal folder_name
    ok3, msg3 = ModInstaller.uninstall_mod(id3)
    assert ok3 is False
    assert (mods_dir / "important_keep.package").exists()
    assert mods_dir.exists()


def test_semantic_version_comparison():
    """
    BUG-08 Test: Validates is_newer_version compares semantically
    and prevents false-positive update alerts.
    """
    # Newer versions
    assert is_newer_version("2.0", "1.9") is True
    assert is_newer_version("v1.5.1", "v1.5.0") is True
    assert is_newer_version("1.10", "1.9") is True

    # Same versions
    assert is_newer_version("1.0.0", "1.0") is False
    assert is_newer_version("v2.0", "2.0") is False
    assert is_newer_version("1.5", "1.5") is False

    # Older versions (candidate is older than current -> do NOT update)
    assert is_newer_version("1.9", "2.0") is False
    assert is_newer_version("1.4.9", "1.5.0") is False


def test_user_config_preservation_on_update(tmp_path, monkeypatch):
    """
    BUG-02 Test: Validates that when a mod is updated, existing user .cfg and .ini files
    are preserved and restored into the updated folder.
    """
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    mod_folder = mods_dir / "TestMCCC"
    mod_folder.mkdir(parents=True, exist_ok=True)

    # Pre-existing user settings
    (mod_folder / "mc_settings.cfg").write_text("USER_CUSTOM_SETTINGS_DATA")
    (mod_folder / "mc_cmd_center.package").write_text("OLD_PACKAGE_V1")

    from src.database.manager import DatabaseManager
    db = DatabaseManager.get_instance()

    with db.get_session() as s:
        existing = InstalledMod(
            title="MC Command Center",
            folder_name="TestMCCC",
            source="manual",
            remote_id="mccc",
        )
        existing.set_installed_files_list(["TestMCCC/mc_cmd_center.package", "TestMCCC/mc_settings.cfg"])
        s.add(existing)
        s.commit()

    # Create new version archive with only new package (no cfg)
    archive_path = tmp_path / "mccc_v2.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mc_cmd_center.package", b"NEW_PACKAGE_V2")
    archive_path.write_bytes(buf.getvalue())

    coordinator = ModInstallCoordinator()
    ok, msg = coordinator.coordinate_file_install(
        file_path=archive_path,
        mods_dir=mods_dir,
        custom_title="MC Command Center",
        source="manual",
    )
    assert ok is True
    # The new package was installed
    assert (mod_folder / "mc_cmd_center.package").read_text() == "NEW_PACKAGE_V2"
    # The user configuration was preserved and restored!
    assert (mod_folder / "mc_settings.cfg").exists()
    assert (mod_folder / "mc_settings.cfg").read_text() == "USER_CUSTOM_SETTINGS_DATA"


def test_nested_archive_and_companion_files_deployment(tmp_path):
    """
    BUG-03 & BUG-04 Test: Validates recursive nested archive unpacking
    and deployment of companion configuration files (.cfg, .ini, .json).
    """
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    target_mod_dir = mods_dir / "NestedMod"
    extract_dir = tmp_path / "staging_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Inner zip containing a .package
    inner_zip_bytes = io.BytesIO()
    with zipfile.ZipFile(inner_zip_bytes, "w") as zf:
        zf.writestr("addon.package", b"DBPF_ADDON")
    (extract_dir / "inner.zip").write_bytes(inner_zip_bytes.getvalue())

    # Companion config files and main package
    (extract_dir / "main.package").write_bytes(b"DBPF_MAIN")
    (extract_dir / "tuning.json").write_text('{"key": "value"}')
    (extract_dir / "config.ini").write_text("[Settings]\nlevel=1")
    # Ignored OS junk
    (extract_dir / ".DS_Store").write_bytes(b"OS_JUNK")

    actions = ModInstallActions()
    installed = actions.deploy_extracted_files(
        extracted_dir=extract_dir,
        target_mod_dir=target_mod_dir,
        mods_dir=mods_dir,
    )

    # Check files deployed
    assert (target_mod_dir / "main.package").exists()
    assert (target_mod_dir / "tuning.json").exists()
    assert (target_mod_dir / "config.ini").exists()
    # Nested archive was unpacked and addon.package was deployed
    assert any("addon.package" in f for f in installed)
    # OS junk ignored
    assert not (target_mod_dir / ".DS_Store").exists()


def test_installed_card_toggle_signal(qapp):
    """
    BUG-06 Test: Validates that InstalledCard has a toggle button
    and emits toggle_requested when clicked.
    """
    mod_data = {
        "id": 42,
        "title": "Awesome Gameplay Mod",
        "folder_name": "AwesomeMod_123",
        "author": "ModderOne",
        "source": "loverslab",
        "is_enabled": True,
        "files_count": 3,
    }
    card = InstalledCard(mod_data)
    assert hasattr(card, "btn_toggle")
    assert card.btn_toggle.text() == "🟢 Actif"

    emitted = []
    card.toggle_requested.connect(lambda d: emitted.append(d))

    card.btn_toggle.click()
    assert len(emitted) == 1
    assert emitted[0]["id"] == 42


def test_game_running_detection():
    """
    BUG-11 Test: Validates GameLauncher.is_game_running() executes without error.
    """
    is_running = GameLauncher.is_game_running()
    assert isinstance(is_running, bool)
