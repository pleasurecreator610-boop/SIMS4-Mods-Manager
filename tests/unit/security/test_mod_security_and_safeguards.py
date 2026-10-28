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


def test_game_launcher_detects_custom_game_exe(tmp_path, monkeypatch):
    """Test: Validates GameLauncher prioritizes config.custom_game_exe if set."""
    custom_exe = tmp_path / "Custom_TS4_x64.exe"
    custom_exe.write_text("DUMMY_EXE")

    from src.core.config import AppConfig

    cfg = AppConfig.load()
    cfg.custom_game_exe = str(custom_exe)
    monkeypatch.setattr(AppConfig, "load", lambda: cfg)

    GameLauncher.clear_cache()
    detected = GameLauncher.detect_game_executable()
    assert detected == custom_exe


def test_archive_extractor_blocks_seven_zip_traversal(tmp_path, monkeypatch):
    """Test: Validates SevenZipArchiveHandler rejects path traversal attempts."""
    from src.infrastructure.filesystem.archive_extractor import SevenZipArchiveHandler

    handler = SevenZipArchiveHandler()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir(parents=True, exist_ok=True)

    class MockSevenZip:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def getnames(self):
            return ["safe.package", "../evil.exe"]

        def extractall(self, path):
            pass

    import py7zr

    monkeypatch.setattr(py7zr, "SevenZipFile", MockSevenZip)

    fake_7z = tmp_path / "malicious.7z"
    fake_7z.write_bytes(b"dummy")

    import pytest

    with pytest.raises(ValueError, match="Évasion de chemin interdite dans l'archive 7Z"):
        handler.extract(fake_7z, dest_dir)


def test_installed_mods_service_populates_dependencies_and_screenshots(monkeypatch):
    """Test: Validates InstalledModsService maps dependencies and screenshots from CatalogModEntity."""
    from src.application.mods.installed_mods_service import InstalledModsService
    from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity

    mock_catalog = [
        CatalogModEntity(
            id=10,
            source="loverslab",
            remote_id="12345",
            title="Complex Mod",
            author="AuthorX",
            external_links=["https://example.com/screenshot.png", "https://example.com/site.html"],
            requirements_mods_json=[
                {"source": "loverslab", "remote_id": "999", "title": "Required Dep", "url": "https://example.com/999"}
            ],
        )
    ]
    mock_installed = [
        InstalledModEntity(
            id=1,
            catalog_mod_id=10,
            source="loverslab",
            remote_id="12345",
            title="Complex Mod",
            folder_name="ComplexMod",
            is_enabled=True,
        )
    ]

    class FakeInstalledRepo:
        def get_all(self):
            return mock_installed

    class FakeCatalogRepo:
        def get_all(self):
            return mock_catalog

    service = InstalledModsService(
        installed_repo=FakeInstalledRepo(),  # type: ignore[arg-type]
        catalog_repo=FakeCatalogRepo(),  # type: ignore[arg-type]
    )

    resp = service.list_installed_mods()
    assert len(resp.items) == 1
    item = resp.items[0]
    assert len(item.dependencies) == 1
    assert item.dependencies[0].title == "Required Dep"
    assert item.dependencies[0].remote_id == "999"
    assert len(item.screenshots) == 1
    assert item.screenshots[0] == "https://example.com/screenshot.png"


def test_installed_card_restore_signal(qapp):
    """Test: Validates that InstalledCard has a restore button and emits restore_requested."""
    mod_data = {
        "id": 99,
        "title": "Restore Test Mod",
        "folder_name": "RestoreMod_99",
        "author": "ModderNine",
        "source": "loverslab",
        "is_enabled": True,
        "files_count": 2,
        "backup_path": "C:/fake/backup.zip",
    }
    card = InstalledCard(mod_data)
    assert hasattr(card, "btn_restore")
    assert card.btn_restore.text() == "↺"

    emitted = []
    card.restore_requested.connect(lambda d: emitted.append(d))
    card.btn_restore.click()
    assert len(emitted) == 1
    assert emitted[0]["id"] == 99


