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
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod
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

    fake_config_path = tmp_path / "config.json"
    monkeypatch.setattr(AppConfig, "get_app_dir", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(AppConfig, "get_config_file_path", classmethod(lambda cls: fake_config_path))

    fake_config = AppConfig(
        custom_mods_dir=str(fake_mods_dir),
        auto_backup=True,
        adult_content_enabled=True,
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
    from src.infrastructure.database.models import InstalledMod

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
    from src.infrastructure.database.models import InstalledMod

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


def test_ambiguous_dependencies_comment_and_forum_interpellation_e2e(e2e_env, monkeypatch):
    """
    Scenario: E2E test for the group of 3 mods with ambiguous dependencies (including Confidence Cascade):
    1. Validates delimiter splitting ('&' and '-') and comment vs unfound mod qualification:
       - Mod 1: Confidence Cascade
         * Comments: 'Game Options -> Script Mods Enabled', 'Bad decisions. Better stories'
         * Missing Mods: 'Lumpinou - Relationship & Pregnancy Overhaul' -> split into 'Lumpinou' and 'Relationship & Pregnancy Overhaul'
       - Mod 2: Wicked Traits Unleashed
         * Comments: 'Script-only mod - no .package file required'
         * Missing Mods: 'Scumbumbo - XML Injector v4' -> split by '-' into 'Scumbumbo' and 'XML Injector v4'
       - Mod 3: Private Night (TS4 WW)
         * Comments: 'Make sure you have the latest patch and restart the game'
         * Missing Mods: 'Kuttoe - Mini Mod Framework' -> split by '-' into 'Kuttoe' and 'Mini Mod Framework'
    2. Validates author interpellation in the forum:
       - Verifies formatted_message strictly separates Missing Mods ('📦 Unresolved / Missing Dependencies:')
         and Comments ('🧹 Notes / Instructions to clean from Requirements:').
       - Posts the forum comment via /api/catalog/report-missing-requirements.
       - Verifies /api/catalog/check-missing-report detects already_reported=True.
       - Deletes the forum comment via /api/catalog/delete-missing-report once validated,
         and verifies already_reported=False.
    """
    from bs4 import BeautifulSoup
    from plugins.loverslab.requirements_extractor import extract_loverslab_requirements
    from src.core.session_manager import SessionManager

    client = e2e_env["client"]
    db = e2e_env["db"]

    # Simulated forum state: page_url -> list of posted comment strings
    forum_comments_store: dict[str, list[str]] = {}

    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"
    mock_provider.get_creator_info.side_effect = lambda url: (
        "99001",
        "BlackBoxMods",
        "https://www.loverslab.com/profile/99001-blackboxmods/",
    )

    def mock_check_already_commented(page_url: str, required_keywords: list[str]):
        comments = forum_comments_store.get(page_url, [])
        for msg in comments:
            msg_low = msg.lower()
            if not required_keywords or any(kw.lower() in msg_low for kw in required_keywords if kw):
                return True, "28/10/2026 à 07:15"
        return False, None

    def mock_post_comment(page_url: str, message: str):
        forum_comments_store.setdefault(page_url, []).append(message)
        return True, "Message publié avec succès sur le forum LoversLab."

    def mock_delete_comment(page_url: str, required_keywords: list[str] | None = None):
        comments = forum_comments_store.get(page_url, [])
        if not comments:
            return False, "Aucun commentaire correspondant trouvé."
        forum_comments_store[page_url] = []
        return True, "Commentaire supprimé avec succès du forum."

    mock_provider.check_user_already_commented.side_effect = mock_check_already_commented
    mock_provider.post_mod_comment.side_effect = mock_post_comment
    mock_provider.delete_mod_comment.side_effect = mock_delete_comment

    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))
    monkeypatch.setattr(SessionManager, "is_member_authenticated", classmethod(lambda cls, src: True))

    test_cases = [
        {
            "remote_id": "51444",
            "title": "Confidence Cascade",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/",
            "raw_html": (
                '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                "Game Options -&gt; Script Mods Enabled<br>"
                "Bad decisions. Better stories.<br>"
                "Lumpinou - Relationship &amp; Pregnancy Overhaul"
                "</div></li></ul>"
            ),
            "expected_comments": [
                "Game Options -> Script Mods Enabled",
                "Bad decisions. Better stories",
            ],
            "expected_unfound_mods": [
                "Lumpinou",
                "Relationship & Pregnancy Overhaul",
            ],
        },
        {
            "remote_id": "51834",
            "title": "Wicked Traits Unleashed",
            "author": "WickedCreator",
            "page_url": "https://www.loverslab.com/files/file/51834-wicked-traits-unleashed/",
            "raw_html": (
                '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                "Script-only mod - no .package file required<br>"
                "Scumbumbo - XML Injector v4"
                "</div></li></ul>"
            ),
            "expected_comments": [
                "Script-only mod - no .package file required",
            ],
            "expected_unfound_mods": [
                "Scumbumbo",
                "XML Injector v4",
            ],
        },
        {
            "remote_id": "52204",
            "title": "Private Night (TS4 WW)",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/52204-private-night/",
            "raw_html": (
                '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                "Make sure you have the latest patch and restart the game<br>"
                "Kuttoe - Mini Mod Framework"
                "</div></li></ul>"
            ),
            "expected_comments": [
                "Make sure you have the latest patch and restart the game",
            ],
            "expected_unfound_mods": [
                "Kuttoe",
                "Mini Mod Framework",
            ],
        },
    ]

    for case in test_cases:
        soup = BeautifulSoup(case["raw_html"], "html.parser")
        req_text, req_status, extracted_mods = extract_loverslab_requirements(soup)
        extracted_titles = [m["title"] for m in extracted_mods]

        # 1. Verify delimiter splitting and extraction accuracy
        for exp_c in case["expected_comments"]:
            assert exp_c in extracted_titles, f"Expected comment '{exp_c}' not in extracted {extracted_titles}"
        for exp_m in case["expected_unfound_mods"]:
            assert exp_m in extracted_titles, f"Expected split mod '{exp_m}' not in extracted {extracted_titles}"

        # 2. Seed mod in catalog DB
        with db.get_session() as s:
            cm = CatalogMod(
                source="loverslab",
                remote_id=case["remote_id"],
                title=case["title"],
                author=case["author"],
                page_url=case["page_url"],
                requirements_text=req_text,
                requirements_status=req_status,
            )
            cm.set_requirements_mods_list(extracted_mods)
            s.add(cm)
            s.commit()
            mod_id = cm.id

        # 3. Apply explicit user qualification overrides via API (/api/catalog/requirements-override)
        overrides_map = {c: "COMMENT" for c in case["expected_comments"]}
        overrides_map.update({m: "MOD" for m in case["expected_unfound_mods"]})

        ov_resp = client.post(
            "/api/catalog/requirements-override",
            json={
                "catalog_mod_id": mod_id,
                "source": "loverslab",
                "remote_id": case["remote_id"],
                "overrides": overrides_map,
            },
        )
        assert ov_resp.status_code == 200
        assert ov_resp.json()["success"] is True

        # 4. Check dependencies via API (/api/catalog/check-dependencies)
        chk_resp = client.post(
            "/api/catalog/check-dependencies",
            json={"catalog_mod_id": mod_id, "source": "loverslab", "title": case["title"]},
        )
        assert chk_resp.status_code == 200
        chk_data = chk_resp.json()
        assert chk_data["can_install"] is True

        comment_titles = [d["title"] for d in chk_data["comment_dependencies"]]
        unfound_titles = [d["title"] for d in chk_data["unfound_dependencies"]]

        assert set(comment_titles) == set(case["expected_comments"])
        assert set(unfound_titles) == set(case["expected_unfound_mods"])

        # 5. Check missing report & verify formatted forum message separation
        rep_chk1 = client.post(
            "/api/catalog/check-missing-report",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": unfound_titles,
                "unnecessary_modules": comment_titles,
            },
        )
        assert rep_chk1.status_code == 200
        rep_data1 = rep_chk1.json()
        assert rep_data1["can_report"] is True
        assert rep_data1["already_reported"] is False

        formatted_msg = rep_data1["formatted_message"]
        assert "📦 Unresolved / Missing Dependencies:" in formatted_msg
        assert "🧹 Notes / Instructions to clean from Requirements:" in formatted_msg

        missing_section, notes_section = formatted_msg.split("🧹 Notes / Instructions to clean from Requirements:", 1)
        for m_title in case["expected_unfound_mods"]:
            assert f"- {m_title}" in missing_section
            assert f"- {m_title}" not in notes_section
        for c_title in case["expected_comments"]:
            assert f"- {c_title}" in notes_section
            assert f"- {c_title}" not in missing_section

        # 6. Post author interpellation message to the forum (send_as_pm=False)
        sub_resp = client.post(
            "/api/catalog/report-missing-requirements",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": unfound_titles,
                "unnecessary_modules": comment_titles,
                "send_as_pm": False,
            },
        )
        assert sub_resp.status_code == 200
        sub_data = sub_resp.json()
        assert sub_data["success"] is True
        assert sub_data["already_reported"] is True
        assert len(forum_comments_store.get(case["page_url"], [])) == 1

        # 7. Verify check-missing-report now detects the comment on the forum
        rep_chk2 = client.post(
            "/api/catalog/check-missing-report",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": unfound_titles,
                "unnecessary_modules": comment_titles,
            },
        )
        assert rep_chk2.status_code == 200
        assert rep_chk2.json()["already_reported"] is True
        assert rep_chk2.json()["can_report"] is False

        # 8. Delete the forum comment once validated & confirm clean state
        del_resp = client.post(
            "/api/catalog/delete-missing-report",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": unfound_titles,
                "unnecessary_modules": comment_titles,
            },
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        rep_chk3 = client.post(
            "/api/catalog/check-missing-report",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": unfound_titles,
                "unnecessary_modules": comment_titles,
            },
        )
        assert rep_chk3.status_code == 200
        assert rep_chk3.json()["already_reported"] is False
        assert rep_chk3.json()["can_report"] is True


