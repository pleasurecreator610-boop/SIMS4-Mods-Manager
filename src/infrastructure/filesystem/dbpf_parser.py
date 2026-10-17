"""Parseur binaire haute performance pour les conteneurs DBPF des Sims 4 (.package).

Permet d'extraire la table d'index des ressources TGI (Type, Group, Instance 64-bit)
sans charger les données lourdes en mémoire, afin de détecter les collisions de tuning.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.utils.logger import logger


# Types de ressources Sims 4 courants pour l'identification humaine
KNOWN_RESOURCE_TYPES: dict[int, str] = {
    0x03B33DDF: "Tuning / XML",
    0x7387A39C: "Tuning Instance",
    0x220557DA: "String Table (STBL)",
    0x034AEECB: "CAS Part",
    0x8EAF13DE: "Skeleton Rig",
    0xB61DE6B4: "Object Definition",
    0x319E4F1D: "Object Catalog",
    0x62B28B02: "Model / Mesh",
    0x00B2D882: "Texture / Image (DDS/DST)",
    0x545AC67A: "Sim Data",
    0x025C95B6: "Animation Clip",
}


@dataclass(frozen=True)
class DbpfResourceKey:
    """Clé TGI identifiant de manière unique une ressource dans le moteur Sims 4."""

    type_id: int
    group_id: int
    instance_id: int

    @property
    def tgi_str(self) -> str:
        """Formatte la clé au format standard hexadécimal Type-Group-Instance."""
        return f"0x{self.type_id:08X}-0x{self.group_id:08X}-0x{self.instance_id:016X}"

    @property
    def resource_type_name(self) -> str:
        """Retourne un nom lisible du type de ressource."""
        return KNOWN_RESOURCE_TYPES.get(self.type_id, f"Resource (0x{self.type_id:08X})")


@dataclass
class DbpfResourceEntry:
    """Entrée d'index d'une ressource au sein d'un fichier .package."""

    key: DbpfResourceKey
    file_offset: int
    file_size: int
    decompressed_size: int
    is_compressed: bool


class DbpfParser:
    """Parseur binaire pour conteneurs DBPF 2.0 / 2.1 (The Sims 4 .package)."""

    HEADER_MAGIC = b"DBPF"
    HEADER_SIZE = 96

    @classmethod
    def is_dbpf(cls, file_path: Path) -> bool:
        """Vérifie si le fichier débute par l'en-tête binaire 'DBPF'."""
        if not file_path.is_file() or file_path.stat().st_size < cls.HEADER_SIZE:
            return False
        try:
            with open(file_path, "rb") as f:
                return f.read(4) == cls.HEADER_MAGIC
        except Exception:
            return False

    @classmethod
    def parse_index(cls, file_path: Path) -> List[DbpfResourceEntry]:
        """Lit la table d'index du fichier .package et retourne toutes les clés TGI.

        Cette opération ne lit que l'en-tête et la table d'index (très rapide).
        """
        if not cls.is_dbpf(file_path):
            return []

        entries: List[DbpfResourceEntry] = []
        try:
            file_size = file_path.stat().st_size
            with open(file_path, "rb") as f:
                header = f.read(cls.HEADER_SIZE)
                if len(header) < cls.HEADER_SIZE:
                    return []

                magic, major, minor = struct.unpack_from("<4sII", header, 0)
                if magic != cls.HEADER_MAGIC or major != 2:
                    return []

                index_record_count = struct.unpack_from("<I", header, 40)[0]
                index_pos_low = struct.unpack_from("<I", header, 44)[0]
                index_size = struct.unpack_from("<I", header, 48)[0]

                # Position 64-bit de l'index dans DBPF 2.1 si spécifiée
                index_pos_64 = struct.unpack_from("<Q", header, 64)[0]
                index_offset = index_pos_64 if (index_pos_64 > 0 and index_pos_64 < file_size) else index_pos_low

                if index_record_count == 0 or index_offset >= file_size or index_offset <= 0:
                    return []

                f.seek(index_offset)
                index_data = f.read(index_size)
                if len(index_data) < 4:
                    return []

                # Format Sims 4 Index 7.x
                # Les 4 premiers octets indiquent les flags de constantes (constant Type/Group/Instance)
                flags = struct.unpack_from("<I", index_data, 0)[0]
                offset = 4

                const_type: Optional[int] = None
                const_group: Optional[int] = None
                const_inst_high: Optional[int] = None

                if flags & 0x01:
                    const_type = struct.unpack_from("<I", index_data, offset)[0]
                    offset += 4
                if flags & 0x02:
                    const_group = struct.unpack_from("<I", index_data, offset)[0]
                    offset += 4
                if flags & 0x04:
                    const_inst_high = struct.unpack_from("<I", index_data, offset)[0]
                    offset += 4

                for _ in range(index_record_count):
                    if offset >= len(index_data):
                        break

                    r_type = const_type if const_type is not None else struct.unpack_from("<I", index_data, offset)[0]
                    if const_type is None:
                        offset += 4

                    r_group = const_group if const_group is not None else struct.unpack_from("<I", index_data, offset)[0]
                    if const_group is None:
                        offset += 4

                    if const_inst_high is not None:
                        inst_low = struct.unpack_from("<I", index_data, offset)[0]
                        offset += 4
                        r_instance = (const_inst_high << 32) | inst_low
                    else:
                        r_instance = struct.unpack_from("<Q", index_data, offset)[0]
                        offset += 8

                    if offset + 12 > len(index_data):
                        break

                    r_file_offset, r_file_size, r_decomp_size = struct.unpack_from("<III", index_data, offset)
                    offset += 12

                    # Flag de compression (2 octets) + flags de validité (2 octets)
                    is_compressed = False
                    if offset + 2 <= len(index_data):
                        comp_flag = struct.unpack_from("<H", index_data, offset)[0]
                        is_compressed = bool(comp_flag & 0xFFFF)
                        offset += 4

                    # Filtrer les ressources nulles
                    if r_type != 0 or r_instance != 0:
                        entries.append(
                            DbpfResourceEntry(
                                key=DbpfResourceKey(type_id=r_type, group_id=r_group, instance_id=r_instance),
                                file_offset=r_file_offset,
                                file_size=r_file_size,
                                decompressed_size=r_decomp_size,
                                is_compressed=is_compressed,
                            )
                        )

        except Exception as e:
            logger.debug(f"Erreur lors du parsing de l'index DBPF sur {file_path.name}: {e}")

        return entries
