"""
End-to-End Mocked Flow Test Suite.
Simulates the full user journey from API lifecycle to catalog synchronization,
dependency resolution, file installation, toggle, and log verification without network dependencies.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from src.api.app import app
from src.application.catalog.sync_tracker import SyncTracker
from src.core.config import AppConfig
from src.database.manager import DatabaseManager
from src.database.models import CatalogMod
from src.providers import ProviderRegistry


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Sets up an isolated database and mock filesystem for end-to-end testing."""
    # 1. Isolated DB
    db_file = tmp_path / "e2e_sims4.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    # 2. Isolated Game / Mods folders
    fake_mods_dir = tmp_path / "The Sims 4" / "Mods"
    fake_mods_dir.mkdir(parents=True, exist_ok=True)
    fake_backup_dir = tmp_path / "backups"
    fake_backup_dir.mkdir(parents=True, exist_ok=True)

    fake_config = AppConfig(
        custom_mods_dir=str(fake_mods_dir),
        auto_backup=True,
    )
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: fake_config))
    monkeypatch.setattr(AppConfig, "get_backups_dir", classmethod(lambda cls: fake_backup_dir))

    from src.application.game.game_service import GameDetector

    monkeypatch.setattr(GameDetector, "detect_mods_dir", classmethod(lambda cls, custom=None: fake_mods_dir))

    # 3. Security auth bypass for test client
    import os

    os.environ["SIMS4_DISABLE_AUTH"] = "1"

    return {
        "db": db_mgr,
        "mods_dir": fake_mods_dir,
        "backups_dir": fake_backup_dir,
        "client": TestClient(app),
    }