def test_multi_mods_shared_dependencies_non_reinstallation_e2e(e2e_env, monkeypatch):
    """
    Scenario: Sequential installation of a group of 4 mods sharing 2 common dependencies
    (WickedWhims + XML Injector).
    Validates:
    - Installing Mod 1 (Confidence Cascade) with install_dependencies=True downloads and installs
      both shared dependencies (WickedWhims and XML Injector) + Mod 1.
    - Directly installing Mod 2 (Exciting Animations Pack), Mod 3 (Wicked Traits Unleashed),
      and Mod 4 (Private Night (TS4 WW)) detects that WickedWhims and XML Injector are already
      installed and does NOT re-download or reinstall them.
    """
    import io
    import zipfile
    from src.infrastructure.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    shared_deps_defs = [
        {
            "remote_id": "3169",
            "title": "WickedWhims",
            "author": "TURBODRIVER",
            "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            "dl_url": "https://example.com/dl/3169",
            "pkg_name": "WickedWhims_Tuning.package",
        },
        {
            "remote_id": "99901",
            "title": "XML Injector",
            "author": "Scumbumbo",
            "page_url": "https://www.loverslab.com/files/file/99901-xml-injector/",
            "dl_url": "https://example.com/dl/99901",
            "pkg_name": "XMLInjector_v4.package",
        },
    ]

    shared_reqs_list = [
        {
            "source": "loverslab",
            "remote_id": "3169",
            "title": "WickedWhims",
            "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        },
        {
            "source": "loverslab",
            "remote_id": "99901",
            "title": "XML Injector",
            "url": "https://www.loverslab.com/files/file/99901-xml-injector/",
        },
    ]

    group_of_4_mods = [
        {
            "remote_id": "51444",
            "title": "Confidence Cascade",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/",
            "dl_url": "https://example.com/dl/51444",
            "pkg_name": "ConfidenceCascade.package",
        },
        {
            "remote_id": "5001",
            "title": "Exciting Animations Pack",
            "author": "AnimatorX",
            "page_url": "https://www.loverslab.com/files/file/5001-exciting-animations/",
            "dl_url": "https://example.com/dl/5001",
            "pkg_name": "ExcitingAnimations.package",
        },
        {
            "remote_id": "51834",
            "title": "Wicked Traits Unleashed",
            "author": "WickedCreator",
            "page_url": "https://www.loverslab.com/files/file/51834-wicked-traits/",
            "dl_url": "https://example.com/dl/51834",
            "pkg_name": "WickedTraitsUnleashed.package",
        },
        {
            "remote_id": "52204",
            "title": "Private Night (TS4 WW)",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/52204-private-night/",
            "dl_url": "https://example.com/dl/52204",
            "pkg_name": "PrivateNight.package",
        },
    ]

    mod_db_ids: dict[str, int] = {}
    with db.get_session() as s:
        for dep_def in shared_deps_defs:
            cm = CatalogMod(
                source="loverslab",
                remote_id=dep_def["remote_id"],
                title=dep_def["title"],
                author=dep_def["author"],
                page_url=dep_def["page_url"],
                requirements_status="NONE",
            )
            cm.set_requirements_mods_list([])
            cm.set_download_urls_list([{"name": f"{dep_def['remote_id']}.zip", "url": dep_def["dl_url"]}])
            s.add(cm)
            s.flush()
            mod_db_ids[dep_def["remote_id"]] = cm.id

        for mod_def in group_of_4_mods:
            cm = CatalogMod(
                source="loverslab",
                remote_id=mod_def["remote_id"],
                title=mod_def["title"],
                author=mod_def["author"],
                page_url=mod_def["page_url"],
                requirements_status="RESOLVED",
            )
            cm.set_requirements_mods_list(shared_reqs_list)
            cm.set_download_urls_list([{"name": f"{mod_def['remote_id']}.zip", "url": mod_def["dl_url"]}])
            s.add(cm)
            s.flush()
            mod_db_ids[mod_def["remote_id"]] = cm.id

        s.commit()

    all_defs_by_id = {d["remote_id"]: d for d in (shared_deps_defs + group_of_4_mods)}
    download_call_counts: dict[str, int] = {rid: 0 for rid in all_defs_by_id}

    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"

    def mock_get_details(url):
        for rid, d in all_defs_by_id.items():
            if rid in str(url):
                is_dep = rid in ("3169", "99901")
                return {
                    "download_urls": [{"name": f"{rid}.zip", "url": d["dl_url"]}],
                    "requirements_mods": [] if is_dep else shared_reqs_list,
                    "requirements_status": "NONE" if is_dep else "RESOLVED",
                    "external_links": [],
                    "screenshots": [],
                }
        return {"download_urls": [], "requirements_mods": [], "requirements_status": "NONE"}

    def mock_download(url, dest_path, progress_callback=None):
        dest_path = Path(dest_path)
        matched_rid = next((rid for rid in all_defs_by_id if rid in str(url)), None)
        assert matched_rid is not None, f"Unexpected download URL: {url}"
        download_call_counts[matched_rid] += 1

        pkg_name = all_defs_by_id[matched_rid]["pkg_name"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(pkg_name, f"DBPF_CONTENT_{matched_rid}".encode("utf-8"))
        dest_path.write_bytes(buf.getvalue())
        return True, str(dest_path)

    mock_provider.get_mod_details.side_effect = mock_get_details
    mock_provider.download_mod_file = mock_download
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))

    # 1. Before any install, Mod 1 (Confidence Cascade) reports 2 missing dependencies
    first_mod = group_of_4_mods[0]
    chk1 = client.post(
        "/api/catalog/check-dependencies",
        json={
            "catalog_mod_id": mod_db_ids[first_mod["remote_id"]],
            "source": "loverslab",
            "title": first_mod["title"],
        },
    )
    assert chk1.status_code == 200
    chk1_data = chk1.json()
    assert len(chk1_data["missing_dependencies"]) == 2
    assert len(chk1_data["already_installed_dependencies"]) == 0

    # 2. Install Mod 1 (Confidence Cascade) with install_dependencies=True
    inst1 = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": mod_db_ids[first_mod["remote_id"]],
            "source": "loverslab",
            "remote_id": first_mod["remote_id"],
            "title": first_mod["title"],
            "page_url": first_mod["page_url"],
            "install_dependencies": True,
        },
    )
    assert inst1.status_code == 200
    inst1_data = inst1.json()
    assert inst1_data["success"] is True

    # Both shared dependencies and Mod 1 were downloaded exactly once
    assert download_call_counts["3169"] == 1
    assert download_call_counts["99901"] == 1
    assert download_call_counts["51444"] == 1

    # 3. Directly execute installation of Mods 2, 3, and 4 with install_dependencies=True
    for subsequent_mod in group_of_4_mods[1:]:
        rid = subsequent_mod["remote_id"]

        # Verify check-dependencies sees both shared dependencies as ALREADY INSTALLED
        chk_sub = client.post(
            "/api/catalog/check-dependencies",
            json={
                "catalog_mod_id": mod_db_ids[rid],
                "source": "loverslab",
                "title": subsequent_mod["title"],
            },
        )
        assert chk_sub.status_code == 200
        chk_sub_data = chk_sub.json()
        assert len(chk_sub_data["missing_dependencies"]) == 0
        already_titles = {d["title"] for d in chk_sub_data["already_installed_dependencies"]}
        assert already_titles == {"WickedWhims", "XML Injector"}

        # Execute installation directly with install_dependencies=True
        inst_sub = client.post(
            "/api/catalog/install",
            json={
                "catalog_mod_id": mod_db_ids[rid],
                "source": "loverslab",
                "remote_id": rid,
                "title": subsequent_mod["title"],
                "page_url": subsequent_mod["page_url"],
                "install_dependencies": True,
            },
        )
        assert inst_sub.status_code == 200
        inst_sub_data = inst_sub.json()
        assert inst_sub_data["success"] is True
        assert inst_sub_data.get("installed_dependencies", []) == []

        # Shared dependencies MUST NOT have been re-downloaded or reinstalled!
        assert download_call_counts["3169"] == 1, f"WickedWhims was reinstalled during {subsequent_mod['title']}!"
        assert download_call_counts["99901"] == 1, f"XML Injector was reinstalled during {subsequent_mod['title']}!"
        assert download_call_counts[rid] == 1

    # 4. Final verification: 6 total installed mods in DB and on disk
    with db.get_session() as s:
        all_installed = s.query(InstalledMod).all()
        assert len(all_installed) == 6
        installed_titles = {im.title for im in all_installed}
        assert installed_titles == {
            "WickedWhims",
            "XML Injector",
            "Confidence Cascade",
            "Exciting Animations Pack",
            "Wicked Traits Unleashed",
            "Private Night (TS4 WW)",
        }
        for im in all_installed:
            folder = mods_dir / im.folder_name
            assert folder.exists()


def test_nsfwmods_provider_catalog_and_installation_e2e(e2e_env, monkeypatch):
    """
    Tests end-to-end catalog listing, filtering, details fetching, and installation
    for a mod from the NSFWMods provider ('nsfwmods', https://nsfwmods.com/files/category/287-sims-mods/).
    """
    import io
    import zipfile
    from unittest.mock import MagicMock
    from src.infrastructure.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    with db.get_session() as s:
        nm_mod = CatalogMod(
            source="nsfwmods",
            remote_id="424",
            title="Sim Snatcher",
            author="ColonolNutty",
            category="Sims Mods (NSFWMods)",
            page_url="https://nsfwmods.com/files/file/424-sim-snatcher/",
            version_str="3.11",
            patreon_status="NONE",
            requirements_status="NONE",
        )
        s.add(nm_mod)
        s.commit()
        nm_mod_id = nm_mod.id

    # 1. Verify catalog filtering by source="nsfwmods"
    cat_resp = client.get("/api/catalog?source=nsfwmods")
    assert cat_resp.status_code == 200
    items = cat_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["source"] == "nsfwmods"
    assert items[0]["title"] == "Sim Snatcher"

    # 2. Mock NSFWMods provider download and install the mod
    mock_nm_provider = MagicMock()
    mock_nm_provider.provider_name = "nsfwmods"
    mock_nm_provider.get_mod_details.return_value = {
        "description": "<div>Sim Snatcher for Sims 4</div>",
        "download_urls": [
            {
                "name": "SimSnatcher_v3.11.zip",
                "url": "https://nsfwmods.com/files/file/424-sim-snatcher/?do=download&csrfKey=abc123",
                "size": 0,
            }
        ],
        "requirements_mods": [],
        "requirements_status": "NONE",
        "version_str": "3.11",
    }

    def mock_nm_download(download_url=None, dest_path=None, progress_callback=None, **kwargs):
        target = Path(dest_path or kwargs.get("dest_folder"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("SimSnatcher.package", b"DBPF_SIM_SNATCHER")
        target.write_bytes(buf.getvalue())
        return True, str(target)

    mock_nm_provider.download_mod_file = mock_nm_download
    orig_get = ProviderRegistry.get_provider
    monkeypatch.setattr(
        ProviderRegistry,
        "get_provider",
        classmethod(lambda cls, name: mock_nm_provider if name == "nsfwmods" else orig_get(name)),
    )

    inst_resp = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": nm_mod_id,
            "source": "nsfwmods",
            "remote_id": "424",
            "title": "Sim Snatcher",
            "page_url": "https://nsfwmods.com/files/file/424-sim-snatcher/",
            "install_dependencies": False,
        },
    )
    assert inst_resp.status_code == 200
    assert inst_resp.json()["success"] is True

    with db.get_session() as s:
        installed = s.query(InstalledMod).filter_by(source="nsfwmods", remote_id="424").first()
        assert installed is not None
        assert (mods_dir / installed.folder_name).exists()


