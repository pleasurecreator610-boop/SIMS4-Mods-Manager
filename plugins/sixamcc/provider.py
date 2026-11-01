"""
SixamCcProvider : Intégration officielle du portail sixam.cc
pour les packs de mobilier, décoration et construction Maxis Match.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["SixamCcProvider"]


@ProviderRegistry.register_provider("sixamcc")
class SixamCcProvider(BasePortalProvider):
    """Fournisseur officiel pour Sixam CC (sixam.cc)."""

    provider_name = "sixamcc"
    display_name = "Sixam CC"
    base_url = "https://sixam.cc"
    default_author = "SixamCC"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "sixam_furniture_packs",
            "name": "Furniture & Room Packs (Sixam CC)",
            "slug": "furniture-packs",
            "url": "https://sixam.cc/category/sims-4-cc/",
            "default_pages": 2,
        },
        {
            "id": "sixam_build_decor",
            "name": "Build Mode & Clutter (Sixam CC)",
            "slug": "build-decor",
            "url": "https://sixam.cc/category/build-mode/",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "sixam_furniture_packs",
            "remote_id": "sixamcc_stylish_wood_bedroom",
            "title": "Stylish Wood Bedroom CC Pack",
            "author": "SixamCC",
            "version_str": "1.1",
            "page_url": "https://sixam.cc/stylish-wood-bedroom-cc-pack-for-the-sims-4/",
            "description": "Ensemble complet de chambre moderne en bois chaleureux Maxis Match (28 objets).",
            "download_urls": [
                {
                    "name": "SixamCC_StylishWoodBedroom.zip",
                    "url": "https://sixam.cc/downloads/SixamCC_StylishWoodBedroom.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Build / Buy", "Bedroom", "SixamCC"],
        },
        {
            "category_id": "sixam_build_decor",
            "remote_id": "sixamcc_cozy_kitchen_clutter",
            "title": "Cozy Kitchen Appliances & Clutter Pack",
            "author": "SixamCC",
            "version_str": "1.0",
            "page_url": "https://sixam.cc/cozy-kitchen-appliances-clutter-pack/",
            "description": "Appareils électroménagers fonctionnels et décoration de cuisine Maxis Match.",
            "download_urls": [
                {
                    "name": "SixamCC_CozyKitchenClutter.zip",
                    "url": "https://sixam.cc/downloads/SixamCC_CozyKitchenClutter.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Build / Buy", "Kitchen", "SixamCC"],
        },
    ]
