"""
BasementalProvider : Intégration officielle de basementalcc.com
pour l'installation directe de Basemental Drugs, Basemental Gangs et Universal Venue List (UVL).
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["BasementalProvider"]


@ProviderRegistry.register_provider("basemental")
class BasementalProvider(BasePortalProvider):
    """Fournisseur officiel Basemental (basementalcc.com)."""

    provider_name = "basemental"
    display_name = "Basemental CC"
    base_url = "https://basementalcc.com"
    default_author = "Basemental"
    is_adult_provider = True
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "basemental_adult",
            "name": "Basemental Drugs & Gangs (+18)",
            "slug": "adult-mods",
            "url": "https://basementalcc.com/adult_mods/",
            "default_pages": 1,
        },
        {
            "id": "basemental_utilities",
            "name": "Universal Venue List & Addons",
            "slug": "utilities",
            "url": "https://basementalcc.com/mods/",
            "default_pages": 1,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "basemental_adult",
            "remote_id": "basemental_drugs",
            "title": "Basemental Drugs",
            "author": "Basemental",
            "version_str": "7.18.172",
            "page_url": "https://basementalcc.com/adult_mods/basemental-drugs/",
            "description": "Système complet de substances, d'effets réalistes, de fêtes et de réhabilitation pour Les Sims 4.",
            "download_urls": [
                {
                    "name": "Basemental_Drugs_Latest.zip",
                    "url": "https://basementalcc.com/downloads/Basemental_Drugs_Latest.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "basemental",
                    "remote_id": "basemental_uvl",
                    "title": "Universal Venue List",
                    "url": "https://basementalcc.com/mods/universal-venue-list/",
                }
            ],
            "tags": ["Adult +18", "Gameplay", "Basemental"],
        },
        {
            "category_id": "basemental_adult",
            "remote_id": "basemental_gangs",
            "title": "Basemental Gangs",
            "author": "Basemental",
            "version_str": "4.2.69",
            "page_url": "https://basementalcc.com/adult_mods/basemental-gangs/",
            "description": "Gestion de gangs, quartiers généraux, territoires et rivalités criminelles dans Les Sims 4.",
            "download_urls": [
                {
                    "name": "Basemental_Gangs_Latest.zip",
                    "url": "https://basementalcc.com/downloads/Basemental_Gangs_Latest.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "basemental",
                    "remote_id": "basemental_uvl",
                    "title": "Universal Venue List",
                    "url": "https://basementalcc.com/mods/universal-venue-list/",
                }
            ],
            "tags": ["Adult +18", "Gameplay", "Basemental"],
        },
        {
            "category_id": "basemental_utilities",
            "remote_id": "basemental_uvl",
            "title": "Universal Venue List",
            "author": "Basemental",
            "version_str": "2.35",
            "page_url": "https://basementalcc.com/mods/universal-venue-list/",
            "description": "Liste universelle de types de terrains partagée entre les mods de gameplay (Basemental, LittleMsSam, ChippedSim, etc.).",
            "download_urls": [
                {
                    "name": "Basemental_UniversalVenueList.zip",
                    "url": "https://basementalcc.com/downloads/Basemental_UniversalVenueList.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Core Library", "Venues", "UVL"],
        },
    ]
