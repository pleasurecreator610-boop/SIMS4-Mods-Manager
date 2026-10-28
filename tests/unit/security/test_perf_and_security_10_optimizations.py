"""Tests unitaires validant les 10 optimisations de Sécurité (S1-S5) et de Performance (P1-P5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import zipfile

import pytest
from starlette.testclient import TestClient

from src.api.app import app
from src.application.mods.conflict_detector_service import ConflictDetectorService
from src.application.mods.installed_mods_service import InstalledModsService
from src.application.mods.mod_install_actions import ModInstallActions
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity
from src.infrastructure.database.models import AccountSession
from src.infrastructure.filesystem.archive_extractor import (
    ArchiveExtractor,
    ArchiveSecurityError,
    validate_archive_quotas,
)
from src.utils.title_normalizer import TitleNormalizer


def test_s1_thumbnail_ssrf_and_path_traversal_blocked(monkeypatch):
    """S1: Vérifie que /api/catalog/thumbnail bloque les attaques SSRF (loopback, IPs privées, file://) et Path Traversal."""
    monkeypatch.setenv("SIMS4_DISABLE_AUTH", "1")
    client = TestClient(app)

    # 1. Path traversal dans remote_id ou source
    resp_trav = client.get(
        "/api/catalog/thumbnail",
        params={"source": "loverslab", "remote_id": "../../evil", "url": "https://www.loverslab.com/thumb.jpg"},
    )
    assert resp_trav.status_code == 400

    # 2. SSRF vers loopback 127.0.0.1
    resp_ssrf_loopback = client.get(
        "/api/catalog/thumbnail",
        params={"source": "loverslab", "remote_id": "1234", "url": "http://127.0.0.1:8000/api/settings"},
    )
    assert resp_ssrf_loopback.status_code == 400

    # 3. SSRF vers metadata cloud 169.254.169.254
    resp_ssrf_meta = client.get(
        "/api/catalog/thumbnail",
        params={"source": "loverslab", "remote_id": "1234", "url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp_ssrf_meta.status_code == 400

    # 4. Schéma file:// interdit
    resp_scheme = client.get(
        "/api/catalog/thumbnail",
        params={"source": "loverslab", "remote_id": "1234", "url": "file:///C:/Windows/win.ini"},
    )
    assert resp_scheme.status_code == 400


def test_s2_account_session_dpapi_encryption_and_legacy_fallback():
    """S2: Vérifie le chiffrement DPAPI au repos des cookies AccountSession et la rétrocompatibilité enc:."""
    acc = AccountSession(provider_name="loverslab", is_authenticated=True)
    secret_cookies = {"cf_clearance": "secret_cf_token", "ips4_pass_hash": "super_secret_hash"}
    acc.set_cookies_dict(secret_cookies)

    assert isinstance(acc.cookies_data, str)
    assert acc.cookies_data.startswith(("dpapi:", "enc:"))
    assert "super_secret_hash" not in acc.cookies_data

    recovered = acc.get_cookies_dict()
    assert recovered == secret_cookies

    # Vérification de la rétrocompatibilité avec l'ancien format enc:
    import base64
    import json

    legacy_payload = base64.b64encode(json.dumps({"legacy_cookie": "val123"}).encode("utf-8")).decode("ascii")
    acc.cookies_data = f"enc:{legacy_payload}"
    assert acc.get_cookies_dict() == {"legacy_cookie": "val123"}


def test_s3_ts4script_strict_validation(tmp_path: Path):
    """S3: Vérifie que is_valid_ts4script bloque les .pyd/.dll, les traversals '..' et les archives corrompues."""
    # 1. Script valide contenant du bytecode Python (.pyc)
    valid_script = tmp_path / "valid_mod.ts4script"
    with zipfile.ZipFile(valid_script, "w") as zf:
        zf.writestr("mod_main.pyc", b"PYTHON_BYTECODE")
    assert ModInstallActions.is_valid_ts4script(valid_script) is True

    # 2. Script contenant un binaire .pyd interdit
    pyd_script = tmp_path / "malicious_pyd.ts4script"
    with zipfile.ZipFile(pyd_script, "w") as zf:
        zf.writestr("inject.pyd", b"MZ_NATIVE_EXTENSION")
    assert ModInstallActions.is_valid_ts4script(pyd_script) is False

    # 3. Script contenant un path traversal '..'
    traversal_script = tmp_path / "traversal.ts4script"
    with zipfile.ZipFile(traversal_script, "w") as zf:
        zf.writestr("../escape.pyc", b"ESCAPE")
    assert ModInstallActions.is_valid_ts4script(traversal_script) is False

    # 4. Fichier commençant par PK mais ZIP corrompu
    corrupt_script = tmp_path / "corrupt.ts4script"
    corrupt_script.write_bytes(b"PK\x03\x04CORRUPTED_ZIP_DATA")
    assert ModInstallActions.is_valid_ts4script(corrupt_script) is False


def test_s4_archive_security_error_stops_immediately(tmp_path: Path):
    """S4: Vérifie que ArchiveSecurityError est levée par validate_archive_quotas et stoppe ArchiveExtractor sans repli."""
    dummy_zip = tmp_path / "bomb.zip"
    with zipfile.ZipFile(dummy_zip, "w") as zf:
        zf.writestr("a.txt", b"hello")

    with pytest.raises(ArchiveSecurityError):
        validate_archive_quotas(dummy_zip, total_uncompressed_bytes=100, file_count=50_000)

    extractor = ArchiveExtractor()
    # Simuler un handler levant ArchiveSecurityError et vérifier que le 2e handler n'est jamais appelé
    h1 = MagicMock()
    h1.can_handle.return_value = True
    h1.extract.side_effect = ArchiveSecurityError("Zip Bomb détectée")
    h2 = MagicMock()
    h2.can_handle.return_value = True
    extractor._handlers = [h1, h2]

    with pytest.raises(ArchiveSecurityError):
        extractor.extract(dummy_zip, tmp_path / "out")
    h2.extract.assert_not_called()


def test_s5_security_headers_present_on_api_responses(monkeypatch):
    """S5: Vérifie la présence des en-têtes HTTP de sécurité sur les réponses de l'API."""
    monkeypatch.setenv("SIMS4_DISABLE_AUTH", "1")
    client = TestClient(app)
    resp = client.get("/api/system/ping")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


def test_p1_installed_mods_service_uses_targeted_catalog_query():
    """P1: Vérifie que list_installed_mods appelle get_by_ids_or_remote_ids au lieu de charger tout le catalogue (get_all)."""
    mock_inst_repo = MagicMock()
    mock_cat_repo = MagicMock()
    mock_update_svc = MagicMock()
    mock_update_svc.check_update_available.return_value = False

    mock_inst_repo.get_all.return_value = [
        InstalledModEntity(
            id=1,
            catalog_mod_id=42,
            source="loverslab",
            remote_id="51444",
            title="Confidence Cascade",
            folder_name="Confidence_Cascade",
            is_enabled=True,
        )
    ]
    mock_cat_repo.get_by_ids_or_remote_ids.return_value = [
        CatalogModEntity(
            id=42,
            source="loverslab",
            remote_id="51444",
            title="Confidence Cascade",
            author="BlackBoxMods",
        )
    ]

    svc = InstalledModsService(
        installed_repo=mock_inst_repo,
        catalog_repo=mock_cat_repo,
        update_service=mock_update_svc,
    )
    res = svc.list_installed_mods()
    assert res.total == 1
    assert res.items[0].author == "BlackBoxMods"
    mock_cat_repo.get_by_ids_or_remote_ids.assert_called_once_with([42], ["51444"])
    mock_cat_repo.get_all.assert_not_called()


def test_p2_title_normalizer_lru_cache_hit():
    """P2: Vérifie que les méthodes de normalisation utilisent le cache LRU."""
    TitleNormalizer.clean_mod_title.cache_clear()
    TitleNormalizer.canonical_fingerprint.cache_clear()

    res1 = TitleNormalizer.clean_mod_title("[TS4] WickedWhims v178 by TURBODRIVER")
    res2 = TitleNormalizer.clean_mod_title("[TS4] WickedWhims v178 by TURBODRIVER")
    assert res1 == res2
    assert TitleNormalizer.clean_mod_title.cache_info().hits >= 1

    fp1 = TitleNormalizer.canonical_fingerprint("XML-Injector")
    fp2 = TitleNormalizer.canonical_fingerprint("XML-Injector")
    assert fp1 == fp2
    assert TitleNormalizer.canonical_fingerprint.cache_info().hits >= 1


def test_p4_conflict_detector_prunes_disabled_directories(tmp_path: Path):
    """P4: Vérifie que _scan_enabled_packages ignore immédiatement les sous-dossiers .disabled et cachés."""
    enabled_dir = tmp_path / "ActiveMod"
    enabled_dir.mkdir()
    pkg_ok = enabled_dir / "active.package"
    pkg_ok.write_bytes(b"DBPF")

    disabled_dir = tmp_path / "DisabledMod.disabled"
    disabled_dir.mkdir()
    (disabled_dir / "ignored.package").write_bytes(b"DBPF")

    hidden_dir = tmp_path / ".hidden_cache"
    hidden_dir.mkdir()
    (hidden_dir / "hidden.package").write_bytes(b"DBPF")

    found = ConflictDetectorService._scan_enabled_packages(tmp_path)
    assert found == [pkg_ok]
