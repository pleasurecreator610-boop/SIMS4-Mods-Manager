"""Tests unitaires pour le parseur binaire DBPF et le détecteur de conflits."""

import struct
from pathlib import Path

from src.infrastructure.filesystem.dbpf_parser import DbpfParser
from src.application.mods.conflict_detector_service import ConflictDetectorService



def create_mock_dbpf_package(file_path: Path, tgi_list: list[tuple[int, int, int]]) -> Path:
    """Crée un fichier conteneur DBPF 2.0 synthétique valide pour les tests."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    header_size = 96
    index_offset = header_size
    entry_size = 32
    index_size = 4 + (len(tgi_list) * entry_size)

    # Création de l'en-tête (96 octets)
    header = bytearray(header_size)
    struct.pack_into("<4sII", header, 0, b"DBPF", 2, 0)
    struct.pack_into("<I", header, 40, len(tgi_list))  # index_record_count
    struct.pack_into("<I", header, 44, index_offset)    # index_pos_low
    struct.pack_into("<I", header, 48, index_size)     # index_size

    # Table d'index
    index_data = bytearray()
    index_data += struct.pack("<I", 0)  # flags: pas de constantes

    dummy_data_offset = index_offset + index_size
    for type_id, group_id, inst_id in tgi_list:
        index_data += struct.pack(
            "<IIQIIIHH",
            type_id,
            group_id,
            inst_id,
            dummy_data_offset,
            10,  # file size
            10,  # decompressed size
            0,   # compressed flag
            0,   # dummy
        )
        dummy_data_offset += 10

    with open(file_path, "wb") as f:
        f.write(header)
        f.write(index_data)
        f.write(b"DUMMYDATA!" * len(tgi_list))

    return file_path


def test_dbpf_parser_is_dbpf(tmp_path: Path):
    """Vérifie la détection de la signature DBPF."""
    pkg_path = tmp_path / "valid.package"
    create_mock_dbpf_package(pkg_path, [(0x03B33DDF, 0x80000000, 0x1111222233334444)])

    non_pkg = tmp_path / "fake.txt"
    non_pkg.write_text("Hello world")

    assert DbpfParser.is_dbpf(pkg_path) is True
    assert DbpfParser.is_dbpf(non_pkg) is False


def test_dbpf_parser_extracts_tgi_entries(tmp_path: Path):
    """Vérifie l'extraction correcte des clés TGI depuis un package."""
    pkg_path = tmp_path / "mod_tuning.package"
    tgi_1 = (0x03B33DDF, 0x80000000, 0x1234567890ABCDEF)
    tgi_2 = (0x7387A39C, 0x80000000, 0xAABBCCDDEEFF0011)

    create_mock_dbpf_package(pkg_path, [tgi_1, tgi_2])

    entries = DbpfParser.parse_index(pkg_path)
    assert len(entries) == 2

    assert entries[0].key.type_id == 0x03B33DDF
    assert entries[0].key.group_id == 0x80000000
    assert entries[0].key.instance_id == 0x1234567890ABCDEF
    assert entries[0].key.resource_type_name == "Tuning / XML"
    assert "0x03B33DDF" in entries[0].key.tgi_str

    assert entries[1].key.type_id == 0x7387A39C
    assert entries[1].key.resource_type_name == "Tuning Instance"


def test_conflict_detector_finds_collisions(tmp_path: Path):
    """Vérifie la détection de conflits entre deux mods partageant la même ressource TGI."""
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    shared_tgi = (0x03B33DDF, 0x80000000, 0x9999888877776666)
    unique_tgi_a = (0x220557DA, 0x80000000, 0x1111111111111111)
    unique_tgi_b = (0x034AEECB, 0x80000000, 0x2222222222222222)

    # Mod A
    pkg_a = mods_dir / "ModA" / "mod_a.package"
    create_mock_dbpf_package(pkg_a, [shared_tgi, unique_tgi_a])

    # Mod B (contient la même ressource shared_tgi !)
    pkg_b = mods_dir / "ModB" / "mod_b.package"
    create_mock_dbpf_package(pkg_b, [shared_tgi, unique_tgi_b])

    # Mod C (mod sans conflit)
    pkg_c = mods_dir / "ModC" / "mod_c.package"
    create_mock_dbpf_package(pkg_c, [unique_tgi_a])  # shared with A, but distinct

    detector = ConflictDetectorService()
    report = detector.detect_conflicts(mods_dir)

    assert report.total_packages_scanned == 3
    assert report.conflict_count >= 1

    # Trouver le conflit sur shared_tgi
    shared_conflict = next(
        (c for c in report.conflicts if f"0x{shared_tgi[0]:08X}" in c.tgi),
        None,
    )
    assert shared_conflict is not None
    assert len(shared_conflict.conflicting_packages) == 2
    assert any("ModA" in p for p in shared_conflict.conflicting_packages)
    assert any("ModB" in p for p in shared_conflict.conflicting_packages)
