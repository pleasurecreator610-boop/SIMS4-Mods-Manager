"""
TheSimsCatalogProvider : Intégration de thesimscatalog.com/sims4/
pour l'indexation et le téléchargement direct de coiffures, vêtements, meubles, maisons et mods.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["TheSimsCatalogProvider"]


@ProviderRegistry.register_provider("thesimscatalog")
class TheSimsCatalogProvider(BasePortalProvider):
    """Fournisseur officiel pour The Sims Catalog (thesimscatalog.com)."""

    provider_name = "thesimscatalog"
    display_name = "The Sims Catalog"
    base_url = "https://thesimscatalog.com"
    default_author = "TheSimsCatalog"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "tsc_hairstyles",
            "name": "Hairstyles (TheSimsCatalog)",
            "slug": "hairstyles",
            "url": "https://thesimscatalog.com/sims4/category/hairstyles/",
            "default_pages": 4,
        },
        {
            "id": "tsc_clothing",
            "name": "Clothing (TheSimsCatalog)",
            "slug": "clothing",
            "url": "https://thesimscatalog.com/sims4/category/clothing/",
            "default_pages": 4,
        },
        {
            "id": "tsc_furniture",
            "name": "Furniture & Objects (TheSimsCatalog)",
            "slug": "furniture",
            "url": "https://thesimscatalog.com/sims4/category/furniture/",
            "default_pages": 3,
        },
        {
            "id": "tsc_mods",
            "name": "Game Mods (TheSimsCatalog)",
            "slug": "game-mods",
            "url": "https://thesimscatalog.com/sims4/category/game-mods/",
            "default_pages": 3,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "tsc_hairstyles",
            "remote_id": "thesimscatalog_wavy_long_hair",
            "title": "Maxis Match Wavy Long Hairstyle",
            "author": "SimCatalogCreator",
            "version_str": "1.0",
            "page_url": "https://thesimscatalog.com/sims4/downloads/hairstyles/wavy-long-hairstyle/",
            "description": "Coiffure longue ondulée Maxis Match avec 24 palettes EA.",
            "download_urls": [
                {
                    "name": "TSC_WavyLongHair.zip",
                    "url": "https://thesimscatalog.com/files/TSC_WavyLongHair.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Hairstyles", "Maxis Match"],
        },
        {
            "category_id": "tsc_mods",
            "remote_id": "thesimscatalog_career_bundle",
            "title": "Interactive Modern Careers Bundle",
            "author": "CatalogModder",
            "version_str": "2.1",
            "page_url": "https://thesimscatalog.com/sims4/downloads/game-mods/interactive-modern-careers/",
            "description": "Pack de carrières modernes interactives nécessitant XML Injector.",
            "download_urls": [
                {
                    "name": "TSC_ModernCareersBundle.zip",
                    "url": "https://thesimscatalog.com/files/TSC_ModernCareersBundle.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "scumbumbo",
                    "remote_id": "scumbumbo_xml_injector",
                    "title": "XML Injector",
                    "url": "https://scumbumbomods.com/xml-injector",
                }
            ],
            "tags": ["Gameplay", "Careers"],
        },
    ]
