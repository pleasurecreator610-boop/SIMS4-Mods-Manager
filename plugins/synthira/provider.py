"""
SynthiraProvider : Intégration du catalogue Sims 4 sur synthira.ru (load/stati_the_sims_4/)
incluant les mods adultes (+18), animations WickedWhims, vêtements, coiffures et objets avec miroirs directs.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["SynthiraProvider"]


@ProviderRegistry.register_provider("synthira")
class SynthiraProvider(BasePortalProvider):
    """Fournisseur officiel pour Synthira.ru (Section The Sims 4 & Adult +18)."""

    provider_name = "synthira"
    display_name = "Synthira"
    base_url = "https://synthira.ru"
    login_url = "https://synthira.ru/index/1"
    default_author = "Synthira"
    is_adult_provider = True
    requires_account_card = True
    supports_comments = True

    CATEGORIES = [
        {
            "id": "synthira_adult_mods",
            "name": "Adult Mods & Animations +18 (Synthira)",
            "slug": "adult-mods",
            "url": "https://synthira.ru/load/stati_the_sims_4/mody_18_dlja_sims_4/409",
            "default_pages": 4,
        },
        {
            "id": "synthira_gameplay_mods",
            "name": "Gameplay Mods (Synthira)",
            "slug": "gameplay-mods",
            "url": "https://synthira.ru/load/stati_the_sims_4/mody_dlja_sims_4/396",
            "default_pages": 4,
        },
        {
            "id": "synthira_clothing_cas",
            "name": "Clothing, Hair & Genetics (Synthira)",
            "slug": "clothing-cas",
            "url": "https://synthira.ru/load/stati_the_sims_4/odezhda_dlja_sims_4/397",
            "default_pages": 4,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "synthira_adult_mods",
            "remote_id": "synthira_ww_romance_animations",
            "title": "Romantic & Passionate WW Animations Bundle",
            "author": "SynthiraCurator",
            "version_str": "2026.2",
            "page_url": "https://synthira.ru/load/stati_the_sims_4/mody_18_dlja_sims_4/romantic-ww-animations/409-1-0-1501",
            "description": "Pack d'animations romantiques et adultes pour WickedWhims avec miroir direct.",
            "download_urls": [
                {
                    "name": "Synthira_RomanticWWAnimations.zip",
                    "url": "https://synthira.ru/files/Synthira_RomanticWWAnimations.zip",
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
            "tags": ["Adult +18", "Animations", "Synthira"],
        },
        {
            "category_id": "synthira_gameplay_mods",
            "remote_id": "synthira_social_events_overhaul",
            "title": "Expanded Nightlife & Social Events Overhaul",
            "author": "SynthiraModder",
            "version_str": "1.5",
            "page_url": "https://synthira.ru/load/stati_the_sims_4/mody_dlja_sims_4/nightlife-overhaul/396-1-0-1502",
            "description": "Refonte des soirées nocturnes et clubs nécessitant XML Injector et Universal Venue List.",
            "download_urls": [
                {
                    "name": "Synthira_NightlifeOverhaul.zip",
                    "url": "https://synthira.ru/files/Synthira_NightlifeOverhaul.zip",
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
            "tags": ["Gameplay", "Synthira"],
        },
    ]