def test_full_user_flow_mocked_e2e(e2e_env, monkeypatch):
    """
    Executes a complete simulated user flow:
    1. System Health & Diagnostics.
    2. Catalog Sync via background worker with mock provider.
    3. Dependency Resolution verification.
    4. Mod Installation (atomic extraction + .ts4script depth rule).
    5. Mod Toggling (enable/disable .disabled extension).
    6. System Logs and cleanup audit.
    """
    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    # =========================================================================
    # Step 1: Health & System Diagnostics
    # =========================================================================
    health_resp = client.get("/api/system/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert "version" in health_data

    # =========================================================================
    # Step 2: Catalog Scraping / Synchronization Simulation
    # =========================================================================
    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"
    mock_provider.CATEGORIES = [
        {"id": "174", "name": "WickedWhims", "default_pages": 1},
        {"id": "201", "name": "Animations", "default_pages": 1},
    ]

    # Return mock mods for category 174
    mock_provider.scrape_category_page.side_effect = [
        (
            [
                {
                    "source": "loverslab",
                    "remote_id": "3169",
                    "title": "WickedWhims",
                    "author": "TURBODRIVER",
                    "category": "WickedWhims",
                    "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
                    "thumbnail_url": "https://example.com/ww.jpg",
                    "published_date": datetime(2025, 1, 1),
                    "updated_date": datetime(2025, 6, 1),
                    "version_str": "v178",
                    "tags": ["script", "core"],
                    "patreon_status": "NONE",
                    "patreon_tier": "",
                }
            ],
            1,
        ),
        (
            [
                {
                    "source": "loverslab",
                    "remote_id": "5001",
                    "title": "Exciting Animations Pack",
                    "author": "AnimatorX",
                    "category": "Animations",
                    "page_url": "https://www.loverslab.com/files/file/5001-animations/",
                    "thumbnail_url": "https://example.com/anim.jpg",
                    "published_date": datetime(2025, 2, 1),
                    "updated_date": datetime(2025, 7, 1),
                    "version_str": "1.2",
                    "tags": ["animations"],
                    "patreon_status": "NONE",
                    "patreon_tier": "",
                }
            ],
            1,
        ),
    ]

    monkeypatch.setattr(ProviderRegistry, "list_providers", classmethod(lambda cls: [mock_provider]))
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))

    from src.application.catalog.catalog_sync_orchestrator import CatalogSyncOrchestrator

    orchestrator = CatalogSyncOrchestrator()
    SyncTracker.start(max_pages=1, categories_list=mock_provider.CATEGORIES)
    orchestrator.orchestrate_sync(max_pages=1)

    assert SyncTracker.is_running is False
    assert SyncTracker.has_error is False

    # Verify records in database
    with db.get_session() as s:
        catalog_mods = s.query(CatalogMod).all()
        assert len(catalog_mods) == 2
        titles = {m.title for m in catalog_mods}
        assert "WickedWhims" in titles
        assert "Exciting Animations Pack" in titles

    # =========================================================================
    # Step 3: Dependency Resolution
    # =========================================================================
    # Add requirements to "Exciting Animations Pack" pointing to "WickedWhims"
    with db.get_session() as s:
        anim_mod = s.query(CatalogMod).filter_by(remote_id="5001").first()
        anim_mod.set_requirements_mods_list([{"title": "WickedWhims", "source": "loverslab", "remote_id": "3169"}])
        s.commit()

    deps_resp = client.post(
        "/api/catalog/check-dependencies",
        json={
            "title": "Exciting Animations Pack",
            "page_url": "https://www.loverslab.com/files/file/5001-animations/",
            "source": "loverslab",
            "remote_id": "5001",
        },
    )
    assert deps_resp.status_code == 200
    deps_data = deps_resp.json()
    assert deps_data["can_install"] is True
    assert len(deps_data["missing_dependencies"]) == 1
    assert deps_data["missing_dependencies"][0]["title"] == "WickedWhims"

    # =========================================================================
    # Step 4: Mod Installation with Engine Rules Enforcement
    # =========================================================================
    # Mock download and package content
    import zipfile
    import io

    def mock_download_file(url, dest_path, progress_callback=None):
        # Create a mock zip containing a package and a deeply nested script to test depth flattening!
        dest_path = Path(dest_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("sub/deep/folder/core_script.ts4script", b"TS4_MOCK_BYTECODE")
            zf.writestr("sub/deep/assets.package", b"DBPF\x00\x00\x00\x00_PACKAGE")
        dest_path.write_bytes(buf.getvalue())
        return True, str(dest_path)

    mock_provider.download_mod_file = mock_download_file
    mock_provider.get_mod_details.return_value = {
        "download_urls": [{"name": "Direct Download", "url": "https://example.com/download/5001"}],
        "requirements_mods": [],
        "requirements_status": "NONE",
        "external_links": [],
        "screenshots": [],
    }

    # Install the animations mod (without cascading to WW for focused file assertion)
    install_payload = {
        "source": "loverslab",
        "remote_id": "5001",
        "title": "Exciting Animations Pack",
        "page_url": "https://www.loverslab.com/files/file/5001-animations/",
        "install_dependencies": False,
    }
    install_resp = client.post("/api/catalog/install", json=install_payload)
    assert install_resp.status_code == 200
    install_data = install_resp.json()
    assert install_data["success"] is True

    # Verify file layout on disk:
    # 1. Target directory was created under Mods/
    installed_folders = list(mods_dir.iterdir())
    assert len(installed_folders) == 1
    target_folder = installed_folders[0]

    # 2. Rule Check: .ts4script MUST be at level 1 under Mods/ (target_folder/core_script.ts4script)
    script_file = target_folder / "core_script.ts4script"
    assert script_file.exists(), "Crucial engine rule: .ts4script was not flattened to depth 1!"
    assert script_file.read_bytes() == b"TS4_MOCK_BYTECODE"

    # =========================================================================
    # Step 5: Installed Mods Management & Toggling (.disabled)
    # =========================================================================
    installed_resp = client.get("/api/installed")
    assert installed_resp.status_code == 200
    installed_data = installed_resp.json()
    installed_list = installed_data.get("items", installed_data if isinstance(installed_data, list) else [])
    assert len(installed_list) == 1
    installed_id = installed_list[0]["id"]
    assert installed_list[0]["is_enabled"] is True

    # Toggle to Disabled
    toggle_resp = client.post(f"/api/installed/{installed_id}/toggle", json={"target_state": False})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["success"] is True

    # Verify that files on disk now have .disabled suffix
    disabled_script = target_folder / "core_script.ts4script.disabled"
    assert disabled_script.exists()
    assert not script_file.exists()

    # Toggle back to Enabled
    toggle_back = client.post(f"/api/installed/{installed_id}/toggle", json={"target_state": True})
    assert toggle_back.status_code == 200
    assert toggle_back.json()["success"] is True
    assert script_file.exists()
    assert not disabled_script.exists()

    # =========================================================================
    # Step 6: Log Verification
    # =========================================================================
    logs_resp = client.get("/api/logs")
    assert logs_resp.status_code == 200
    logs_data = logs_resp.json()
    assert "items" in logs_data or "lines" in logs_data


def test_fast_standalone_mod_installation_e2e(e2e_env, monkeypatch):
    """
    Scenario: Fast E2E installation of a standalone mod (0 dependencies, e.g. Vernier Mod).
    Validates:
    - check-dependencies returns can_install=True and empty missing dependencies.
    - install-mod-stream completes with 100% progress and files created on disk.
    - InstalledMod record created in DB.
    """
    import io
    import zipfile
    from src.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    # 1. Seed catalog mod in DB
    with db.get_session() as s:
        mod = CatalogMod(
            source="loverslab",
            remote_id="51681",
            title="Vernier Mod",
            page_url="https://www.loverslab.com/files/file/51681-vernier-mod/",
            author="VernierCreator",
            requirements_status="NONE",
        )
        mod.set_requirements_mods_list([])
        mod.set_download_urls_list([{"name": "vernier.zip", "url": "https://example.com/dl/51681"}])
        s.add(mod)
        s.commit()
        cat_id = mod.id

    # 2. Check dependencies (instantaneous, 0 missing)
    deps_resp = client.post(
        "/api/catalog/check-dependencies",
        json={"catalog_mod_id": cat_id, "source": "loverslab", "title": "Vernier Mod"},
    )
    assert deps_resp.status_code == 200
    deps_data = deps_resp.json()
    assert deps_data["can_install"] is True
    assert len(deps_data["missing_dependencies"]) == 0
    assert len(deps_data["unfound_dependencies"]) == 0

    # 3. Mock provider download and details
    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"
    mock_provider.get_mod_details.return_value = {
        "download_urls": [{"name": "vernier.zip", "url": "https://example.com/dl/51681"}],
        "requirements_mods": [],
        "requirements_status": "NONE",
        "external_links": [],
        "screenshots": [],
    }

    def mock_download(url, dest_path, progress_callback=None):
        dest_path = Path(dest_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("vernier_dress.package", b"DBPF_VERNIER_ASSETS")
        dest_path.write_bytes(buf.getvalue())
        return True, str(dest_path)

    mock_provider.download_mod_file = mock_download
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))

    # 4. Install mod
    install_resp = client.post(
        "/api/catalog/install",
        json={
            "source": "loverslab",
            "remote_id": "51681",
            "title": "Vernier Mod",
            "page_url": "https://www.loverslab.com/files/file/51681-vernier-mod/",
            "install_dependencies": False,
        },
    )
    assert install_resp.status_code == 200
    assert install_resp.json()["success"] is True

    # 5. Verify on disk and in database
    with db.get_session() as s:
        inst = s.query(InstalledMod).filter_by(title="Vernier Mod").first()
        assert inst is not None
        assert inst.is_enabled is True
        mod_folder = mods_dir / inst.folder_name
        assert mod_folder.exists()
        assert (mod_folder / "vernier_dress.package").exists()


