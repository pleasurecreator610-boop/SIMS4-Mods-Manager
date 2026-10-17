"""Tests d'intégration pour l'endpoint GET /api/installed/conflicts."""

from fastapi.testclient import TestClient
from src.api.app import app
from src.application.mods.conflict_detector_service import ConflictDetectorService, ModConflictReport, ModConflictItem


def test_get_installed_conflicts_endpoint(monkeypatch):
    """Vérifie le bon fonctionnement de l'endpoint /api/installed/conflicts."""
    client = TestClient(app)

    # Simuler le rapport de détection de conflit
    fake_report = ModConflictReport(
        total_packages_scanned=10,
        total_resources_indexed=150,
        conflict_count=1,
        conflicts=[
            ModConflictItem(
                tgi="0x03B33DDF-0x80000000-0x1234567890ABCDEF",
                resource_type_name="Tuning / XML",
                conflicting_packages=["ModA/mod_a.package", "ModB/mod_b.package"],
            )
        ],
    )

    monkeypatch.setattr(
        ConflictDetectorService,
        "detect_conflicts",
        lambda self, mods_dir: fake_report,
    )

    response = client.get("/api/installed/conflicts")
    assert response.status_code == 200

    data = response.json()
    assert data["total_packages_scanned"] == 10
    assert data["total_resources_indexed"] == 150
    assert data["conflict_count"] == 1
    assert len(data["conflicts"]) == 1

    item = data["conflicts"][0]
    assert item["tgi"] == "0x03B33DDF-0x80000000-0x1234567890ABCDEF"
    assert item["resource_type_name"] == "Tuning / XML"
    assert len(item["conflicting_packages"]) == 2
