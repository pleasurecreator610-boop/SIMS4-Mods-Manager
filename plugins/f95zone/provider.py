"""
F95ZoneProvider : Intégration des fils et ressources The Sims 4 sur F95zone (f95zone.to)
avec gestion d'authentification membre XenForo et publication/vérification de commentaires et MP.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["F95ZoneProvider"]


@ProviderRegistry.register_provider("f95zone")
class F95ZoneProvider(BasePortalProvider):
    """Fournisseur officiel pour F95zone (Section Mods & Collections Sims 4 +18)."""

    provider_name = "f95zone"
    display_name = "F95zone"
    base_url = "https://f95zone.to"
    login_url = "https://f95zone.to/login/"
    default_author = "F95Creator"
    is_adult_provider = True
    requires_account_card = True
    supports_comments = True

    CATEGORIES = [
        {
            "id": "f95_sims4_mods",
            "name": "Sims 4 Adult Mods & Overhauls (F95zone)",
            "slug": "sims4-mods",
            "url": "https://f95zone.to/tags/sims-4/",
            "default_pages": 2,
        },
        {
            "id": "f95_sims4_animations",
            "name": "WickedWhims Megapacks & Animations (F95zone)",
            "slug": "sims4-animations",
            "url": "https://f95zone.to/tags/wickedwhims/",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "f95_sims4_mods",
            "remote_id": "f95zone_sims4_romance_suite",
            "title": "TS4 Adult Club & Relationship Suite",
            "author": "F95SimDev",
            "version_str": "3.2",
            "page_url": "https://f95zone.to/threads/ts4-adult-club-relationship-suite.180001/",
            "description": "Extension adulte de clubs et d'interactions avancées publiée sur F95zone.",
            "download_urls": [
                {
                    "name": "F95_AdultClubSuite.zip",
                    "url": "https://f95zone.to/attachments/F95_AdultClubSuite.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "wickedcc",
                    "remote_id": "3169",
                    "title": "WickedWhims",
                    "url": "https://wicked.cc/download/3169-wickedwhims/",
                },
                {
                    "source": "deaderpool",
                    "remote_id": "deaderpool_mccc",
                    "title": "MC Command Center",
                    "url": "https://deaderpool-mccc.com/downloads.html#mccc",
                },
                {
                    "source": "lumpinou",
                    "remote_id": "lumpinou_mood_pack",
                    "title": "Mood Pack Mod",
                    "url": "https://www.lumpinoumods.com/mood-pack-mod/",
                },
            ],
            "tags": ["Adult +18", "Gameplay", "F95zone"],
        },
        {
            "category_id": "f95_sims4_animations",
            "remote_id": "f95zone_ww_studio_animations",
            "title": "F95 Curated WW Studio Animations Pack",
            "author": "F95Animator",
            "version_str": "2.0",
            "page_url": "https://f95zone.to/threads/f95-curated-ww-studio-animations.180002/",
            "description": "Pack d'animations haute précision pour WickedWhims.",
            "download_urls": [
                {
                    "name": "F95_CuratedWWAnimations.zip",
                    "url": "https://f95zone.to/attachments/F95_CuratedWWAnimations.zip",
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
            "tags": ["Adult +18", "Animations", "F95zone"],
        },
    ]