def test_fast_mod_with_wickedwhims_dependency_installation_e2e(e2e_env, monkeypatch):
    """
    Scenario: Fast E2E installation of a parent mod requiring WickedWhims.
    Validates:
    - check-dependencies detects WickedWhims as missing requirement.
    - Installation of WickedWhims dependency + parent mod.
    - Subsequent check-dependencies marks WickedWhims as already installed.
    """
    import io
    import zipfile
    from src.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    # 1. Seed WickedWhims and Confidence Cascade in DB
    with db.get_session() as s:
        ww_mod = CatalogMod(
            source="loverslab",
            remote_id="3169",
            title="WickedWhims",
            page_url="https://www.loverslab.com/files/file/3169-wickedwhims/",
            author="TURBODRIVER",
            requirements_status="NONE",
        )
        ww_mod.set_requirements_mods_list([])
        ww_mod.set_download_urls_list([{"name": "ww.zip", "url": "https://example.com/dl/3169"}])

        cascade_mod = CatalogMod(
            source="loverslab",
            remote_id="5002",
            title="Confidence Cascade",
            page_url="https://www.loverslab.com/files/file/5002-confidence-cascade/",
            author="BlackBoxMods",
            requirements_status="FOUND",
        )
        cascade_mod.set_requirements_mods_list([{"title": "WickedWhims", "source": "loverslab", "remote_id": "3169"}])
        cascade_mod.set_download_urls_list([{"name": "cascade.zip", "url": "https://example.com/dl/5002"}])

        s.add_all([ww_mod, cascade_mod])
        s.commit()
        ww_id = ww_mod.id
        cascade_id = cascade_mod.id

    # 2. Check dependencies for Confidence Cascade: WickedWhims must be missing
    deps_resp1 = client.post(
        "/api/catalog/check-dependencies",
        json={"catalog_mod_id": cascade_id, "title": "Confidence Cascade", "source": "loverslab"},
    )
    assert deps_resp1.status_code == 200
    data1 = deps_resp1.json()
    assert len(data1["missing_dependencies"]) == 1
    assert data1["missing_dependencies"][0]["title"] == "WickedWhims"
    assert len(data1["already_installed_dependencies"]) == 0

    # 3. Mock provider download and details for both mods
    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"

    def mock_get_details(url):
        if "3169" in str(url):
            return {
                "download_urls": [{"name": "ww.zip", "url": "https://example.com/dl/3169"}],
                "requirements_mods": [],
                "requirements_status": "NONE",
            }
        return {
            "download_urls": [{"name": "cascade.zip", "url": "https://example.com/dl/5002"}],
            "requirements_mods": [{"title": "WickedWhims", "source": "loverslab", "remote_id": "3169"}],
            "requirements_status": "FOUND",
        }

    mock_provider.get_mod_details.side_effect = mock_get_details

    def mock_download(url, dest_path, progress_callback=None):
        dest_path = Path(dest_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            if "3169" in str(url):
                # WickedWhims TS4 script + package
                zf.writestr("WickedWhims_Scripts.ts4script", b"WW_SCRIPT_BYTECODE")
                zf.writestr("WickedWhims_Tuning.package", b"DBPF_WW_PACKAGE")
            else:
                # Cascade package
                zf.writestr("ConfidenceCascade.package", b"DBPF_CASCADE_PACKAGE")
        dest_path.write_bytes(buf.getvalue())
        return True, str(dest_path)

    mock_provider.download_mod_file = mock_download
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))

    # 4. Install WickedWhims first
    ww_inst_resp = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": ww_id,
            "source": "loverslab",
            "remote_id": "3169",
            "title": "WickedWhims",
            "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            "install_dependencies": False,
        },
    )
    assert ww_inst_resp.status_code == 200
    assert ww_inst_resp.json()["success"] is True

    # 5. Check dependencies for Confidence Cascade again: WickedWhims is now ALREADY installed!
    deps_resp2 = client.post(
        "/api/catalog/check-dependencies",
        json={"catalog_mod_id": cascade_id, "title": "Confidence Cascade", "source": "loverslab"},
    )
    assert deps_resp2.status_code == 200
    data2 = deps_resp2.json()
    assert len(data2["missing_dependencies"]) == 0
    assert len(data2["already_installed_dependencies"]) == 1
    assert data2["already_installed_dependencies"][0]["title"] == "WickedWhims"

    # 6. Install Confidence Cascade
    cascade_inst_resp = client.post(
        "/api/catalog/install",
        json={
            "source": "loverslab",
            "remote_id": "5002",
            "title": "Confidence Cascade",
            "page_url": "https://www.loverslab.com/files/file/5002-confidence-cascade/",
            "install_dependencies": False,
        },
    )
    assert cascade_inst_resp.status_code == 200
    assert cascade_inst_resp.json()["success"] is True

    # 7. Verify both mods exist on disk in Mods/ with correct files
    with db.get_session() as s:
        ww_inst = s.query(InstalledMod).filter_by(title="WickedWhims").first()
        cas_inst = s.query(InstalledMod).filter_by(title="Confidence Cascade").first()
        assert ww_inst is not None
        assert cas_inst is not None

        ww_folder = mods_dir / ww_inst.folder_name
        cas_folder = mods_dir / cas_inst.folder_name
        assert (ww_folder / "WickedWhims_Scripts.ts4script").exists()
        assert (ww_folder / "WickedWhims_Tuning.package").exists()
        assert (cas_folder / "ConfidenceCascade.package").exists()