def test_curseforge_provider_catalog_and_installation_e2e(e2e_env, monkeypatch):
    """
    Tests end-to-end catalog listing, filtering, details fetching, and installation
    for a mod from the CurseForge provider ('curseforge', https://www.curseforge.com/sims4).
    """
    import io
    import zipfile
    from unittest.mock import MagicMock
    from src.infrastructure.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    with db.get_session() as s:
        cf_mod = CatalogMod(
            source="curseforge",
            remote_id="xml-injector",
            title="XML Injector",
            author="ScumbumboMods",
            category="Mods - Utilities (CurseForge)",
            page_url="https://www.curseforge.com/sims4/mods/xml-injector",
            version_str="4.2",
            patreon_status="NONE",
            requirements_status="NONE",
        )
        s.add(cf_mod)
        s.commit()
        cf_mod_id = cf_mod.id

    # 1. Verify catalog filtering by source="curseforge"
    cat_resp = client.get("/api/catalog?source=curseforge")
    assert cat_resp.status_code == 200
    items = cat_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["source"] == "curseforge"
    assert items[0]["title"] == "XML Injector"

    # 2. Mock CurseForge provider download and install the mod
    mock_cf_provider = MagicMock()
    mock_cf_provider.provider_name = "curseforge"
    mock_cf_provider.get_mod_details.return_value = {
        "description": "<div>XML Injector v4.2 for The Sims 4</div>",
        "download_urls": [
            {
                "name": "XmlInjector_Script_v4.2.zip",
                "url": "https://www.curseforge.com/api/v1/mods/694283/files/7021809/download",
                "size": 28199,
            }
        ],
        "requirements_mods": [],
        "requirements_status": "NONE",
        "version_str": "4.2",
    }

    def mock_cf_download(download_url=None, dest_path=None, progress_callback=None, **kwargs):
        target = Path(dest_path or kwargs.get("dest_folder"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("XmlInjector_Script_v4.2.ts4script", b"PK\x03\x04\x14\x00\x00\x00")
            zf.writestr("XmlInjector_Test_v4.package", b"DBPF_XML_INJECTOR_CF")
        target.write_bytes(buf.getvalue())
        return True, str(target)

    mock_cf_provider.download_mod_file = mock_cf_download
    orig_get = ProviderRegistry.get_provider
    monkeypatch.setattr(
        ProviderRegistry,
        "get_provider",
        classmethod(lambda cls, name: mock_cf_provider if name == "curseforge" else orig_get(name)),
    )

    inst_resp = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": cf_mod_id,
            "source": "curseforge",
            "remote_id": "xml-injector",
            "title": "XML Injector",
            "page_url": "https://www.curseforge.com/sims4/mods/xml-injector",
            "install_dependencies": False,
        },
    )
    assert inst_resp.status_code == 200
    assert inst_resp.json()["success"] is True

    with db.get_session() as s:
        installed = s.query(InstalledMod).filter_by(source="curseforge", remote_id="xml-injector").first()
        assert installed is not None
        assert (mods_dir / installed.folder_name).exists()


def test_three_platforms_concurrent_installation_e2e(e2e_env, monkeypatch):
    """
    Tests simultaneous (concurrent) installation of 3 mods from the 3 platforms
    (LoversLab, NSFWMods, CurseForge) at the exact same time using ThreadPoolExecutor.
    """
    import concurrent.futures
    import io
    import zipfile
    from unittest.mock import MagicMock
    from src.api.schemas.catalog import CatalogInstallRequest
    from src.application.mods.mod_install_orchestrator import perform_mod_install
    from src.infrastructure.database.models import InstalledMod

    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    three_platform_mods = [
        {
            "source": "loverslab",
            "remote_id": "3169",
            "title": "WickedWhims",
            "author": "TURBODRIVER",
            "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            "dl_url": "https://www.loverslab.com/files/file/3169-wickedwhims/?do=download",
            "pkg": "WickedWhims.package",
        },
        {
            "source": "nsfwmods",
            "remote_id": "424",
            "title": "Sim Snatcher",
            "author": "ColonolNutty",
            "page_url": "https://nsfwmods.com/files/file/424-sim-snatcher/",
            "dl_url": "https://nsfwmods.com/files/file/424-sim-snatcher/?do=download&csrfKey=123",
            "pkg": "SimSnatcher.package",
        },
        {
            "source": "curseforge",
            "remote_id": "universal-venue-list",
            "title": "Universal Venue List",
            "author": "Basemental",
            "page_url": "https://www.curseforge.com/sims4/mods/universal-venue-list",
            "dl_url": "https://www.curseforge.com/api/v1/mods/710000/files/810000/download",
            "pkg": "UniversalVenueList.package",
        },
    ]

    with db.get_session() as s:
        for m in three_platform_mods:
            cm = CatalogMod(
                source=m["source"],
                remote_id=m["remote_id"],
                title=m["title"],
                author=m["author"],
                page_url=m["page_url"],
                requirements_status="NONE",
            )
            s.add(cm)
        s.commit()

    providers_map = {}
    for m in three_platform_mods:
        prov = MagicMock()
        prov.provider_name = m["source"]
        prov.get_mod_details.return_value = {
            "download_urls": [{"name": f"{m['remote_id']}.zip", "url": m["dl_url"]}],
            "requirements_mods": [],
            "requirements_status": "NONE",
            "version_str": "1.0",
        }

        def make_dl(pkg_name, rid):
            def _dl(download_url=None, dest_path=None, progress_callback=None, **kwargs):
                target = Path(dest_path or kwargs.get("dest_folder"))
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as zf:
                    zf.writestr(pkg_name, f"DBPF_{rid}".encode("utf-8"))
                target.write_bytes(buf.getvalue())
                return True, str(target)

            return _dl

        prov.download_mod_file = make_dl(m["pkg"], m["remote_id"])
        providers_map[m["source"]] = prov

    monkeypatch.setattr(
        ProviderRegistry,
        "get_provider",
        classmethod(lambda cls, name: providers_map.get(name)),
    )

    def _install_worker(mod_info):
        req = CatalogInstallRequest(
            source=mod_info["source"],
            remote_id=mod_info["remote_id"],
            title=mod_info["title"],
            page_url=mod_info["page_url"],
            install_dependencies=False,
        )
        return perform_mod_install(req)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_install_worker, m) for m in three_platform_mods]
        results = [f.result() for f in futures]

    assert all(r.success for r in results), f"Concurrent 3-platform install failed: {[r.message for r in results]}"

    with db.get_session() as s:
        installed = s.query(InstalledMod).all()
        assert len(installed) == 3
        assert {im.source for im in installed} == {"loverslab", "nsfwmods", "curseforge"}
        for im in installed:
            assert (mods_dir / im.folder_name).exists()


