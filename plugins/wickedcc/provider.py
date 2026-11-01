"""
WickedCcProvider : Intégration du site officiel wicked.cc / wickedwhims.com (TURBODRIVER)
pour l'installation directe de WickedWhims (sans compte LoversLab requis), WonderfulWhims
et le répertoire officiel d'animations et d'extensions.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["WickedCcProvider"]


@ProviderRegistry.register_provider("wickedcc")
class WickedCcProvider(BasePortalProvider):
    """Fournisseur officiel Wicked.cc / TURBODRIVER (WickedWhims & Animations)."""

    provider_name = "wickedcc"
    display_name = "Wicked.cc (Official WW)"
    base_url = "https://wicked.cc"
    default_author = "TURBODRIVER"
    is_adult_provider = True
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "wickedcc_core",
            "name": "WickedWhims & WonderfulWhims (Core)",
            "slug": "core",
            "url": "https://wicked.cc/download/",
            "default_pages": 1,
        },
        {
            "id": "wickedcc_animations",
            "name": "Official Animation Creators (Wicked.cc)",
            "slug": "animations",
            "url": "https://wicked.cc/mods/animations/",
            "default_pages": 1,
        },
        {
            "id": "wickedcc_body_skins",
            "name": "Skins, Anatomy & Addons (Wicked.cc)",
            "slug": "skins-addons",
            "url": "https://wicked.cc/mods/skins/",
            "default_pages": 1,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "wickedcc_core",
            "remote_id": "3169",
            "title": "WickedWhims",
            "author": "TURBODRIVER",
            "version_str": "v184",
            "page_url": "https://wicked.cc/download/3169-wickedwhims/",
            "description": "Version communautaire officielle de WickedWhims par TURBODRIVER (téléchargement direct depuis wicked.cc sans compte requis).",
            "download_urls": [
                {
                    "name": "WickedWhims_Official_Community.zip",
                    "url": "https://wicked.cc/files/WickedWhims_Official_Community.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Adult +18", "Core Framework", "WickedWhims"],
        },
        {
            "category_id": "wickedcc_core",
            "remote_id": "wickedcc_wonderfulwhims",
            "title": "WonderfulWhims",
            "author": "TURBODRIVER",
            "version_str": "v54",
            "page_url": "https://wonderfulwhims.com/download/",
            "description": "Système d'attraction, d'archétypes de personnalité, de cycle menstruel et de relations par TURBODRIVER.",
            "download_urls": [
                {
                    "name": "WonderfulWhims_Official.zip",
                    "url": "https://wonderfulwhims.com/files/WonderfulWhims_Official.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Relationships", "WonderfulWhims"],
        },
        {
            "category_id": "wickedcc_animations",
            "remote_id": "wickedcc_ooblivion_pack",
            "title": "OOblivion Official WW Animations Pack",
            "author": "OOblivion",
            "version_str": "2026.1",
            "page_url": "https://wicked.cc/mods/animations/ooblivion-pack/",
            "description": "Pack d'animations officielles répertorié sur le portail Wicked.cc.",
            "download_urls": [
                {
                    "name": "OOblivion_WW_Animations.zip",
                    "url": "https://wicked.cc/files/OOblivion_WW_Animations.zip",
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
            "tags": ["Animations", "WickedWhims"],
        },
        {
            "category_id": "wickedcc_body_skins",
            "remote_id": "wickedcc_default_anatomy",
            "title": "WickedWhims HD Anatomy & Rig Pack",
            "author": "TURBODRIVER",
            "version_str": "2.0",
            "page_url": "https://wicked.cc/mods/skins/hd-anatomy-pack/",
            "description": "Textures et rigs anatomiques HD officiels compatibles WickedWhims.",
            "download_urls": [
                {
                    "name": "WW_HD_Anatomy_Pack.zip",
                    "url": "https://wicked.cc/files/WW_HD_Anatomy_Pack.zip",
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
            "tags": ["Body Parts", "WickedWhims"],
        },
    ]
