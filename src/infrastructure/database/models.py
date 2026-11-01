"""Modèles déclaratifs SQLAlchemy 2.0 typés pour l'infrastructure de persistance."""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.crypto import decrypt_to_dict, encrypt_dict
from src.utils.mod_type_classifier import ModTypeClassifier
from src.utils.title_normalizer import TitleNormalizer

_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an|le|la|les)\s+", re.IGNORECASE)


def compute_title_fingerprint(title: Optional[str]) -> str:
    """Calcule l'empreinte canonique normalisée d'un titre de mod pour l'indexation SQLite."""
    if not title:
        return ""
    stripped = _LEADING_ARTICLE_RE.sub("", str(title).strip())
    cleaned = TitleNormalizer.clean_mod_title(stripped) or stripped
    return TitleNormalizer.canonical_fingerprint(cleaned)[:150]


class Base(DeclarativeBase):
    """Classe de base déclarative SQLAlchemy 2.0 pour l'ensemble des entités ORM."""


def _get_json_data(val: Any, default_type: type) -> Any:
    if isinstance(val, default_type):
        return default_type(val)
    try:
        return json.loads(val or ("[]" if default_type is list else "{}"))
    except (json.JSONDecodeError, TypeError):
        return default_type()


def _set_json_data(val: Any, default_type: type) -> Any:
    return default_type(val) if val is not None else default_type()


class CatalogMod(Base):
    """Représente un mod répertorié dans le catalogue distant (LoversLab, Patreon, CurseForge...)."""

    __tablename__ = "catalog_mods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    remote_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title_fingerprint: Mapped[str] = mapped_column(String(150), default="", index=True)
    author: Mapped[str] = mapped_column(String(100), default="", index=True)
    category: Mapped[str] = mapped_column(String(100), default="", index=True)
    mod_type: Mapped[str] = mapped_column(String(40), default="other", index=True)
    tags: Mapped[Any] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    page_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="")
    download_urls: Mapped[Any] = mapped_column(JSON, default=list)
    external_links: Mapped[Any] = mapped_column(JSON, default=list)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    version_str: Mapped[str] = mapped_column(String(50), default="")
    patreon_status: Mapped[str] = mapped_column(String(20), default="NONE", index=True)
    patreon_tier: Mapped[str] = mapped_column(String(100), default="")
    requirements_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements_status: Mapped[str] = mapped_column(String(50), default="NONE")
    requirements_mods_json: Mapped[Any] = mapped_column(JSON, default=list)
    requirements_overrides_json: Mapped[Any] = mapped_column(JSON, default=dict)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_source_remote", "source", "remote_id", unique=True),
        Index("idx_source_updated", "source", "updated_date"),
        Index("idx_source_title", "source", "title"),
        Index("idx_catalog_category_updated", "category", "updated_date"),
        Index("idx_catalog_title_fp", "title_fingerprint"),
        Index("idx_catalog_updated_id", "updated_date", "id"),
        Index("idx_catalog_patreon_source", "patreon_status", "source"),
        Index("idx_catalog_mod_type_updated", "mod_type", "updated_date", "id"),
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_mod_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("catalog_mods.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(50), default="manual")
    remote_id: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title_fingerprint: Mapped[str] = mapped_column(String(150), default="", index=True)
    folder_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    installed_files: Mapped[Any] = mapped_column(JSON, default=list)
    installed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)
    version_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    version_str: Mapped[str] = mapped_column(String(50), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    backup_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    catalog_mod: Mapped[Optional["CatalogMod"]] = relationship("CatalogMod", backref="installed_mod", uselist=False)

    __table_args__ = (
        Index("idx_installed_source_remote", "source", "remote_id"),
        Index("idx_installed_catalog_id", "catalog_mod_id"),
        Index("idx_installed_folder", "folder_name"),
        Index("idx_installed_enabled_folder", "is_enabled", "folder_name"),
        Index("idx_installed_title_fp", "title_fingerprint"),
    )

    def get_installed_files_list(self) -> List[str]:
        """Retourne la liste des fichiers relatifs installés."""
        return _get_json_data(self.installed_files, list)

    def set_installed_files_list(self, files: List[str]) -> None:
        """Définit la liste des fichiers relatifs installés."""
        self.installed_files = _set_json_data(files, list)


class AccountSession(Base):
    """Stocke la session de connexion et cookies pour un provider (LoversLab, Patreon, etc.)."""

    __tablename__ = "account_sessions"

    provider_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    user_display_name: Mapped[str] = mapped_column(String(100), default="")
    cookies_data: Mapped[Any] = mapped_column(JSON, default=dict)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    def get_cookies_dict(self) -> Dict[str, str]:
        """Retourne le dictionnaire des cookies avec déchiffrement AES-256-GCM ou rétrocompatibilité."""
        return decrypt_to_dict(self.cookies_data)

    def set_cookies_dict(self, cookies: Dict[str, str]) -> None:
        """Définit les cookies sous forme chiffrée au repos via AES-256-GCM."""
        self.cookies_data = encrypt_dict(cookies)


class DbpfPackageCache(Base):
    """Cache persistant SQLite des index TGI des packages DBPF (.package)."""

    __tablename__ = "dbpf_package_cache"

    file_path: Mapped[str] = mapped_column(String(500), primary_key=True)
    mtime: Mapped[float] = mapped_column(Float, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    tgi_json: Mapped[str] = mapped_column(Text, default="[]")

    def get_tgi_list(self) -> List[List[Any]]:
        """Retourne la liste des tuples [tgi_str, resource_type_name, is_stbl] désérialisés."""
        return _get_json_data(self.tgi_json, list)

    def set_tgi_list(self, entries: List[Any]) -> None:
        """Sérialise en JSON la liste des entrées TGI."""
        self.tgi_json = json.dumps(entries)


@event.listens_for(CatalogMod, "before_insert")
@event.listens_for(CatalogMod, "before_update")
def _sync_catalog_mod_fingerprint(_mapper: Any, _connection: Any, target: CatalogMod) -> None:
    """Maintient automatiquement title_fingerprint et mod_type sur CatalogMod avant insertion ou mise à jour."""
    if target.title:
        target.title_fingerprint = compute_title_fingerprint(target.title)
    target.mod_type = ModTypeClassifier.classify_mod(
        title=target.title or "",
        category=target.category or "",
        tags=target.tags,
    )


@event.listens_for(InstalledMod, "before_insert")
@event.listens_for(InstalledMod, "before_update")
def _sync_installed_mod_fingerprint(_mapper: Any, _connection: Any, target: InstalledMod) -> None:
    """Maintient automatiquement title_fingerprint sur InstalledMod avant insertion ou mise à jour."""
    if target.title:
        target.title_fingerprint = compute_title_fingerprint(target.title)
