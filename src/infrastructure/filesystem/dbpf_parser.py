"""Parseur binaire haute performance pour les conteneurs DBPF des Sims 4 (.package).

Permet d'extraire la table d'index des ressources TGI (Type, Group, Instance 64-bit)
par projection mémoire (mmap zero-copy) sans charger les données lourdes en mémoire,
afin de détecter les collisions de tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
import mmap
from pathlib import Path
import struct
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
    """Parseur binaire zero-copy (mmap) pour conteneurs DBPF 2.0 / 2.1 (The Sims 4 .package)."""

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
        """Lit la table d'index du fichier .package via mmap et retourne toutes les clés TGI.

        Cette opération projette le fichier en lecture seule sans copie mémoire intermédiaire.
        """
        if not cls.is_dbpf(file_path):
            return []

        entries: List[DbpfResourceEntry] = []
        try:
            file_size = file_path.stat().st_size
            with open(file_path, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    if len(mm) < cls.HEADER_SIZE:
                        return []

                    magic, major, _minor = struct.unpack_from("<4sII", mm, 0)
                    if magic != cls.HEADER_MAGIC or major != 2:
                        return []

                    index_record_count = struct.unpack_from("<I", mm, 40)[0]
                    index_pos_low = struct.unpack_from("<I", mm, 44)[0]
                    index_size = struct.unpack_from("<I", mm, 48)[0]

                    # Position 64-bit de l'index dans DBPF 2.1 si spécifiée
                    index_pos_64 = struct.unpack_from("<Q", mm, 64)[0]
                    index_offset = index_pos_64 if (0 < index_pos_64 < file_size) else index_pos_low

                    if (
                        index_record_count == 0
                        or index_record_count > 500_000
                        or index_size > 50 * 1024 * 1024
                        or index_offset >= file_size
                        or index_offset <= 0
                        or (index_offset + index_size) > file_size + 1024
                    ):
                        return []

                    index_end = min(file_size, index_offset + index_size)
                    if index_end - index_offset < 4:
                        return []

                    # Format Sims 4 Index 7.x directement lu depuis la vue mmap
                    flags = struct.unpack_from("<I", mm, index_offset)[0]
                    offset = index_offset + 4

                    const_type: Optional[int] = None
                    const_group: Optional[int] = None
                    const_inst_high: Optional[int] = None

                    if flags & 0x01:
                        const_type = struct.unpack_from("<I", mm, offset)[0]
                        offset += 4
                    if flags & 0x02:
                        const_group = struct.unpack_from("<I", mm, offset)[0]
                        offset += 4
                    if flags & 0x04:
                        const_inst_high = struct.unpack_from("<I", mm, offset)[0]
                        offset += 4

                    for _ in range(index_record_count):
                        if offset >= index_end:
                            break

                        r_type = const_type if const_type is not None else struct.unpack_from("<I", mm, offset)[0]
                        if const_type is None:
                            offset += 4

                        r_group = const_group if const_group is not None else struct.unpack_from("<I", mm, offset)[0]
                        if const_group is None:
                            offset += 4

                        if const_inst_high is not None:
                            inst_low = struct.unpack_from("<I", mm, offset)[0]
                            offset += 4
                            r_instance = (const_inst_high << 32) | inst_low
                        else:
                            r_instance = struct.unpack_from("<Q", mm, offset)[0]
                            offset += 8

                        if offset + 12 > index_end:
                            break

                        r_file_offset, r_file_size, r_decomp_size = struct.unpack_from("<III", mm, offset)
                        offset += 12

                        # Flag de compression (2 octets) + flags de validité (2 octets)
                        is_compressed = False
                        if offset + 2 <= index_end:
                            comp_flag = struct.unpack_from("<H", mm, offset)[0]
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