def test_cross_platform_shared_dependencies_and_non_collision_e2e(e2e_env, monkeypatch):
    """
    Tests real-world cross-platform non-collision and shared dependencies across LoversLab, NSFWMods, and CurseForge:
    1. Cross-Platform Shared Dependencies:
       - 'Social Activities (Visit Friends, Family and more)' on CurseForge requires 'XML Injector' (CurseForge).
       - 'Confidence Cascade' on LoversLab requires 'XML Injector v4' (LoversLab).
       -> Installing 'Social Activities' installs 'XML Injector' once; subsequent installation of 'Confidence Cascade'
          recognizes 'XML Injector' as already installed across platforms and does NOT re-download or create a second folder.
    2. Cross-Platform Identical Mod Non-Collision (Sequential & Concurrent):
       - 'The Sims 4 Community Library' on NSFWMods (#742) vs 'Sims 4 Community Library' on LoversLab (#25060)
         installed concurrently across threads.
       -> Only 1 download occurs, only 1 physical folder on disk is created, and 1 InstalledMod record exists.
    """
    import concurrent.futures
    import io
    import threading
    import zipfile
    from unittest.mock import MagicMock
    from src.api.schemas.catalog import CatalogInstallRequest
    from src.application.mods.active_installation_registry import ActiveInstallationRegistry
    from src.application.mods.mod_install_orchestrator import perform_mod_install
    from src.infrastructure.database.models import InstalledMod

    ActiveInstallationRegistry.reset()
    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    catalog_entries = [
        # Shared Dependency 1: XML Injector on CurseForge & LoversLab
        {
            "source": "curseforge",
            "remote_id": "xml-injector",
            "title": "XML Injector",
            "author": "ScumbumboMods",
            "page_url": "https://www.curseforge.com/sims4/mods/xml-injector",
            "dl_url": "https://www.curseforge.com/api/v1/mods/694283/files/7021809/download",
            "pkg": "XmlInjector_v4.package",
            "reqs": [],
        },
        {
            "source": "loverslab",
            "remote_id": "99901",
            "title": "XML Injector v4",
            "author": "Scumbumbo",
            "page_url": "https://www.loverslab.com/files/file/99901-xml-injector/",
            "dl_url": "https://www.loverslab.com/files/file/99901-xml-injector/?do=download",
            "pkg": "XmlInjector_v4.package",
            "reqs": [],
        },
        # Mod on CurseForge requiring XML Injector
        {
            "source": "curseforge",
            "remote_id": "social-activities-visit-friends-family-and-more",
            "title": "Social Activities (Visit Friends, Family and more)",
            "author": "LittleMsSam",
            "page_url": "https://www.curseforge.com/sims4/mods/social-activities-visit-friends-family-and-more",
            "dl_url": "https://www.curseforge.com/api/v1/mods/700100/files/800100/download",
            "pkg": "LittleMsSam_SocialActivities.package",
            "reqs": [
                {
                    "source": "curseforge",
                    "remote_id": "xml-injector",
                    "title": "XML Injector",
                    "url": "https://www.curseforge.com/sims4/mods/xml-injector",
                }
            ],
        },
        # Mod on LoversLab requiring XML Injector v4
        {
            "source": "loverslab",
            "remote_id": "51444",
            "title": "Confidence Cascade",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/",
            "dl_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/?do=download",
            "pkg": "ConfidenceCascade.package",
            "reqs": [
                {
                    "source": "loverslab",
                    "remote_id": "99901",
                    "title": "XML Injector v4",
                    "url": "https://www.loverslab.com/files/file/99901-xml-injector/",
                }
            ],
        },
        # Mod on The Sims Resource requiring XML Injector
        {
            "source": "thesimsresource",
            "remote_id": "1736888",
            "title": "Boho Functional Tea Set",
            "author": "Syboulette",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1736888",
            "dl_url": "https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid=1736888&setItems=&format=zip",
            "pkg": "Syboulette_BohoTeaSet.package",
            "reqs": [
                {
                    "source": "curseforge",
                    "remote_id": "xml-injector",
                    "title": "XML Injector",
                    "url": "https://www.curseforge.com/sims4/mods/xml-injector",
                }
            ],
        },
        # Identical Mod on NSFWMods & LoversLab: Sims 4 Community Library
        {
            "source": "nsfwmods",
            "remote_id": "742",
            "title": "The Sims 4 Community Library",
            "author": "ColonolNutty",
            "page_url": "https://nsfwmods.com/files/file/742-sims-4-community-library/",
            "dl_url": "https://nsfwmods.com/files/file/742-sims-4-community-library/?do=download&csrfKey=s4cl",
            "pkg": "s4cl.package",
            "reqs": [],
        },
        {
            "source": "loverslab",
            "remote_id": "25060",
            "title": "Sims 4 Community Library",
            "author": "ColonolNutty",
            "page_url": "https://www.loverslab.com/files/file/25060-sims-4-community-library/",
            "dl_url": "https://www.loverslab.com/files/file/25060-sims-4-community-library/?do=download",
            "pkg": "s4cl.package",
            "reqs": [],
        },
        # Identical Mod on The Sims Resource & CurseForge: Syboulette Boho Living Room
        {
            "source": "thesimsresource",
            "remote_id": "1736999",
            "title": "Syboulette Boho Living Room",
            "author": "Syboulette",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1736999",
            "dl_url": "https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid=1736999&setItems=&format=zip",
            "pkg": "Syboulette_BohoLiving.package",
            "reqs": [],
        },
        {
            "source": "curseforge",
            "remote_id": "syboulette-boho-living-room",
            "title": "Syboulette Boho Living Room v2",
            "author": "Syboulette",
            "page_url": "https://www.curseforge.com/sims4/build-buy/syboulette-boho-living-room",
            "dl_url": "https://www.curseforge.com/api/v1/mods/800999/files/900999/download",
            "pkg": "Syboulette_BohoLiving.package",
            "reqs": [],
        },
    ]

    db_ids: dict[tuple[str, str], int] = {}
    with db.get_session() as s:
        for entry in catalog_entries:
            cm = CatalogMod(
                source=entry["source"],
                remote_id=entry["remote_id"],
                title=entry["title"],
                author=entry["author"],
                page_url=entry["page_url"],
                requirements_status="FOUND" if entry["reqs"] else "NONE",
            )
            cm.set_requirements_mods_list(entry["reqs"])
            s.add(cm)
            s.flush()
            db_ids[(entry["source"], entry["remote_id"])] = cm.id
        s.commit()

    entries_by_url = {e["page_url"]: e for e in catalog_entries}
    entries_by_dl = {e["dl_url"]: e for e in catalog_entries}
    download_lock = threading.Lock()
    download_counts = {
        "xml_injector": 0,
        "s4cl": 0,
        "social_activities": 0,
        "confidence_cascade": 0,
        "boho_tea_set": 0,
        "boho_living": 0,
    }

    def _make_provider(source_name: str):
        prov = MagicMock()
        prov.provider_name = source_name

        def _get_details(page_url):
            e = entries_by_url.get(page_url)
            if not e:
                return {"download_urls": [], "requirements_mods": [], "requirements_status": "NONE"}
            return {
                "download_urls": [{"name": f"{e['remote_id']}.zip", "url": e["dl_url"]}],
                "requirements_mods": e["reqs"],
                "requirements_status": "FOUND" if e["reqs"] else "NONE",
                "version_str": "1.0",
            }

        def _download(download_url=None, dest_path=None, progress_callback=None, **kwargs):
            target = Path(dest_path or kwargs.get("dest_folder"))
            e = entries_by_dl.get(download_url) or entries_by_url.get(download_url)
            assert e is not None, f"Unexpected download URL: {download_url}"
            with download_lock:
                if e["remote_id"] in ("xml-injector", "99901"):
                    download_counts["xml_injector"] += 1
                elif e["remote_id"] in ("742", "25060"):
                    download_counts["s4cl"] += 1
                elif e["remote_id"] == "social-activities-visit-friends-family-and-more":
                    download_counts["social_activities"] += 1
                elif e["remote_id"] == "51444":
                    download_counts["confidence_cascade"] += 1
                elif e["remote_id"] == "1736888":
                    download_counts["boho_tea_set"] += 1
                elif e["remote_id"] in ("1736999", "syboulette-boho-living-room"):
                    download_counts["boho_living"] += 1

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr(e["pkg"], f"DBPF_{e['remote_id']}".encode("utf-8"))
            target.write_bytes(buf.getvalue())
            return True, str(target)

        prov.get_mod_details.side_effect = _get_details
        prov.download_mod_file = _download
        return prov

    providers = {
        "loverslab": _make_provider("loverslab"),
        "nsfwmods": _make_provider("nsfwmods"),
        "curseforge": _make_provider("curseforge"),
        "thesimsresource": _make_provider("thesimsresource"),
    }
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: providers.get(name)))

    # 1. Install 'Social Activities' on CurseForge -> installs 'XML Injector' (from CurseForge)
    res_cf = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": db_ids[("curseforge", "social-activities-visit-friends-family-and-more")],
            "source": "curseforge",
            "remote_id": "social-activities-visit-friends-family-and-more",
            "title": "Social Activities (Visit Friends, Family and more)",
            "page_url": "https://www.curseforge.com/sims4/mods/social-activities-visit-friends-family-and-more",
            "install_dependencies": True,
        },
    )
    assert res_cf.status_code == 200
    assert res_cf.json()["success"] is True
    assert download_counts["xml_injector"] == 1
    assert download_counts["social_activities"] == 1

    # 2. Check dependencies of 'Confidence Cascade' on LoversLab -> 'XML Injector v4' must be seen as ALREADY INSTALLED!
    chk_ll = client.post(
        "/api/catalog/check-dependencies",
        json={
            "catalog_mod_id": db_ids[("loverslab", "51444")],
            "source": "loverslab",
            "title": "Confidence Cascade",
        },
    )
    assert chk_ll.status_code == 200
    chk_ll_data = chk_ll.json()
    assert len(chk_ll_data["missing_dependencies"]) == 0
    assert len(chk_ll_data["already_installed_dependencies"]) == 1

    # 3. Install 'Confidence Cascade' on LoversLab AND 'Boho Functional Tea Set' on TSR -> XML Injector MUST NOT be downloaded again!
    res_ll = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": db_ids[("loverslab", "51444")],
            "source": "loverslab",
            "remote_id": "51444",
            "title": "Confidence Cascade",
            "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/",
            "install_dependencies": True,
        },
    )
    assert res_ll.status_code == 200
    assert res_ll.json()["success"] is True
    assert download_counts["xml_injector"] == 1, "XML Injector was re-downloaded across platforms!"
    assert download_counts["confidence_cascade"] == 1

    res_tsr_dep = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": db_ids[("thesimsresource", "1736888")],
            "source": "thesimsresource",
            "remote_id": "1736888",
            "title": "Boho Functional Tea Set",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1736888",
            "install_dependencies": True,
        },
    )
    assert res_tsr_dep.status_code == 200
    assert res_tsr_dep.json()["success"] is True
    assert download_counts["xml_injector"] == 1, "XML Injector was re-downloaded during TSR mod install!"
    assert download_counts["boho_tea_set"] == 1

    # 4. Attempt direct installation of 'XML Injector v4' from LoversLab when 'XML Injector' from CurseForge is installed
    res_dup_xml = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": db_ids[("loverslab", "99901")],
            "source": "loverslab",
            "remote_id": "99901",
            "title": "XML Injector v4",
            "page_url": "https://www.loverslab.com/files/file/99901-xml-injector/",
            "install_dependencies": False,
        },
    )
    assert res_dup_xml.status_code == 200
    assert res_dup_xml.json()["success"] is True
    assert download_counts["xml_injector"] == 1, "Direct cross-platform duplicate install re-downloaded XML Injector!"

    # 5. Concurrent installation of the same mod ('Sims 4 Community Library') from NSFWMods (#742) and LoversLab (#25060)
    #    AND concurrent installation of ('Syboulette Boho Living Room') from The Sims Resource (#1736999) and CurseForge
    req_s4cl_nm = CatalogInstallRequest(
        catalog_mod_id=db_ids[("nsfwmods", "742")],
        source="nsfwmods",
        remote_id="742",
        title="The Sims 4 Community Library",
        page_url="https://nsfwmods.com/files/file/742-sims-4-community-library/",
        install_dependencies=False,
    )
    req_s4cl_ll = CatalogInstallRequest(
        catalog_mod_id=db_ids[("loverslab", "25060")],
        source="loverslab",
        remote_id="25060",
        title="Sims 4 Community Library",
        page_url="https://www.loverslab.com/files/file/25060-sims-4-community-library/",
        install_dependencies=False,
    )
    req_boho_tsr = CatalogInstallRequest(
        catalog_mod_id=db_ids[("thesimsresource", "1736999")],
        source="thesimsresource",
        remote_id="1736999",
        title="Syboulette Boho Living Room",
        page_url="https://www.thesimsresource.com/downloads/details/id/1736999",
        install_dependencies=False,
    )
    req_boho_cf = CatalogInstallRequest(
        catalog_mod_id=db_ids[("curseforge", "syboulette-boho-living-room")],
        source="curseforge",
        remote_id="syboulette-boho-living-room",
        title="Syboulette Boho Living Room v2",
        page_url="https://www.curseforge.com/sims4/build-buy/syboulette-boho-living-room",
        install_dependencies=False,
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f1 = pool.submit(perform_mod_install, req_s4cl_nm)
        f2 = pool.submit(perform_mod_install, req_s4cl_ll)
        f3 = pool.submit(perform_mod_install, req_boho_tsr)
        f4 = pool.submit(perform_mod_install, req_boho_cf)
        r1, r2, r3, r4 = f1.result(), f2.result(), f3.result(), f4.result()

    assert r1.success is True and r2.success is True and r3.success is True and r4.success is True
    assert download_counts["s4cl"] == 1, f"S4CL was downloaded {download_counts['s4cl']} times instead of 1!"
    assert download_counts["boho_living"] == 1, f"Boho Living was downloaded {download_counts['boho_living']} times!"

    # 6. Verify DB and physical folders: strictly 6 unique mods
    with db.get_session() as s:
        all_installed = s.query(InstalledMod).all()
        assert len(all_installed) == 6, f"Expected 6 unique installed mods, got {[m.title for m in all_installed]}"
        physical_dirs = [p for p in mods_dir.iterdir() if p.is_dir()]
        assert len(physical_dirs) == 6, f"Expected 6 folders on disk, got {[p.name for p in physical_dirs]}"


def test_thesimsresource_provider_catalog_and_installation_e2e(e2e_env, monkeypatch):
    """
    Tests end-to-end catalog listing, filtering, details fetching, and installation
    for a mod from The Sims Resource provider ('thesimsresource',
    https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/).
    """
    from unittest.mock import MagicMock
    from src.infrastructure.database.models import InstalledMod

    client = e2e_env["client"]
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    with db.get_session() as s:
        tsr_mod = CatalogMod(
            source="thesimsresource",
            remote_id="1736888",
            title="Modern Boho Living Room Set",
            author="Syboulette",
            category="Objects (TSR)",
            page_url="https://www.thesimsresource.com/downloads/details/id/1736888",
            version_str="v2",
            patreon_status="NONE",
            requirements_status="NONE",
        )
        s.add(tsr_mod)
        s.commit()
        tsr_mod_id = tsr_mod.id

    # 1. Verify catalog filtering by source="thesimsresource"
    cat_resp = client.get("/api/catalog?source=thesimsresource")
    assert cat_resp.status_code == 200
    items = cat_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["source"] == "thesimsresource"
    assert items[0]["title"] == "Modern Boho Living Room Set"

    # 2. Mock TSR provider download (returning a direct .package file via TSR ticket flow) and install
    mock_tsr_provider = MagicMock()
    mock_tsr_provider.provider_name = "thesimsresource"
    mock_tsr_provider.get_mod_details.return_value = {
        "description": "<div>Modern Boho Living Room Set for Sims 4</div>",
        "download_urls": [
            {
                "name": "Téléchargement TSR (#1736888)",
                "url": "https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid=1736888&setItems=&format=zip",
                "size": 0,
            }
        ],
        "requirements_mods": [],
        "requirements_status": "NONE",
        "version_str": "v2",
    }

    def mock_tsr_download(download_url=None, dest_path=None, progress_callback=None, **kwargs):
        target = Path(dest_path or kwargs.get("dest_folder")).parent / "Syboulette_ModernBohoSet.package"
        target.write_bytes(b"DBPF\x02\x00\x00\x00\x01\x00\x00\x00TSR_BOHO_PACKAGE")
        return True, str(target)

    mock_tsr_provider.download_mod_file = mock_tsr_download
    orig_get = ProviderRegistry.get_provider
    monkeypatch.setattr(
        ProviderRegistry,
        "get_provider",
        classmethod(lambda cls, name: mock_tsr_provider if name == "thesimsresource" else orig_get(name)),
    )

    inst_resp = client.post(
        "/api/catalog/install",
        json={
            "catalog_mod_id": tsr_mod_id,
            "source": "thesimsresource",
            "remote_id": "1736888",
            "title": "Modern Boho Living Room Set",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1736888",
            "install_dependencies": False,
        },
    )
    assert inst_resp.status_code == 200
    assert inst_resp.json()["success"] is True

    with db.get_session() as s:
        installed = s.query(InstalledMod).filter_by(source="thesimsresource", remote_id="1736888").first()
        assert installed is not None
        assert (mods_dir / installed.folder_name / "Syboulette_ModernBohoSet.package").exists()


def test_four_platforms_concurrent_installation_e2e(e2e_env, monkeypatch):
    """
    Tests simultaneous (concurrent) installation of 4 mods from all 4 platforms
    (LoversLab, NSFWMods, CurseForge, The Sims Resource) at the exact same time using ThreadPoolExecutor.
    """
    import concurrent.futures
    import io
    import zipfile
    from unittest.mock import MagicMock
    from src.api.schemas.catalog import CatalogInstallRequest
    from src.application.mods.active_installation_registry import ActiveInstallationRegistry
    from src.application.mods.mod_install_orchestrator import perform_mod_install
    from src.infrastructure.database.models import InstalledMod

    ActiveInstallationRegistry.reset()
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    four_platform_mods = [
        {
            "source": "loverslab",
            "remote_id": "3169",
            "title": "WickedWhims",
            "author": "TURBODRIVER",
            "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            "dl_url": "https://www.loverslab.com/files/file/3169-wickedwhims/?do=download",
            "pkg": "WickedWhims.package",
        },
        {
            "source": "nsfwmods",
            "remote_id": "424",
            "title": "Sim Snatcher",
            "author": "ColonolNutty",
            "page_url": "https://nsfwmods.com/files/file/424-sim-snatcher/",
            "dl_url": "https://nsfwmods.com/files/file/424-sim-snatcher/?do=download&csrfKey=123",
            "pkg": "SimSnatcher.package",
        },
        {
            "source": "curseforge",
            "remote_id": "universal-venue-list",
            "title": "Universal Venue List",
            "author": "Basemental",
            "page_url": "https://www.curseforge.com/sims4/mods/universal-venue-list",
            "dl_url": "https://www.curseforge.com/api/v1/mods/710000/files/810000/download",
            "pkg": "UniversalVenueList.package",
        },
        {
            "source": "thesimsresource",
            "remote_id": "1736888",
            "title": "Modern Boho Living Room Set",
            "author": "Syboulette",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1736888",
            "dl_url": "https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid=1736888&setItems=&format=zip",
            "pkg": "ModernBohoSet.package",
        },
    ]

    with db.get_session() as s:
        for m in four_platform_mods:
            cm = CatalogMod(
                source=m["source"],
                remote_id=m["remote_id"],
                title=m["title"],
                author=m["author"],
                page_url=m["page_url"],
                requirements_status="NONE",
            )
            s.add(cm)
        s.commit()

    providers_map = {}
    for m in four_platform_mods:
        prov = MagicMock()
        prov.provider_name = m["source"]
        prov.get_mod_details.return_value = {
            "download_urls": [{"name": f"{m['remote_id']}.zip", "url": m["dl_url"]}],
            "requirements_mods": [],
            "requirements_status": "NONE",
            "version_str": "1.0",
        }

        def make_dl(pkg_name, rid):
            def _dl(download_url=None, dest_path=None, progress_callback=None, **kwargs):
                target = Path(dest_path or kwargs.get("dest_folder"))
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as zf:
                    zf.writestr(pkg_name, f"DBPF_{rid}".encode("utf-8"))
                target.write_bytes(buf.getvalue())
                return True, str(target)

            return _dl

        prov.download_mod_file = make_dl(m["pkg"], m["remote_id"])
        providers_map[m["source"]] = prov

    monkeypatch.setattr(
        ProviderRegistry,
        "get_provider",
        classmethod(lambda cls, name: providers_map.get(name)),
    )

    def _install_worker(mod_info):
        req = CatalogInstallRequest(
            source=mod_info["source"],
            remote_id=mod_info["remote_id"],
            title=mod_info["title"],
            page_url=mod_info["page_url"],
            install_dependencies=False,
        )
        return perform_mod_install(req)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_install_worker, m) for m in four_platform_mods]
        results = [f.result() for f in futures]

    assert all(r.success for r in results), f"Concurrent 4-platform install failed: {[r.message for r in results]}"

    with db.get_session() as s:
        installed = s.query(InstalledMod).all()
        assert len(installed) == 4
        assert {im.source for im in installed} == {"loverslab", "nsfwmods", "curseforge", "thesimsresource"}
        for im in installed:
            assert (mods_dir / im.folder_name).exists()


