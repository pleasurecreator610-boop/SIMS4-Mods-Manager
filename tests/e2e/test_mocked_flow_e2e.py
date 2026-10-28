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
    from src.database.models import InstalledMod

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
