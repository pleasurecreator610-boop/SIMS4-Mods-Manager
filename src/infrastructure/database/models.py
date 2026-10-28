"""Modèles déclaratifs SQLAlchemy pour l'infrastructure de persistance."""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship, Mapped

Base = declarative_base()


def _get_json_data(val: Any, default_type: type):
    if isinstance(val, default_type):
        return default_type(val)
    try:
        return json.loads(val or ("[]" if default_type is list else "{}"))
    except (json.JSONDecodeError, TypeError):
        return default_type()


def _set_json_data(val: Any, default_type: type):
    return default_type(val) if val is not None else default_type()


class CatalogMod(Base):
    """Représente un mod répertorié dans le catalogue distant (LoversLab, Patreon...)."""

    __tablename__ = "catalog_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)
    remote_id = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(100), index=True)
    category = Column(String(100), index=True)
    tags = Column(JSON, default=list)
    description = Column(Text, default="")
    page_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), default="")
    download_urls = Column(JSON, default=list)
    external_links = Column(JSON, default=list)
    published_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True, index=True)
    version_str = Column(String(50), default="")
    patreon_status = Column(String(20), default="NONE", index=True)
    patreon_tier = Column(String(100), default="")
    requirements_text = Column(Text, nullable=True)
    requirements_status = Column(String(50), default="NONE")
    requirements_mods_json = Column(JSON, default=list)
    requirements_overrides_json = Column(JSON, default=dict)
    last_scraped_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_source_remote", "source", "remote_id", unique=True),
        Index("idx_source_updated", "source", "updated_date"),
        Index("idx_source_title", "source", "title"),
        Index("idx_catalog_category_updated", "category", "updated_date"),
    )

    def get_tags_list(self) -> List[str]:
        """Retourne les tags sous forme de liste de chaînes."""
        return _get_json_data(self.tags, list)

    def set_tags_list(self, tags_list: List[str]) -> None:
        """Définit la liste des tags."""
        self.tags = _set_json_data(tags_list, list)

    def get_download_urls_list(self) -> List[Dict[str, Any]]:
        """Retourne la liste des URLs de téléchargement."""
        return _get_json_data(self.download_urls, list)

    def set_download_urls_list(self, urls: List[Dict[str, Any]]) -> None:
        """Définit la liste des URLs de téléchargement."""
        self.download_urls = _set_json_data(urls, list)

    def get_external_links_list(self) -> List[str]:
        """Retourne la liste des liens externes."""
        return _get_json_data(self.external_links, list)

    def set_external_links_list(self, links: List[str]) -> None:
        """Définit la liste des liens externes."""
        self.external_links = _set_json_data(links, list)

    def get_requirements_mods_list(self) -> List[Dict[str, Any]]:
        """Retourne la liste des dépendances résolues."""
        return _get_json_data(self.requirements_mods_json, list)

    def set_requirements_mods_list(self, reqs: List[Dict[str, Any]]) -> None:
        """Définit la liste des dépendances résolues."""
        self.requirements_mods_json = _set_json_data(reqs, list)

    def get_requirements_overrides(self) -> Dict[str, str]:
        """Retourne le dictionnaire des classifications manuelles de prérequis."""
        return _get_json_data(self.requirements_overrides_json, dict)

    def set_requirements_overrides(self, overrides: Dict[str, str]) -> None:
        """Définit les classifications manuelles de prérequis."""
        self.requirements_overrides_json = _set_json_data(overrides, dict)


