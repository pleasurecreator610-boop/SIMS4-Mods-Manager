"""
LittleMsSamProvider : Intégration officielle du catalogue lms-mods.com
pour les +200 mods de gameplay, RSM (Random Small Mods), More Buyable Venues et SimDa Dating App.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["LittleMsSamProvider"]


@ProviderRegistry.register_provider("littlemssam")
class LittleMsSamProvider(BasePortalProvider):
    """Fournisseur officiel pour LittleMsSam's Sims 4 Mods (lms-mods.com)."""

    provider_name = "littlemssam"
    display_name = "LittleMsSam Mods"
    base_url = "https://lms-mods.com"
    default_author = "LittleMsSam"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "lms_gameplay_mods",
            "name": "Big Gameplay Mods (LMS)",
            "slug": "gameplay-mods",
            "url": "https://lms-mods.com/",
            "default_pages": 2,
        },
        {
            "id": "lms_random_small_mods",
            "name": "Random Small Mods & Fixes (LMS)",
            "slug": "random-small-mods",
            "url": "https://lms-mods.com/random-small-mods/",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "lms_gameplay_mods",
            "remote_id": "littlemssam_more_buyable_venues",
            "title": "More Buyable Venues and new Venue Types",
            "author": "LittleMsSam",
            "version_str": "2026.1",
            "page_url": "https://lms-mods.com/#more-buyable-venues",
            "description": "Permet aux Sims d'acheter des bars, boîtes de nuit, spas, cafés et nouveaux terrains personnalisés.",
            "download_urls": [
                {
                    "name": "LittleMsSam_MoreBuyableVenues.zip",
                    "url": "https://lms-mods.com/files/LittleMsSam_MoreBuyableVenues.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "scumbumbo",
                    "remote_id": "scumbumbo_xml_injector",
                    "title": "XML Injector",
                    "url": "https://scumbumbomods.com/xml-injector",
                },
                {
                    "source": "basemental",
                    "remote_id": "basemental_uvl",
                    "title": "Universal Venue List",
                    "url": "https://basementalcc.com/mods/universal-venue-list/",
                },
            ],
            "tags": ["Gameplay", "Venues", "LittleMsSam"],
        },
        {
            "category_id": "lms_gameplay_mods",
            "remote_id": "littlemssam_simda_dating_app",
            "title": "SimDa Dating App",
            "author": "LittleMsSam",
            "version_str": "2026.1",
            "page_url": "https://lms-mods.com/#simda-dating-app",
            "description": "Application de rencontres sur téléphone et ordinateur (rendez-vous spécifiques, blind dates, aventures).",
            "download_urls": [
                {
                    "name": "LittleMsSam_SimDaDatingApp.zip",
                    "url": "https://lms-mods.com/files/LittleMsSam_SimDaDatingApp.zip",
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
            "tags": ["Gameplay", "Romance", "LittleMsSam"],
        },
        {
            "category_id": "lms_random_small_mods",
            "remote_id": "littlemssam_live_in_business",
            "title": "Live in Business",
            "author": "LittleMsSam",
            "version_str": "2026.1",
            "page_url": "https://lms-mods.com/#live-in-business",
            "description": "Permet de gérer un commerce, café, bar, garderie ou pension pour animaux directement depuis son terrain résidentiel.",
            "download_urls": [
                {
                    "name": "LittleMsSam_LiveInBusiness.zip",
                    "url": "https://lms-mods.com/files/LittleMsSam_LiveInBusiness.zip",
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
            "tags": ["Gameplay", "Business", "LittleMsSam"],
        },
    ]
