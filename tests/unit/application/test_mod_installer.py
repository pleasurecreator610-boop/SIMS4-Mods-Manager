import re
import zipfile
from src.application.mods.mod_install_actions import ModInstallActions
from src.application.mods.mod_installer_service import (
    ModInstaller,
    sanitize_filename,
    sanitize_mod_folder_name,
    generate_unique_mod_folder_name,
)
from src.application.mods.mod_toggle_service import ModToggleManager
from src.database import DatabaseManager, InstalledMod
from src.core.config import AppConfig


def test_sanitize_filename():
    assert sanitize_filename('Mod: "Super/Best*Mod?"') == "Mod_SuperBestMod"


def test_sanitize_mod_folder_name():
    # 1. Strips spaces and replaces with underscores
    assert sanitize_mod_folder_name("My Great Mod") == "My_Great_Mod"

    # 2. Strips apostrophes
    assert sanitize_mod_folder_name("Kritical's Dreams") == "Kriticals_Dreams"
    assert sanitize_mod_folder_name("L’Armure d’or") == "LArmure_dor"

    # 3. Strips accents / diacritics
    assert sanitize_mod_folder_name("Objekte / Deutsche Übersetzungen") == "Objekte_Deutsche_Ubersetzungen"
    assert sanitize_mod_folder_name("Épée et château") == "Epee_et_chateau"

    # 4. Strips emojis and special symbols
    assert sanitize_mod_folder_name("Cowboy Hat - Pose Pack 🎀") == "Cowboy_Hat_Pose_Pack"
    assert sanitize_mod_folder_name("NEW ❤️ leather Trench") == "NEW_leather_Trench"

    # 5. Strict alphanumeric check: no characters other than [a-zA-Z0-9_]
    res = sanitize_mod_folder_name("Mod! @#$%^&*()_+~`=-[]\\{}|;':\",./<>?")
    assert re.match(r"^[a-zA-Z0-9_]+$", res) is not None


def test_generate_unique_mod_folder_name():
    source = "loverslab"
    title = "Kritical's Dreams of Surrender & Objekte / Deutsche Übersetzungen"
    folder = generate_unique_mod_folder_name(source, title)

    # Pure alphanumeric + underscores
    assert re.match(r"^[a-zA-Z0-9_]+$", folder) is not None
    # Must end with _xxx (3 or 4 digits)
    assert re.search(r"_\d{3,4}$", folder) is not None
    # Must start with source
    assert folder.startswith("loverslab_")
    # Must NOT contain spaces, apostrophes or accents
    assert " " not in folder
    assert "'" not in folder
    assert "’" not in folder
    assert "ü" not in folder
    assert "Ü" not in folder


def test_cleanup_deleted_mods(tmp_path, monkeypatch):
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    existing_mod_folder = mods_dir / "loverslab_TestMod_123"
    existing_mod_folder.mkdir()
    (existing_mod_folder / "test.package").write_text("dummy")

    db_path = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Add two records: one folder exists, one folder was deleted by user
    with db_mgr.get_session() as session:
        session.add(InstalledMod(title="Test Mod 1", folder_name="loverslab_TestMod_123"))
        session.add(InstalledMod(title="Deleted Mod 2", folder_name="loverslab_DeletedMod_456"))
        session.commit()

    # Run cleanup
    removed = ModInstaller.verify_and_cleanup_installed_mods()
    assert "Deleted Mod 2" in removed

    with db_mgr.get_session() as session:
        remaining = session.query(InstalledMod).all()
        assert len(remaining) == 1
        assert remaining[0].title == "Test Mod 1"


def test_install_and_ts4script_depth_fix(tmp_path, monkeypatch):
    # Setup test environment
    mods_dir = tmp_path / "The Sims 4" / "Mods"
    mods_dir.mkdir(parents=True)

    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir), auto_backup=True)
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Create a mock zip archive with a deeply nested .ts4script and a .package
    zip_path = tmp_path / "test_mod.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("subfolder/deep/core_script.ts4script", "mock ts4script content")
        z.writestr("subfolder/package1.package", "mock package content")

    ok, msg = ModInstaller.install_mod_from_file(
        file_path=zip_path,
        source="loverslab",
        custom_title="AwesomeMod",
    )
    assert ok is True

    installed_folders = list(mods_dir.glob("loverslab_AwesomeMod*"))
    assert len(installed_folders) == 1
    installed_folder = installed_folders[0]
    assert installed_folder.exists()

    # Verify that .ts4script was relocated to direct child of installed_folder (depth 1 from Mods/)
    direct_script = installed_folder / "core_script.ts4script"
    assert direct_script.exists()

    # Verify that .package is present
    package_files = list(installed_folder.rglob("*.package"))
    assert len(package_files) >= 1