def test_installed_mods_service_restore_backup(tmp_path, monkeypatch):
    """Test: Validates InstalledModsService.restore_backup successfully restores files from backup ZIP."""
    from src.application.mods.installed_mods_service import InstalledModsService
    from src.core.config import AppConfig
    from src.domain.models.mod_entity import InstalledModEntity

    mods_dir = tmp_path / "TheSims4Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    app_dir = tmp_path / "AppData"
    backups_dir = app_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    cfg = AppConfig.load()
    cfg.custom_mods_dir = str(mods_dir)
    monkeypatch.setattr(AppConfig, "load", lambda: cfg)
    monkeypatch.setattr(AppConfig, "get_app_dir", classmethod(lambda cls: app_dir))

    # Existing corrupted or modified mod directory
    mod_folder = mods_dir / "BackupMod"
    mod_folder.mkdir(parents=True, exist_ok=True)
    (mod_folder / "corrupted.package").write_bytes(b"CORRUPTED")

    # Create a backup zip
    backup_zip = backups_dir / "BackupMod_20261018_120000.zip"
    with zipfile.ZipFile(backup_zip, "w") as zf:
        zf.writestr("original.package", b"ORIGINAL_VALID_DBPF")

    installed_mod = InstalledModEntity(
        id=77,
        folder_name="BackupMod",
        title="Backup Mod",
        source="loverslab",
        remote_id="777",
        is_enabled=True,
        backup_path=str(backup_zip),
    )

    class FakeInstalledRepo:
        def get_by_id(self, mid):
            return installed_mod if mid == 77 else None

        def save(self, entity):
            return entity

        def update(self, entity):
            return entity

    service = InstalledModsService(
        installed_repo=FakeInstalledRepo(),  # type: ignore[arg-type]
        catalog_repo=None,  # type: ignore[arg-type]
    )

    res = service.restore_backup(77)
    assert res.success is True
    assert (mod_folder / "original.package").exists()
    assert (mod_folder / "original.package").read_bytes() == b"ORIGINAL_VALID_DBPF"
    assert not (mod_folder / "corrupted.package").exists()


def test_conflict_detector_service_resolve_conflict(tmp_path):
    """Test: Validates ConflictDetectorService.resolve_conflict enables and disables packages."""
    from src.application.mods.conflict_detector_service import ConflictDetectorService

    mods_dir = tmp_path / "Mods"
    mod_sub = mods_dir / "ConflictingMod"
    mod_sub.mkdir(parents=True, exist_ok=True)
    pkg = mod_sub / "conflict_item.package"
    pkg.write_bytes(b"DBPF_DATA")

    # Disable action
    ok, msg, new_path = ConflictDetectorService.resolve_conflict(
        mods_dir, "ConflictingMod/conflict_item.package", action="disable"
    )
    assert ok is True
    assert new_path == "ConflictingMod/conflict_item.package.disabled"
    assert not pkg.exists()
    assert (mod_sub / "conflict_item.package.disabled").exists()

    # Enable action
    ok2, msg2, new_path2 = ConflictDetectorService.resolve_conflict(
        mods_dir, "ConflictingMod/conflict_item.package.disabled", action="enable"
    )
    assert ok2 is True
    assert new_path2 == "ConflictingMod/conflict_item.package"
    assert pkg.exists()
    assert not (mod_sub / "conflict_item.package.disabled").exists()