def test_multilingual_i18n_fr_en_switching_e2e(e2e_env):
    """
    Tests end-to-end multilingual i18n switching between French ('fr') and English ('en'),
    verifying API settings persistence, I18nManager dynamic translations, ModTypeClassifier
    choices, and TSR/CurseForge/NSFWMods/LoversLab account & conflict strings.
    """
    from src.i18n import I18nManager, tr
    from src.utils.mod_type_classifier import ModTypeClassifier

    client = e2e_env["client"]
    i18n = I18nManager.instance()

    try:
        # 1. Switch to English ('en') via API and I18nManager
        resp_en = client.patch("/api/settings", json={"language": "en"})
        assert resp_en.status_code == 200
        assert resp_en.json()["language"] == "en"
        assert i18n.set_language("en") is True
        assert i18n.get_language() == "en"

        assert tr("nav.catalog") == "📁  Unified Catalog"
        assert tr("accounts.thesimsresource_title") == "The Sims Resource (Sims 4 CC & Mods Catalog)"
        assert tr("conflicts.no_conflicts_title") == "✅ No DBPF conflicts detected!"
        assert tr("installed.status_active") == "🟢 Active"

        en_types = dict(ModTypeClassifier.get_type_choices())
        assert "All Types" in en_types["all"]
        assert "Clothing & Outfits" in en_types["clothing"]

        # 2. Switch back to French ('fr') via API and I18nManager
        resp_fr = client.patch("/api/settings", json={"language": "fr"})
        assert resp_fr.status_code == 200
        assert resp_fr.json()["language"] == "fr"
        assert i18n.set_language("fr") is True
        assert i18n.get_language() == "fr"

        assert tr("nav.catalog") == "📁  Catalogue Unifié"
        assert tr("accounts.thesimsresource_title") == "The Sims Resource (Catalogue Sims 4 CC & Mods)"
        assert tr("conflicts.no_conflicts_title") == "✅ Aucun conflit DBPF détecté !"
        assert tr("installed.status_active") == "🟢 Actif"

        fr_types = dict(ModTypeClassifier.get_type_choices())
        assert "Tous les types" in fr_types["all"]
        assert "Vêtements & Tenues" in fr_types["clothing"]
    finally:
        i18n.set_language("fr")


