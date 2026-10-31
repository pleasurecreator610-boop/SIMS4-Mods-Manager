"""Modèles DTO normalisés pour les données brutes extraites par les scrapers (Domain layer)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScrapedFileDTO(BaseModel):
    """Fichier téléchargeable associé à un mod."""

    file_id: str
    file_name: str
    download_url: str
    file_size_bytes: Optional[int] = None
    upload_date: Optional[datetime] = None
    version_str: Optional[str] = None
    is_primary: bool = False


class ScrapedModDTO(BaseModel):
    """Représentation canonique et typée d'un mod scrapé depuis une plateforme externe."""

    source: str = Field(..., description="Nom du provider (curseforge, loverslab, thesimsresource, nsfwmods, patreon)")
    remote_id: str = Field(..., description="Identifiant unique distant sur la plateforme source")
    title: str = Field(..., description="Titre complet du mod")
    author: str = Field(default="Unknown", description="Nom du créateur ou auteur du mod")
    category: str = Field(default="Gameplay", description="Catégorie normalisée Sims 4")
    category_slug: Optional[str] = Field(default=None, description="Slug de la catégorie source")
    page_url: str = Field(..., description="URL de la page descriptive du mod")
    thumbnail_url: Optional[str] = Field(default=None, description="URL de la vignette ou image principale")
    summary: Optional[str] = Field(default=None, description="Courte description textuelle")
    description_html: Optional[str] = Field(default=None, description="Corps HTML ou texte complet de description")
    published_date: Optional[datetime] = Field(default=None, description="Date initiale de publication")
    updated_date: Optional[datetime] = Field(default=None, description="Date de dernière mise à jour")
    downloads_count: Optional[int] = Field(default=None, description="Nombre total de téléchargements")
    views_count: Optional[int] = Field(default=None, description="Nombre de vues")
    tags: List[str] = Field(default_factory=list, description="Liste des étiquettes associées")
    files: List[ScrapedFileDTO] = Field(default_factory=list, description="Liste des fichiers rattachés")
    external_links: Dict[str, str] = Field(
        default_factory=dict, description="Liens externes (dépendances, documentation)"
    )
    patreon_status: str = Field(default="NONE", description="Statut Patreon (NONE, LOCKED, UNLOCKED)")
    patreon_tier: Optional[str] = Field(default=None, description="Niveau d'abonnement requis")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées spécifiques au provider")

    def to_catalog_dict(self) -> Dict[str, Any]:
        """Convertit le DTO en dictionnaire compatible avec CatalogMod et upsert_mods_batch."""
        return {
            "source": self.source,
            "remote_id": self.remote_id,
            "title": self.title,
            "author": self.author,
            "category": self.category,
            "category_slug": self.category_slug,
            "page_url": self.page_url,
            "thumbnail_url": self.thumbnail_url or "",
            "summary": self.summary or "",
            "published_date": self.published_date,
            "updated_date": self.updated_date,
            "downloads_count": self.downloads_count,
            "tags": self.tags,
            "external_links": self.external_links,
            "patreon_status": self.patreon_status,
            "patreon_tier": self.patreon_tier or "",
        }
