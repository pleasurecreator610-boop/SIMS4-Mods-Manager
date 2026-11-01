"""
LumpinouProvider : Intégration officielle de lumpinoumods.com
pour la résolution et l'installation directe de RPO, Mood Pack Mod, Lumpinou's Toolbox et LGBTQIA+ Mod.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["LumpinouProvider"]


@ProviderRegistry.register_provider("lumpinou")
class LumpinouProvider(BasePortalProvider):
    """Fournisseur officiel Lumpinou (lumpinoumods.com)."""

    provider_name = "lumpinou"
    display_name = "Lumpinou Mods"
    base_url = "https://www.lumpinoumods.com"
    default_author = "Lumpinou"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "lumpinou_core",
            "name": "Core & Frameworks (Mood Pack / Toolbox)",
            "slug": "core-frameworks",
            "url": "https://www.lumpinoumods.com/lumpinous-toolbox/",
            "default_pages": 1,
        },
        {
            "id": "lumpinou_overhauls",
            "name": "Relationship & Gameplay Overhauls (RPO / LGBTQIA+)",
            "slug": "gameplay-overhauls",
            "url": "https://www.lumpinoumods.com/woohoo-wellness-and-pregnancy-overhaul/",
            "default_pages": 1,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "lumpinou_core",
            "remote_id": "lumpinou_mood_pack",
            "title": "Mood Pack Mod",
            "author": "Lumpinou",
            "version_str": "1.6",
            "page_url": "https://www.lumpinoumods.com/mood-pack-mod/",
            "description": "Bibliothèque d'états d'esprit (Moodlets) personnalisés requise par de nombreux mods de gameplay.",
            "download_urls": [
                {
                    "name": "Lumpinou_MoodPackMod.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_MoodPackMod.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Core Library", "Mood Pack", "Emotions"],
        },
        {
            "category_id": "lumpinou_core",
            "remote_id": "lumpinou_toolbox",
            "title": "Lumpinou's Toolbox",
            "author": "Lumpinou",
            "version_str": "1.17",
            "page_url": "https://www.lumpinoumods.com/lumpinous-toolbox/",
            "description": "Bibliothèque partagée requise par la collection RPO et les grands mods de Lumpinou.",
            "download_urls": [
                {
                    "name": "Lumpinou_Toolbox_Library.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_Toolbox_Library.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Core Library", "Toolbox"],
        },
        {
            "category_id": "lumpinou_overhauls",
            "remote_id": "lumpinou_rpo",
            "title": "Relationship & Pregnancy Overhaul",
            "author": "Lumpinou",
            "version_str": "2.99",
            "page_url": "https://www.lumpinoumods.com/woohoo-wellness-and-pregnancy-overhaul/",
            "description": "Refonte complète des relations, de la grossesse, de la fertilité, de l'adoption et de la fidélité (RPO / WooHoo Wellness).",
            "download_urls": [
                {
                    "name": "Lumpinou_RPO_Collection.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_RPO_Collection.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "lumpinou",
                    "remote_id": "lumpinou_toolbox",
                    "title": "Lumpinou's Toolbox",
                    "url": "https://www.lumpinoumods.com/lumpinous-toolbox/",
                },
                {
                    "source": "lumpinou",
                    "remote_id": "lumpinou_mood_pack",
                    "title": "Mood Pack Mod",
                    "url": "https://www.lumpinoumods.com/mood-pack-mod/",
                },
            ],
            "tags": ["Gameplay Overhaul", "RPO", "Relationships"],
        },
        {
            "category_id": "lumpinou_overhauls",
            "remote_id": "lumpinou_lgbtqia",
            "title": "LGBTQIA+ Mod",
            "author": "Lumpinou",
            "version_str": "2.4",
            "page_url": "https://www.lumpinoumods.com/lgbtqia-mod/",
            "description": "Système approfondi d'identité de genre, d'orientation, de coming-out et de transition.",
            "download_urls": [
                {
                    "name": "Lumpinou_LGBTQIA_Mod.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_LGBTQIA_Mod.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "lumpinou",
                    "remote_id": "lumpinou_mood_pack",
                    "title": "Mood Pack Mod",
                    "url": "https://www.lumpinoumods.com/mood-pack-mod/",
                }
            ],
            "tags": ["Gameplay", "LGBTQIA+"],
        },
        {
            "category_id": "lumpinou_overhauls",
            "remote_id": "lumpinou_open_love_life",
            "title": "Open Love Life",
            "author": "Lumpinou",
            "version_str": "1.3",
            "page_url": "https://www.lumpinoumods.com/open-love-life/",
            "description": "Relations polyamoureuses, couples ouverts et préférences d'exclusivité personnalisables.",
            "download_urls": [
                {
                    "name": "Lumpinou_OpenLoveLife.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_OpenLoveLife.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Relationships"],
        },
        {
            "category_id": "lumpinou_core",
            "remote_id": "lumpinou_siminfo_manager",
            "title": "SimInfo Manager",
            "author": "Lumpinou",
            "version_str": "1.2",
            "page_url": "https://www.lumpinoumods.com/sim-info-manager/",
            "description": "Utilitaire d'inspection et d'édition complète des informations d'un Sim.",
            "download_urls": [
                {
                    "name": "Lumpinou_SimInfoManager.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_SimInfoManager.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Utilities", "SimInfo"],
        },
        {
            "category_id": "lumpinou_overhauls",
            "remote_id": "lumpinou_milestones_expanded",
            "title": "Milestones Expanded",
            "author": "Lumpinou",
            "version_str": "1.3",
            "page_url": "https://www.lumpinoumods.com/milestones-expanded/",
            "description": "Ajoute des dizaines de nouveaux jalons de vie (Milestones) pour Grandir Ensemble.",
            "download_urls": [
                {
                    "name": "Lumpinou_MilestonesExpanded.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_MilestonesExpanded.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Milestones"],
        },
        {
            "category_id": "lumpinou_overhauls",
            "remote_id": "lumpinou_talents_weaknesses",
            "title": "Talents & Weaknesses",
            "author": "Lumpinou",
            "version_str": "1.1",
            "page_url": "https://www.lumpinoumods.com/talents-and-weaknesses/",
            "description": "Système de prédispositions naturelles et de faiblesses d'apprentissage des compétences.",
            "download_urls": [
                {
                    "name": "Lumpinou_TalentsAndWeaknesses.zip",
                    "url": "https://www.lumpinoumods.com/downloads/Lumpinou_TalentsAndWeaknesses.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Skills"],
        },
    ]