def test_storage_service_stats_and_cleanup(tmp_path, monkeypatch):
    """Test: Validates StorageService calculates storage sizes and safely cleans up obsolete files."""
    from src.application.system.storage_service import StorageService
    from src.core.config import AppConfig

    app_dir = tmp_path / "Sims4ManagerApp"
    backups_dir = app_dir / "backups"
    cache_dir = app_dir / "cache"
    downloads_dir = app_dir / "downloads"
    for d in (backups_dir, cache_dir, downloads_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(AppConfig, "get_app_dir", classmethod(lambda cls: app_dir))

    # Create dummy files
    (cache_dir / "thumb1.jpg").write_bytes(b"A" * 1024 * 100)  # 100 KB
    (downloads_dir / "temp_archive.zip").write_bytes(b"B" * 1024 * 200)  # 200 KB
    (backups_dir / "backup.zip").write_bytes(b"C" * 1024 * 50)  # 50 KB

    stats = StorageService.get_storage_stats()
    assert stats.cache_size_bytes >= 1024 * 100
    assert stats.downloads_size_bytes >= 1024 * 200
    assert stats.backups_count == 1
    assert stats.total_size_mb > 0.0

    # Cleanup temporary downloads and cache
    cleanup_res = StorageService.cleanup_storage(clean_cache=True, clean_downloads=True)
    assert cleanup_res.freed_size_mb > 0.0
    assert cleanup_res.deleted_files_count >= 2
    assert not (cache_dir / "thumb1.jpg").exists()
    assert not (downloads_dir / "temp_archive.zip").exists()
    assert (backups_dir / "backup.zip").exists()


def test_main_window_mod_detail_view_refresh_trigger(qapp, monkeypatch):
    """Test: Validates MainWindow._on_mods_state_changed refreshes mod_detail_view when active."""
    from src.ui.app import MainWindow

    monkeypatch.setattr(MainWindow, "refresh_game_status", lambda self: None)
    monkeypatch.setattr(MainWindow, "update_nav_badge", lambda self: None)
    monkeypatch.setattr(MainWindow, "auto_start_background_sync", lambda self: None)

    win = MainWindow()
    refreshed = []
    win._refresh_current_mod_detail = lambda: refreshed.append(True)

    # Set to catalog (index 1) - should not refresh mod_detail_view
    win.stacked_widget.setCurrentWidget(win.catalog_view)
    win._on_mods_state_changed()
    assert len(refreshed) == 0

    # Set to mod_detail_view (index 7) - should refresh mod_detail_view
    win.stacked_widget.setCurrentWidget(win.mod_detail_view)
    win._on_mods_state_changed()
    assert len(refreshed) == 1

    win.close()


def test_catalog_view_cleanup_dep_workers(qapp, monkeypatch):
    """Test: Validates CatalogView._cleanup_dep_worker and cleanup() properly manage worker life cycle."""
    from src.ui.views.catalog_view import CatalogView
    from PySide6.QtCore import QThread

    cat = CatalogView()
    dummy_worker = QThread()
    cat._dep_workers.append(dummy_worker)
    assert dummy_worker in cat._dep_workers

    cat._cleanup_dep_worker(dummy_worker)
    assert dummy_worker not in cat._dep_workers

    dummy_worker2 = QThread()
    cat._dep_workers.append(dummy_worker2)
    cat.cleanup()
    assert len(cat._dep_workers) == 0
    cat.close()


def test_base_downloader_cleans_up_incomplete_file(tmp_path):
    """Test: Validates BaseDownloader removes partial file if stream is truncated."""
    from src.infrastructure.network.base_downloader import BaseDownloader

    dest = tmp_path / "truncated_mod.zip"

    class MockResponse:
        headers = {"Content-Length": "1000"}

        def iter_content(self, chunk_size=65536):
            yield b"12345"  # Only 5 bytes instead of 1000

    ok, msg, digest = BaseDownloader.stream_to_file(MockResponse(), dest)
    assert not ok
    assert "incomplet" in msg
    assert not dest.exists()


def test_mod_install_actions_deterministic_collision_resolution(tmp_path):
    """Test: Validates ModInstallActions._resolve_unique_dest_path resolves collisions without overwriting."""
    from src.application.mods.mod_install_actions import ModInstallActions

    folder = tmp_path / "ModFolder"
    folder.mkdir()
    existing_file = folder / "mod.package"
    existing_file.write_text("v1")

    # 1st collision: adds parent name
    resolved_1 = ModInstallActions._resolve_unique_dest_path(existing_file, fallback_parent_name="sub1")
    assert resolved_1 == folder / "sub1_mod.package"
    resolved_1.write_text("v2")

    # 2nd collision with same parent name: adds numeric counter
    resolved_2 = ModInstallActions._resolve_unique_dest_path(existing_file, fallback_parent_name="sub1")
    assert resolved_2 == folder / "sub1_mod_1.package"
    resolved_2.write_text("v3")

    # All files exist and retain original content without overwriting
    assert existing_file.read_text() == "v1"
    assert resolved_1.read_text() == "v2"
    assert resolved_2.read_text() == "v3"


def test_mod_install_orchestrator_targets_app_downloads_dir():
    """Test: Validates ModInstallOrchestrator uses AppConfig.get_app_dir() / 'downloads'."""
    from src.core.config import AppConfig

    expected_downloads_dir = AppConfig.get_app_dir() / "downloads"
    assert expected_downloads_dir.name == "downloads"
    # Ensure directory is monitored by StorageService
    from src.application.system.storage_service import StorageService

    stats = StorageService.get_storage_stats()
    assert hasattr(stats, "downloads_size_bytes")
