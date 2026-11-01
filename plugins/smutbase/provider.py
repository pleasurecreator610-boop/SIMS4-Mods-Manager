"""
SmutBaseProvider : Intégration de smutbase.com pour la résolution et le téléchargement
des meshes 3D adultes, rigs et accessoires requis par les animateurs Sims 4 / WickedWhims.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["SmutBaseProvider"]


@ProviderRegistry.register_provider("smutbase")
class SmutBaseProvider(BasePortalProvider):
    """Fournisseur officiel pour SmutBase (Meshes, Props & Rigs +18)."""

    provider_name = "smutbase"
    display_name = "SmutBase"
    base_url = "https://smutbase.com"
    default_author = "SmutBase Artist"
    is_adult_provider = True
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "smutbase_rigs_meshes",
            "name": "Body Meshes & Anatomy Rigs (SmutBase)",
            "slug": "rigs-meshes",
            "url": "https://smutbase.com/category/1/",
            "default_pages": 2,
        },
        {
            "id": "smutbase_props_furniture",
            "name": "Props & Interactive Furniture (SmutBase)",
            "slug": "props-furniture",
            "url": "https://smutbase.com/category/4/",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "smutbase_rigs_meshes",
            "remote_id": "smutbase_universal_anatomy_mesh",
            "title": "Universal High-Poly Body & Anatomy Mesh",
            "author": "SmutBaseMeshCreator",
            "version_str": "2.1",
            "page_url": "https://smutbase.com/project/30101/",
            "description": "Mesh corporel et rig anatomique universel utilisé comme prérequis par les packs d'animations.",
            "download_urls": [
                {
                    "name": "SmutBase_UniversalAnatomyMesh.zip",
                    "url": "https://smutbase.com/files/SmutBase_UniversalAnatomyMesh.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "wickedcc",
                    "remote_id": "3169",
                    "title": "WickedWhims",
                    "url": "https://wicked.cc/download/3169-wickedwhims/",
                }
            ],
            "tags": ["Adult +18", "Body Parts", "SmutBase"],
        },
        {
            "category_id": "smutbase_props_furniture",
            "remote_id": "smutbase_interactive_lounge_props",
            "title": "Interactive Lounge & Studio Props Pack",
            "author": "SmutBaseProps",
            "version_str": "1.3",
            "page_url": "https://smutbase.com/project/30102/",
            "description": "Accessoires et mobilier interactif pour scènes et animations WickedWhims.",
            "download_urls": [
                {
                    "name": "SmutBase_InteractiveLoungeProps.zip",
                    "url": "https://smutbase.com/files/SmutBase_InteractiveLoungeProps.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Adult +18", "Objects", "SmutBase"],
        },
    ]