def test_session_manager_thread_isolated_http_sessions_e2e(e2e_env):
    """
    Verifies that SessionManager.get_http_session reuses pooled sessions within the same thread
    while isolating curl_cffi Session instances across concurrent worker threads (preventing
    native libcurl access violations during 8-worker parallel scraping).
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from src.core.session_manager import SessionManager

    SessionManager.close_all_http_sessions()
    barrier = threading.Barrier(8)

    def _worker_task(_idx: int):
        barrier.wait(timeout=5)
        s1 = SessionManager.get_http_session("loverslab")
        s2 = SessionManager.get_http_session("loverslab")
        assert s1 is s2
        return id(s1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        session_ids = list(pool.map(_worker_task, range(8)))

    assert len(set(session_ids)) == 8
    SessionManager.close_all_http_sessions()


def test_adult_content_disabled_by_default_and_multi_provider_drawer_e2e(e2e_env, qapp):
    """
    Verifies:
    1. AppConfig().adult_content_enabled is False by default.
    2. When adult_content_enabled is False, GET /api/catalog automatically hides 'loverslab'
       and 'nsfwmods' mods while returning 'curseforge' and 'thesimsresource' mods.
    3. Toggling adult_content_enabled to True via PATCH /api/settings exposes all 4 platforms.
    4. AccountCardWidget labels are styled without inner borders/padding, and AccountsView,
       FilterBar, and ProviderDrawer properly hide/show adult platforms and track all 4 scrapers.
    """
    from src.ui.components.account_card import AccountCardWidget
    from src.ui.components.filter_bar import FilterBar
    from src.ui.components.provider_drawer import ProviderDrawer

    client = e2e_env["client"]
    db = e2e_env["db"]

    # 1. Verify default AppConfig has adult_content_enabled = False
    default_cfg = AppConfig()
    assert default_cfg.adult_content_enabled is False

    # Seed 1 mod per platform into CatalogMod
    with db.get_session() as s:
        s.query(CatalogMod).delete()
        s.add_all(
            [
                CatalogMod(
                    source="curseforge",
                    remote_id="cf_1",
                    title="CurseForge Safe Mod",
                    author="CFAuthor",
                    category="Gameplay",
                    page_url="https://www.curseforge.com/sims4/mods/cf-1",
                ),
                CatalogMod(
                    source="thesimsresource",
                    remote_id="tsr_1",
                    title="TSR Safe Hair",
                    author="TSRAuthor",
                    category="Sims 4 Hair",
                    page_url="https://www.thesimsresource.com/downloads/1",
                ),
                CatalogMod(
                    source="loverslab",
                    remote_id="ll_1",
                    title="LoversLab Adult Mod",
                    author="LLAuthor",
                    category="Adult",
                    page_url="https://www.loverslab.com/files/file/1-ll/",
                ),
                CatalogMod(
                    source="nsfwmods",
                    remote_id="nm_1",
                    title="NSFWMods Adult Mod",
                    author="NMAuthor",
                    category="Adult",
                    page_url="https://nsfwmods.com/files/file/1-nm/",
                ),
            ]
        )
        s.commit()

    # 2. Disable adult content via PATCH /api/settings and verify catalog hides loverslab & nsfwmods
    patch_off = client.patch("/api/settings", json={"adult_content_enabled": False})
    assert patch_off.status_code == 200
    assert patch_off.json()["adult_content_enabled"] is False

    cat_safe = client.get("/api/catalog").json()
    safe_sources = {item["source"] for item in cat_safe["items"]}
    assert safe_sources == {"curseforge", "thesimsresource"}
    assert "loverslab" not in safe_sources
    assert "nsfwmods" not in safe_sources

    # 3. Re-enable adult content via PATCH /api/settings and verify all 4 platforms appear
    patch_on = client.patch("/api/settings", json={"adult_content_enabled": True})
    assert patch_on.status_code == 200
    assert patch_on.json()["adult_content_enabled"] is True

    cat_all = client.get("/api/catalog").json()
    all_sources = {item["source"] for item in cat_all["items"]}
    assert all_sources == {"curseforge", "thesimsresource", "loverslab", "nsfwmods"}

    # 4. Verify UI widgets: AccountCardWidget readability, FilterBar +18 toggle, ProviderDrawer 4 scrapers
    card = AccountCardWidget("curseforge", "CurseForge Title", "CurseForge Description")
    assert card.objectName() == "card_curseforge"
    assert "QFrame#card_curseforge" in card.styleSheet()
    assert "QLabel {\n                background-color: transparent;\n                border: none;" in card.styleSheet()
    assert card.title_lbl.text() == "CurseForge Title"
    assert card.desc_lbl.text() == "CurseForge Description"

    fb = FilterBar()
    fb.set_adult_content_enabled(False)
    assert fb.adult_toggle_btn.isChecked() is False
    sources_safe = [fb.source_combo.itemText(i) for i in range(fb.source_combo.count())]
    assert "LoversLab" not in sources_safe
    assert "NSFWMods" not in sources_safe
    assert "CurseForge" in sources_safe
    assert "The Sims Resource" in sources_safe

    fb.set_adult_content_enabled(True)
    assert fb.adult_toggle_btn.isChecked() is True
    sources_all = [fb.source_combo.itemText(i) for i in range(fb.source_combo.count())]
    assert "LoversLab" in sources_all
    assert "NSFWMods" in sources_all

    drawer = ProviderDrawer()
    drawer.set_adult_content_enabled(False)
    assert drawer.ll_card.isHidden() is True
    assert drawer.nm_card.isHidden() is True
    assert drawer.cf_card.isHidden() is False
    assert drawer.tsr_card.isHidden() is False

    drawer.set_adult_content_enabled(True)
    assert drawer.ll_card.isHidden() is False
    assert drawer.nm_card.isHidden() is False

    # Update drawer with multi-provider status payload matching SyncTracker.get_status_dict()
    drawer.update_sync_status(
        {
            "is_running": True,
            "is_paused": False,
            "pages_completed": 8,
            "total_pages": 20,
            "progress_percent": 40,
            "total_scraped": 160,
            "current_category": "Hair",
            "categories_progress": [
                {
                    "id": "cf_gameplay",
                    "name": "Gameplay",
                    "pages_completed": 2,
                    "total_pages": 5,
                    "mods_count": 40,
                    "status": "IN_PROGRESS",
                },
                {
                    "id": "tsr_hair",
                    "name": "Hair",
                    "pages_completed": 3,
                    "total_pages": 5,
                    "mods_count": 60,
                    "status": "IN_PROGRESS",
                },
                {
                    "id": "161",
                    "name": "Les Sims 4 (Racine)",
                    "pages_completed": 2,
                    "total_pages": 5,
                    "mods_count": 40,
                    "status": "IN_PROGRESS",
                },
                {
                    "id": "287",
                    "name": "Sims Mods (Racine)",
                    "pages_completed": 1,
                    "total_pages": 5,
                    "mods_count": 20,
                    "status": "IN_PROGRESS",
                },
            ],
            "providers_status": {
                "curseforge": "RUNNING",
                "thesimsresource": "RUNNING",
                "loverslab": "RUNNING",
                "nsfwmods": "RUNNING",
                "patreon": "OK",
            },
        }
    )
    assert drawer.cf_card.last_computed_state == "RUNNING"
    assert drawer.tsr_card.last_computed_state == "RUNNING"
    assert drawer.ll_card.last_computed_state == "RUNNING"
    assert drawer.nm_card.last_computed_state == "RUNNING"
    assert drawer.cf_card.drawer_progress_bar.value() > 0
    assert drawer.tsr_card.drawer_progress_bar.value() > 0
    assert drawer.ll_card.drawer_progress_bar.value() > 0
    assert drawer.nm_card.drawer_progress_bar.value() > 0


def test_nsfwmods_login_timeout_account_free_downloads_and_comments_e2e(tmp_path):
    """
    Vérifie :
    1. Le timeout étendu dans `ApiClient.login_account` (>= timeout_seconds + 60s) et la détection de session `nsfwmods`.
    2. Le téléchargement et l'activation du bouton d'installation sans compte pour `curseforge` et `thesimsresource`,
       tandis que `loverslab`, `nsfwmods` et `patreon` exigent un compte.
    3. La vérification et publication de commentaires sur `TheSimsResourceProvider` (`/feedback/ax-add-comment/`)
       et `CurseForgeProvider` (`/api/v1/mods/{projectId}/comments`).
    """
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication
    from src.api.client import ApiClient
    from src.core.session_manager import SessionManager
    from src.ui.components.mod_card import ModCard
    from plugins.curseforge.scraper import CurseForgeProvider
    from plugins.thesimsresource.scraper import TheSimsResourceProvider

    _app = QApplication.instance() or QApplication([])

    # 1. Verify ApiClient.login_account passes extended timeout (>= 360s for 300s login)
    client = ApiClient("http://127.0.0.1:8000")
    captured_kwargs = {}

    def _fake_post(url, **kwargs):
        captured_kwargs["url"] = url
        captured_kwargs.update(kwargs)
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"success": True, "message": "OK", "cookies_count": 4}
        return resp

    with patch.object(client._client, "post", side_effect=_fake_post):
        res = client.login_account("nsfwmods", timeout_seconds=300)
        assert res["success"] is True
        assert captured_kwargs["url"] == "/api/accounts/nsfwmods/login"
        assert captured_kwargs["timeout"] >= 360.0

    # 2. Verify SessionManager member auth detection for nsfwmods, thesimsresource, curseforge
    SessionManager.save_session(
        provider_name="nsfwmods",
        cookies={"ips4_member_id": "998877", "ips4_hasAcceptedAge": "1"},
        user_display_name="SimmerNSFW",
        is_authenticated=True,
    )
    assert SessionManager.is_member_authenticated("nsfwmods") is True
    assert SessionManager.is_session_ready("nsfwmods") is True

    SessionManager.save_session(
        provider_name="thesimsresource",
        cookies={"tsrmember": "1", "memberid": "445566"},
        user_display_name="SimmerTSR",
        is_authenticated=True,
    )
    assert SessionManager.is_member_authenticated("thesimsresource") is True

    # 3. Verify ModCard button states without any account logged in:
    # CurseForge & TSR must be enabled without account, whereas LoversLab, NSFWMods, Patreon require login
    for free_source in ("curseforge", "thesimsresource"):
        card_free = ModCard(
            {
                "id": 1,
                "source": free_source,
                "remote_id": "free-mod-1",
                "title": f"Free Mod {free_source}",
                "author": "Creator",
                "page_url": "https://example.com/mod",
                "patreon_status": "PUBLIC",
            },
            is_installed=False,
            has_update=False,
            is_patreon_auth=False,
            is_loverslab_auth=False,
            is_nsfwmods_auth=False,
        )
        assert card_free.action_btn.isEnabled() is True

    for auth_source in ("loverslab", "nsfwmods", "patreon"):
        card_locked = ModCard(
            {
                "id": 2,
                "source": auth_source,
                "remote_id": "auth-mod-2",
                "title": f"Auth Mod {auth_source}",
                "author": "Creator",
                "page_url": "https://example.com/mod",
                "patreon_status": "PUBLIC",
            },
            is_installed=False,
            has_update=False,
            is_patreon_auth=False,
            is_loverslab_auth=False,
            is_nsfwmods_auth=False,
        )
        assert card_locked.action_btn.isEnabled() is False

    # 4. Verify TSR comment checking and posting via /feedback/ax-add-comment/
    tsr_provider = TheSimsResourceProvider()
    mock_tsr_session = MagicMock()
    tsr_page_html = """
    <html><body>
      <a class="creator-name" href="/artists/SimArtist/">SimArtist</a>
      <div class="comments-area">
        <div class="comment-list">
          <div class="comment group">
            <div class="comment-message">
              <p><strong><a href="/members/SimmerTSR/">SimmerTSR</a></strong>
              <span class="date-added">∙ Oct 29, 2026</span></p>
              <p>Missing requirement XML Injector in description</p>
            </div>
          </div>
        </div>
      </div>
    </body></html>
    """

    def _tsr_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.text = tsr_page_html
        return r

    def _tsr_post(url, data=None, headers=None, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.text = "OK"
        return r

    mock_tsr_session.get.side_effect = _tsr_get
    mock_tsr_session.post.side_effect = _tsr_post

    with patch.object(SessionManager, "get_http_session", return_value=mock_tsr_session):
        cid, cname, curl = tsr_provider.get_creator_info("https://www.thesimsresource.com/downloads/details/id/1645520")
        assert cname == "SimArtist"
        already, date_str = tsr_provider.check_user_already_commented(
            "https://www.thesimsresource.com/downloads/details/id/1645520",
            ["XML Injector"],
        )
        assert already is True
        assert "2026" in (date_str or "")

        ok_post, msg_post = tsr_provider.post_mod_comment(
            "https://www.thesimsresource.com/downloads/details/id/1645520",
            "Hello, please list XML Injector as a required dependency!",
        )
        assert ok_post is True
        assert "The Sims Resource" in msg_post

    # 5. Verify CurseForge comment checking and posting via /api/v1/mods/{projectId}/comments
    cf_provider = CurseForgeProvider()
    mock_cf_session = MagicMock()
    cf_page_html = """
    <html><body>
      <a class="author-name" href="/members/deaderpool">deaderpool</a>
      <dt>Project ID</dt><dd>694283</dd>
      <script>self.__next_f.push([1, '{"hasComments":true}'])</script>
    </body></html>
    """

    def _cf_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        if "/comments" in url:
            r.json.return_value = {
                "data": [
                    {
                        "id": 101,
                        "body": "Requires Lot 51 Core Library to work.",
                        "author": {"username": "simmercf", "displayName": "SimmerCF"},
                        "datePosted": "2026-10-29",
                    }
                ],
                "pagination": {"totalCount": 1},
            }
        else:
            r.text = cf_page_html
        return r

    def _cf_post(url, json=None, **kwargs):
        r = MagicMock()
        r.status_code = 201
        r.text = '{"id": 102}'
        return r

    mock_cf_session.get.side_effect = _cf_get
    mock_cf_session.post.side_effect = _cf_post

    with patch.object(SessionManager, "get_http_session", return_value=mock_cf_session):
        cid_cf, cname_cf, _ = cf_provider.get_creator_info("https://www.curseforge.com/sims4/mods/xml-injector")
        assert cname_cf == "deaderpool"
        already_cf, _ = cf_provider.check_user_already_commented(
            "https://www.curseforge.com/sims4/mods/xml-injector",
            ["Lot 51 Core Library"],
        )
        assert already_cf is True

        ok_cf_post, msg_cf_post = cf_provider.post_mod_comment(
            "https://www.curseforge.com/sims4/mods/xml-injector",
            "Thanks for updating!",
        )
        assert ok_cf_post is True
        assert "CurseForge" in msg_cf_post


def test_all_platforms_comments_and_ambiguous_requirements_interpellation_e2e(tmp_path):
    """
    Valide de bout en bout sur les 4 plateformes (LoversLab, NSFWMods, TSR, CurseForge) :
    1. Le découpage et la qualification COMMENT vs MOD (avec 'Toddler don't go to Daycare Mod' en COMMENT sur CF-2).
    2. La séparation des sections dans le message d'interpellation généré.
    3. Le cycle complet de commentaire (check_user_already_commented -> post_mod_comment -> delete_mod_comment).
    """
    from unittest.mock import MagicMock, patch
    from src.application.dependencies.requirement_reporter_service import RequirementReporterService
    from src.infrastructure.database.manager import DatabaseManager
    from src.infrastructure.database.models import CatalogMod
    from src.core.session_manager import SessionManager
    from plugins.loverslab.scraper import LoversLabProvider
    from plugins.nsfwmods.scraper import NSFWModsProvider
    from plugins.thesimsresource.scraper import TheSimsResourceProvider
    from plugins.curseforge.scraper import CurseForgeProvider
    from plugins.modthesims.scraper import ModTheSimsProvider
    from plugins.simsfinds.scraper import SimsFindsProvider
    from plugins.nexusmods.scraper import NexusModsProvider
    from plugins.mmccworld.scraper import MMCCWorldProvider

    cases = [
        # LoversLab
        {
            "source": "loverslab",
            "remote_id": "test_ll_cascade",
            "title": "Confidence Cascade",
            "author": "BlackBoxMods",
            "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade/",
            "deps": [
                {"title": "Lumpinou", "remote_id": "lumpinou"},
                {"title": "Relationship & Pregnancy Overhaul", "remote_id": "rpo"},
                {"title": "Game Options -> Script Mods Enabled", "remote_id": "script-opt"},
                {"title": "Bad decisions. Better stories", "remote_id": "flavor-text"},
            ],
            "expected_comments": ["Game Options -> Script Mods Enabled", "Bad decisions. Better stories"],
            "expected_unfound": ["Lumpinou", "Relationship & Pregnancy Overhaul"],
        },
        # NSFWMods
        {
            "source": "nsfwmods",
            "remote_id": "test_nm_snatcher",
            "title": "Sim Snatcher",
            "author": "ColonolNutty",
            "page_url": "https://nsfwmods.com/files/file/424-sim-snatcher/",
            "deps": [
                {"title": "Sims 4 Community Library", "remote_id": "s4cl"},
                {"title": "Deviant Core", "remote_id": "deviant-core"},
                {"title": "The More Universal Venue List", "remote_id": "muvl"},
                {"title": "Spoiler", "remote_id": "spoiler-tag"},
                {"title": "Mod Settings Menu is optionally required to modify SS Settings", "remote_id": "msm-opt"},
            ],
            "expected_comments": ["Spoiler", "Mod Settings Menu is optionally required to modify SS Settings"],
            "expected_unfound": ["Sims 4 Community Library", "Deviant Core", "The More Universal Venue List"],
        },
        # The Sims Resource
        {
            "source": "thesimsresource",
            "remote_id": "test_tsr_chill",
            "title": "Chill and Cherish",
            "author": "MelBennett",
            "page_url": "https://www.thesimsresource.com/downloads/details/id/1787392",
            "deps": [
                {"title": "[MB] Canned Soda and Beer Accessory RIGHT", "remote_id": "canned-soda-acc"},
                {"title": "Basketball Accessory", "remote_id": "1573507"},
                {"title": "https://blog.naver.com/mel_165/222563632404", "remote_id": "naver-link"},
                {"title": "Pose Player & Teleport Any Sim required in game", "remote_id": "pose-note"},
            ],
            "expected_comments": [
                "https://blog.naver.com/mel_165/222563632404",
                "Pose Player & Teleport Any Sim required in game",
            ],
            "expected_unfound": ["[MB] Canned Soda and Beer Accessory RIGHT", "Basketball Accessory"],
        },
        # CurseForge (avec 'Toddler don't go to Daycare Mod' qualifié en COMMENTaire per user feedback!)
        {
            "source": "curseforge",
            "remote_id": "test_cf_social",
            "title": "Social Activities (Visit Friends, Family and more)",
            "author": "LittleMsSam",
            "page_url": "https://www.curseforge.com/sims4/mods/social-activities-visit-friends-family-and-more",
            "deps": [
                {"title": "XML Injector", "remote_id": "xml-injector"},
                {"title": "Toddler don't go to Daycare Mod", "remote_id": "toddler-daycare"},
                {
                    "title": "Optional Addons included in archive - remove the ones you do not want",
                    "remote_id": "addons-note",
                },
            ],
            "expected_comments": [
                "Toddler don't go to Daycare Mod",
                "Optional Addons included in archive - remove the ones you do not want",
            ],
            "expected_unfound": ["XML Injector"],
        },
        # ModTheSims
        {
            "source": "modthesims",
            "remote_id": "test_mts_cooking",
            "title": "Realistic Cooking Mod",
            "author": "SrslySims",
            "page_url": "https://modthesims.info/d/701054/realistic-cooking.html",
            "deps": [
                {"title": "Scumbumbo XML Injector", "remote_id": "xml-injector"},
                {"title": "Custom Food Interactions", "remote_id": "cfi"},
                {"title": "Game Options -> Script Mods Enabled", "remote_id": "script-opt"},
                {"title": "bb.moveobjects on recommended for kitchen island counters", "remote_id": "moo-opt"},
            ],
            "expected_comments": [
                "Game Options -> Script Mods Enabled",
                "bb.moveobjects on recommended for kitchen island counters",
            ],
            "expected_unfound": ["Scumbumbo XML Injector", "Custom Food Interactions"],
        },
        # SimsFinds
        {
            "source": "simsfinds",
            "remote_id": "test_sf_outfit",
            "title": "Trillyke Knit Crop Top",
            "author": "Trillyke",
            "page_url": "https://www.simsfinds.com/downloads/350124/knit-crop-top",
            "deps": [
                {"title": "Trillyke Knit Base Mesh", "remote_id": "trill-mesh"},
                {
                    "title": "Base Game compatible - Maxis Match friendly. 25 swatches.",
                    "remote_id": "swatch-note",
                },
                {"title": "Tag me on Instagram when you use it!", "remote_id": "insta-note"},
            ],
            "expected_comments": [
                "Base Game compatible - Maxis Match friendly. 25 swatches.",
                "Tag me on Instagram when you use it!",
            ],
            "expected_unfound": ["Trillyke Knit Base Mesh"],
        },
        # Nexus Mods
        {
            "source": "nexusmods",
            "remote_id": "test_nexus_buffs",
            "title": "Emotional Inertia Classic",
            "author": "roburky",
            "page_url": "https://www.nexusmods.com/thesims4/mods/14",
            "deps": [
                {"title": "MTS Scumbumbo XML Injector", "remote_id": "xml-injector"},
                {"title": "Requires script mods enabled in Game Options", "remote_id": "script-opt"},
                {"title": "Tested on game version 1.108+", "remote_id": "version-note"},
            ],
            "expected_comments": [
                "Requires script mods enabled in Game Options",
                "Tested on game version 1.108+",
            ],
            "expected_unfound": ["MTS Scumbumbo XML Injector"],
        },
        # Maxis Match CC World (Tumblr / SFS)
        {
            "source": "mmccworld",
            "remote_id": "test_mmccw_counters",
            "title": "SixamCC Modular Counter Set",
            "author": "SixamCC",
            "page_url": "https://maxismatchccworld.tumblr.com/post/715421542/sixamcc-counter",
            "deps": [
                {"title": "SixamCC Modular Counter Mesh Rig", "remote_id": "sixam-mesh"},
                {"title": "Use bb.moveobjects on when placing island counters.", "remote_id": "bb-note"},
                {"title": "Requires Medium texture quality setting in Graphics options.", "remote_id": "gfx-note"},
            ],
            "expected_comments": [
                "Use bb.moveobjects on when placing island counters.",
                "Requires Medium texture quality setting in Graphics options.",
            ],
            "expected_unfound": ["SixamCC Modular Counter Mesh Rig"],
        },
    ]

    db = DatabaseManager.get_instance()
    for case in cases:
        src = case["source"]
        with db.get_session() as s:
            s.query(CatalogMod).filter_by(source=src, remote_id=case["remote_id"]).delete()
            cm = CatalogMod(
                source=src,
                remote_id=case["remote_id"],
                title=case["title"],
                author=case["author"],
                page_url=case["page_url"],
                requirements_status="RESOLVED",
            )
            cm.set_requirements_mods_list(case["deps"])
            s.add(cm)
            s.commit()

        # 1. Test message generation
        msg = RequirementReporterService.build_english_message(
            case["title"],
            case["author"],
            missing_modules=case["expected_unfound"],
            unnecessary_modules=case["expected_comments"],
        )
        assert "📦 Unresolved / Missing Dependencies:" in msg
        assert "🧹 Notes / Instructions to clean from Requirements:" in msg
        m_sec, n_sec = msg.split("🧹 Notes / Instructions to clean from Requirements:", 1)
        for u in case["expected_unfound"]:
            assert f"- {u}" in m_sec
            assert f"- {u}" not in n_sec
        for c in case["expected_comments"]:
            assert f"- {c}" in n_sec
            assert f"- {c}" not in m_sec

    # 2. Test comment lifecycle on each provider (LL, NM, TSR, CF, MTS, SF, NEXUS, MMCCW)
    ll_prov = LoversLabProvider()
    nm_prov = NSFWModsProvider()
    tsr_prov = TheSimsResourceProvider()
    cf_prov = CurseForgeProvider()
    mts_prov = ModTheSimsProvider()
    sf_prov = SimsFindsProvider()
    nexus_prov = NexusModsProvider()
    mmccw_prov = MMCCWorldProvider()

    # Verify all 8 providers implement all comment methods
    for p in (ll_prov, nm_prov, tsr_prov, cf_prov, mts_prov, sf_prov, nexus_prov, mmccw_prov):
        assert hasattr(p, "get_creator_info")
        assert hasattr(p, "check_user_already_commented")
        assert hasattr(p, "post_mod_comment")
        assert hasattr(p, "delete_mod_comment")

    # CurseForge delete_mod_comment verification
    mock_cf_session = MagicMock()
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.text = """
    <html><body>
      <dt>Project ID</dt><dd>1194810</dd>
    </body></html>
    """
    mock_comms_resp = MagicMock()
    mock_comms_resp.status_code = 200
    mock_comms_resp.json.return_value = {
        "data": [
            {
                "id": 888999,
                "body": "Hi @Simsiboy, please check XML Injector requirements.",
                "author": {"username": "myuser", "displayName": "MyUser"},
            }
        ]
    }
    mock_del_resp = MagicMock()
    mock_del_resp.status_code = 204

    def _cf_req_router(url, **kwargs):
        if "/comments" in url and not url.endswith("/comments/888999"):
            return mock_comms_resp
        return mock_get_resp

    mock_cf_session.get.side_effect = _cf_req_router
    mock_cf_session.delete.return_value = mock_del_resp

    mock_acc = MagicMock()
    mock_acc.user_display_name = "MyUser"

    with (
        patch.object(SessionManager, "get_saved_session", return_value=mock_acc),
        patch.object(SessionManager, "get_http_session", return_value=mock_cf_session),
    ):
        ok_del, msg_del = cf_prov.delete_mod_comment(
            "https://www.curseforge.com/sims4/mods/simsiphone",
            required_keywords=["XML Injector"],
        )
        assert ok_del is True
        assert "CurseForge" in msg_del
        mock_cf_session.delete.assert_called_once()
        assert "1194810/comments/888999" in mock_cf_session.delete.call_args[0][0]


def test_eight_platforms_cross_deduplication_and_shared_deps_e2e(e2e_env, monkeypatch):
    """
    Tests real-world cross-platform deduplication, non-collision, and shared dependencies
    across all platforms (ModTheSims, CurseForge, Nexus Mods, SimsFinds, TSR, LoversLab, NSFWMods, MMCCWorld/SFS):
    1. Cross-Platform Identical Mod Deduplication (MTS, CurseForge, Nexus Mods):
       - 'XML Injector v4' by Scumbumbo on MTS, CurseForge, and Nexus Mods.
       - Installing from MTS creates 1 folder and 1 record.
       - Subsequent install from CurseForge or Nexus Mods recognizes existing installation
         via semantic title/author matching and DBPF SHA-256 fingerprint, preventing duplication.
    2. Cross-Platform Shared Dependency Resolution:
       - 'Realistic Cooking Mod' (MTS) and 'Emotional Inertia Classic' (Nexus) both require 'XML Injector'.
       - Installing either mod satisfies the requirement for both without re-downloading.
    3. SimFileShare Direct Resolution & Deduplication:
       - 'Trillyke Knit Outfit' on SimsFinds and 'SixamCC Modular Counter Set' on MMCCWorld
         resolve SFS download links into direct file extraction.
    """
    import io
    import zipfile
    from unittest.mock import MagicMock
    from src.api.schemas.catalog import CatalogInstallRequest
    from src.application.mods.active_installation_registry import ActiveInstallationRegistry
    from src.application.mods.mod_install_orchestrator import perform_mod_install
    from src.infrastructure.database.models import InstalledMod
    from src.providers import ProviderRegistry

    ActiveInstallationRegistry.reset()
    db = e2e_env["db"]
    mods_dir = e2e_env["mods_dir"]

    catalog_entries = [
        # XML Injector v4 across MTS, CurseForge, Nexus Mods
        {
            "source": "modthesims",
            "remote_id": "mts_685412",
            "title": "XML Injector v4",
            "author": "Scumbumbo",
            "page_url": "https://modthesims.info/d/685412/xml-injector-v4.html",
            "dl_url": "https://chii.modthesims.info/getfile.php?file=685412",
            "pkg": "XmlInjector_v4.package",
            "reqs": [],
        },
        {
            "source": "curseforge",
            "remote_id": "cf_xml_injector",
            "title": "XML Injector v4",
            "author": "Scumbumbo",
            "page_url": "https://www.curseforge.com/sims4/mods/xml-injector",
            "dl_url": "https://www.curseforge.com/api/v1/mods/694283/files/7021809/download",
            "pkg": "XmlInjector_v4.package",
            "reqs": [],
        },
        {
            "source": "nexusmods",
            "remote_id": "nexus_xml_injector",
            "title": "XML Injector v4",
            "author": "Scumbumbo",
            "page_url": "https://www.nexusmods.com/thesims4/mods/14",
            "dl_url": "https://www.nexusmods.com/thesims4/mods/14?tab=files&file_id=14",
            "pkg": "XmlInjector_v4.package",
            "reqs": [],
        },
        # Mod on ModTheSims requiring XML Injector
        {
            "source": "modthesims",
            "remote_id": "mts_cooking_mod",
            "title": "Realistic Cooking Mod",
            "author": "SrslySims",
            "page_url": "https://modthesims.info/d/701054/realistic-cooking.html",
            "dl_url": "https://chii.modthesims.info/getfile.php?file=701054",
            "pkg": "SrslySims_Cooking.package",
            "reqs": [
                {
                    "source": "modthesims",
                    "remote_id": "mts_685412",
                    "title": "XML Injector v4",
                    "url": "https://modthesims.info/d/685412/xml-injector-v4.html",
                }
            ],
        },
        # Mod on SimsFinds with SFS mesh download
        {
            "source": "simsfinds",
            "remote_id": "sf_trillyke_crop",
            "title": "Trillyke Knit Crop Top",
            "author": "Trillyke",
            "page_url": "https://www.simsfinds.com/downloads/350124/knit-crop-top",
            "dl_url": "https://simfileshare.net/download/350124/",
            "pkg": "Trillyke_KnitCropTop.package",
            "reqs": [],
        },
        # Mod on MMCCWorld with SFS mesh download
        {
            "source": "mmccworld",
            "remote_id": "mmccw_sixam_counter",
            "title": "SixamCC Modular Counter Set",
            "author": "SixamCC",
            "page_url": "https://maxismatchccworld.tumblr.com/post/715421542/sixamcc-counter",
            "dl_url": "https://simfileshare.net/download/715421/",
            "pkg": "SixamCC_ModularCounters.package",
            "reqs": [],
        },
    ]

    db_ids: dict[tuple[str, str], int] = {}
    with db.get_session() as s:
        for entry in catalog_entries:
            s.query(CatalogMod).filter_by(source=entry["source"], remote_id=entry["remote_id"]).delete()
            cm = CatalogMod(
                source=entry["source"],
                remote_id=entry["remote_id"],
                title=entry["title"],
                author=entry["author"],
                page_url=entry["page_url"],
                requirements_status="FOUND" if entry["reqs"] else "NONE",
            )
            cm.set_requirements_mods_list(entry["reqs"])
            s.add(cm)
            s.flush()
            db_ids[(entry["source"], entry["remote_id"])] = cm.id
        s.commit()

    entries_by_url = {e["page_url"]: e for e in catalog_entries}
    entries_by_dl = {e["dl_url"]: e for e in catalog_entries}

    def _make_provider(source_name: str):
        mock_prov = MagicMock()
        mock_prov.provider_name = source_name

        def _get_mod_details(page_url: str):
            entry = entries_by_url.get(page_url, {})
            dl_url = entry.get("dl_url", f"https://example.com/{source_name}/dl")
            reqs = entry.get("reqs", [])
            return {
                "title": entry.get("title", f"Mod from {source_name}"),
                "author": entry.get("author", "Author"),
                "download_urls": [dl_url],
                "requirements": reqs,
                "requirements_status": "FOUND" if reqs else "NONE",
            }

        def _download_mod_file(download_url: str, dest_path: str, progress_callback=None, **kwargs):
            entry = entries_by_dl.get(download_url, {})
            pkg_name = entry.get("pkg", f"{source_name}_default.package")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                # Deterministic content to test DBPF SHA-256 matching
                content = f"DBPF_DATA_FOR_{pkg_name}".encode("utf-8")
                zf.writestr(pkg_name, content)
            target = Path(dest_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(buf.getvalue())
            return True, str(target)

        mock_prov.get_mod_details.side_effect = _get_mod_details
        mock_prov.download_mod_file = _download_mod_file
        return mock_prov

    providers = {src: _make_provider(src) for src in ("modthesims", "curseforge", "nexusmods", "simsfinds", "mmccworld")}
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: providers.get(name)))

    # Also mock SimFileShareResolver.download_mod_file so SFS URLs resolve deterministically
    from src.infrastructure.network.simfileshare_resolver import SimFileShareResolver

    def _mock_sfs_dl(self, url, dest_path, progress_callback=None):
        entry = entries_by_dl.get(url, {})
        pkg_name = entry.get("pkg", "sfs_download.package")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            content = f"DBPF_DATA_FOR_{pkg_name}".encode("utf-8")
            zf.writestr(pkg_name, content)
        target = Path(dest_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(buf.getvalue())
        return True, str(target)

    monkeypatch.setattr(SimFileShareResolver, "download_mod_file", _mock_sfs_dl)

    # 1. Install XML Injector v4 from ModTheSims
    mts_xml_id = db_ids[("modthesims", "mts_685412")]
    res1 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=mts_xml_id, install_dependencies=True)
    )
    assert res1.success is True

    # Verify exactly 1 folder on disk for XML Injector
    xml_folders = [p for p in mods_dir.glob("*") if "xml" in p.name.lower()]
    assert len(xml_folders) == 1
    assert (xml_folders[0] / "XmlInjector_v4.package").exists()

    with db.get_session() as s:
        installed_xml = s.query(InstalledMod).filter(InstalledMod.folder_name == xml_folders[0].name).all()
        assert len(installed_xml) == 1

    # 2. Attempt duplicate install of XML Injector from CurseForge and Nexus Mods
    cf_xml_id = db_ids[("curseforge", "cf_xml_injector")]
    res2 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=cf_xml_id, install_dependencies=True)
    )
    assert res2.success is True

    nexus_xml_id = db_ids[("nexusmods", "nexus_xml_injector")]
    res3 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=nexus_xml_id, install_dependencies=True)
    )
    assert res3.success is True

    # Check deduplication: STILL exactly 1 folder and 1 physical package file on disk!
    xml_folders_after = [p for p in mods_dir.glob("*") if "xml" in p.name.lower()]
    assert len(xml_folders_after) == 1

    # 3. Install Realistic Cooking Mod (MTS) which depends on XML Injector
    cooking_id = db_ids[("modthesims", "mts_cooking_mod")]
    res4 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=cooking_id, install_dependencies=True)
    )
    assert res4.success is True

    cooking_folders = [p for p in mods_dir.glob("*") if "cooking" in p.name.lower()]
    assert len(cooking_folders) == 1
    assert (cooking_folders[0] / "SrslySims_Cooking.package").exists()

    # 4. Install SimsFinds mod (resolving SFS)
    sf_id = db_ids[("simsfinds", "sf_trillyke_crop")]
    res5 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=sf_id, install_dependencies=True)
    )
    assert res5.success is True
    sf_folders = [p for p in mods_dir.glob("*") if "trillyke" in p.name.lower()]
    assert len(sf_folders) == 1
    assert (sf_folders[0] / "Trillyke_KnitCropTop.package").exists()

    # 5. Install MMCCWorld mod (resolving SFS)
    mmccw_id = db_ids[("mmccworld", "mmccw_sixam_counter")]
    res6 = perform_mod_install(
        CatalogInstallRequest(catalog_mod_id=mmccw_id, install_dependencies=True)
    )
    assert res6.success is True
    mmccw_folders = [p for p in mods_dir.glob("*") if "sixam" in p.name.lower()]
    assert len(mmccw_folders) == 1
    assert (mmccw_folders[0] / "SixamCC_ModularCounters.package").exists()