class InstalledMod(Base):
    """Représente un mod installé localement dans le dossier Mods des Sims 4."""

    __tablename__ = "installed_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_mod_id = Column(Integer, ForeignKey("catalog_mods.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(50), default="manual")
    remote_id = Column(String(100), default="")
    title = Column(String(255), nullable=False, index=True)
    folder_name = Column(String(255), nullable=False, index=True)
    installed_files = Column(JSON, default=list)
    installed_date = Column(DateTime, default=datetime.now)
    version_date = Column(DateTime, nullable=True)
    version_str = Column(String(50), default="")
    is_enabled = Column(Boolean, default=True, index=True)
    backup_path = Column(String(500), nullable=True)

    catalog_mod: Mapped[Optional["CatalogMod"]] = relationship("CatalogMod", backref="installed_mod", uselist=False)

    __table_args__ = (
        Index("idx_installed_source_remote", "source", "remote_id"),
        Index("idx_installed_catalog_id", "catalog_mod_id"),
        Index("idx_installed_folder", "folder_name"),
        Index("idx_installed_enabled_folder", "is_enabled", "folder_name"),
    )

    def get_installed_files_list(self) -> List[str]:
        """Retourne la liste des fichiers relatifs installés."""
        return _get_json_data(self.installed_files, list)

    def set_installed_files_list(self, files: List[str]) -> None:
        """Définit la liste des fichiers relatifs installés."""
        self.installed_files = _set_json_data(files, list)


def _dpapi_encrypt(raw_bytes: bytes) -> Optional[bytes]:
    """Chiffre des octets via Windows DPAPI (CryptProtectData) lié au compte utilisateur OS courant."""
    import os

    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(raw_bytes, len(raw_bytes))
        in_blob = DATA_BLOB(len(raw_bytes), buf)
        out_blob = DATA_BLOB()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x01
        if crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)):
            try:
                return ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None
    return None


def _dpapi_decrypt(enc_bytes: bytes) -> Optional[bytes]:
    """Déchiffre des octets via Windows DPAPI (CryptUnprotectData)."""
    import os

    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(enc_bytes, len(enc_bytes))
        in_blob = DATA_BLOB(len(enc_bytes), buf)
        out_blob = DATA_BLOB()
        if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)):
            try:
                return ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None
    return None


class AccountSession(Base):
    """Stocke la session de connexion et cookies pour un provider (LoversLab, Patreon)."""

    __tablename__ = "account_sessions"

    provider_name = Column(String(50), primary_key=True)
    is_authenticated = Column(Boolean, default=False)
    user_display_name = Column(String(100), default="")
    cookies_data = Column(JSON, default=dict)
    user_agent = Column(String(255), default="")
    last_verified = Column(DateTime, default=datetime.now)

    def get_cookies_dict(self) -> Dict[str, str]:
        """Retourne le dictionnaire des cookies avec support du déchiffrement DPAPI et rétrocompatibilité."""
        val = self.cookies_data
        if isinstance(val, dict):
            return dict(val)
        if isinstance(val, str):
            import base64

            if val.startswith("dpapi:"):
                try:
                    enc_raw = base64.b64decode(val[6:])
                    dec_raw = _dpapi_decrypt(enc_raw)
                    if dec_raw is not None:
                        return json.loads(dec_raw.decode("utf-8"))
                except Exception:
                    return {}
            if val.startswith("enc:"):
                try:
                    raw = base64.b64decode(val[4:]).decode("utf-8")
                    return json.loads(raw)
                except Exception:
                    return {}
        return _get_json_data(val, dict)

    def set_cookies_dict(self, cookies: Dict[str, str]) -> None:
        """Définit les cookies sous forme chiffrée au repos (DPAPI sur Windows avec repli Base64)."""
        try:
            import base64

            serialized_bytes = json.dumps(cookies or {}).encode("utf-8")
            dpapi_blob = _dpapi_encrypt(serialized_bytes)
            if dpapi_blob is not None:
                encoded_dpapi = base64.b64encode(dpapi_blob).decode("ascii")
                self.cookies_data = f"dpapi:{encoded_dpapi}"
                return
            encoded = base64.b64encode(serialized_bytes).decode("ascii")
            self.cookies_data = f"enc:{encoded}"
        except Exception:
            self.cookies_data = _set_json_data(cookies, dict)