def test_toggle_mod_enable_disable(tmp_path, monkeypatch):
    mods_dir = tmp_path / "The Sims 4" / "Mods"
    mods_dir.mkdir(parents=True)

    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Create mod folder with files
    mod_dir = mods_dir / "loverslab_TestToggle"
    mod_dir.mkdir()
    (mod_dir / "item.package").write_text("package data")
    (mod_dir / "logic.ts4script").write_text("script data")

    with db_mgr.get_session() as session:
        im = InstalledMod(
            title="TestToggle",
            folder_name="loverslab_TestToggle",
            source="loverslab",
            is_enabled=True,
        )
        im.set_installed_files_list(["loverslab_TestToggle/item.package", "loverslab_TestToggle/logic.ts4script"])
        session.add(im)
        session.commit()
        mod_id = im.id

    # 1. Disable mod
    ok, _ = ModToggleManager.toggle_mod(mod_id, target_state=False)
    assert ok is True
    assert (mod_dir / "item.package.disabled").exists()
    assert (mod_dir / "logic.ts4script.disabled").exists()
    assert not (mod_dir / "item.package").exists()

    # 2. Enable mod back
    ok, _ = ModToggleManager.toggle_mod(mod_id, target_state=True)
    assert ok is True
    assert (mod_dir / "item.package").exists()
    assert (mod_dir / "logic.ts4script").exists()
    assert not (mod_dir / "item.package.disabled").exists()


def test_deploy_package_depth_capping(tmp_path):
    """Vérifie que les .package imbriqués à plus de 5 sous-dossiers sont aplatis pour Sims 4."""
    mods_dir = tmp_path / "Mods"
    target_mod_dir = mods_dir / "DeepMod"
    extracted_dir = tmp_path / "extracted"

    # Crée un chemin à 6 niveaux de sous-dossiers dans extracted_dir
    deep_pkg = extracted_dir / "l1" / "l2" / "l3" / "l4" / "l5" / "l6" / "deep.package"
    deep_pkg.parent.mkdir(parents=True)
    deep_pkg.write_text("package data")

    actions = ModInstallActions()
    deployed = actions.deploy_extracted_files(extracted_dir, target_mod_dir, mods_dir)

    assert len(deployed) == 1
    deployed_path = mods_dir / deployed[0]
    assert deployed_path.exists()
    # Le fichier doit être sous target_mod_dir / l1 / l2 / l3 / l4 / deep.package (depth <= 5 from mods_dir)
    # relative_to(mods_dir).parts: ('DeepMod', 'l1', 'l2', 'l3', 'l4', 'deep.package') -> 5 dirs + 1 file
    assert len(deployed_path.relative_to(mods_dir).parts) <= 6


def test_scan_loose_files_and_toggle_uninstall(tmp_path, monkeypatch):
    """Vérifie la détection, le basculement et la désinstallation des fichiers packages/scripts isolés."""
    mods_dir = tmp_path / "The Sims 4" / "Mods"
    mods_dir.mkdir(parents=True)

    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Fichier racine lâche .package et .ts4script
    loose_pkg = mods_dir / "Standalone_Outfit.package"
    loose_pkg.write_text("loose package content")
    loose_script = mods_dir / "Standalone_Script.ts4script"
    loose_script.write_text("loose script content")

    # Scanner
    found = ModInstaller.scan_existing_mods()
    assert len(found) == 2
    folders = [f["folder"] for f in found]
    assert "Standalone_Outfit.package" in folders
    assert "Standalone_Script.ts4script" in folders

    with db_mgr.get_session() as session:
        mods = session.query(InstalledMod).all()
        assert len(mods) == 2
        pkg_mod = next(m for m in mods if "Outfit" in m.title)
        assert any("Script" in m.title for m in mods)
        pkg_mod_id = pkg_mod.id

    # Toggle disable loose package
    ok, _ = ModToggleManager.toggle_mod(pkg_mod_id, target_state=False)
    assert ok is True
    assert (mods_dir / "Standalone_Outfit.package.disabled").exists()
    assert not (mods_dir / "Standalone_Outfit.package").exists()

    # Toggle enable loose package
    ok, _ = ModToggleManager.toggle_mod(pkg_mod_id, target_state=True)
    assert ok is True
    assert (mods_dir / "Standalone_Outfit.package").exists()
    assert not (mods_dir / "Standalone_Outfit.package.disabled").exists()

    # Désinstallation du mod lâche
    ok, msg = ModInstaller.uninstall_mod(pkg_mod_id)
    assert ok is True
    assert not (mods_dir / "Standalone_Outfit.package").exists()
    with db_mgr.get_session() as session:
        assert session.query(InstalledMod).filter_by(id=pkg_mod_id).first() is None

