"""
DeaderpoolOfficialProvider : Intégration officielle de deaderpool-mccc.com
pour la résolution et l'installation directe de MC Command Center (MCCC) et MC WooHoo.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["DeaderpoolProvider"]


@ProviderRegistry.register_provider("deaderpool")
class DeaderpoolProvider(BasePortalProvider):
    """Fournisseur officiel Deaderpool (MC Command Center & MC WooHoo)."""

    provider_name = "deaderpool"
    display_name = "Deaderpool (MCCC)"
    base_url = "https://deaderpool-mccc.com"
    default_author = "Deaderpool"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "dp_mccc_core",
            "name": "MC Command Center (Core)",
            "slug": "mccc-core",
            "url": "https://deaderpool-mccc.com/downloads.html",
            "default_pages": 1,
        },
        {
            "id": "dp_mc_woohoo",
            "name": "MC WooHoo (Module)",
            "slug": "mc-woohoo",
            "url": "https://deaderpool-mccc.com/downloads.html#mcwoohoo",
            "default_pages": 1,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "dp_mccc_core",
            "remote_id": "deaderpool_mccc",
            "title": "MC Command Center",
            "author": "Deaderpool",
            "version_str": "2026.2.0",
            "page_url": "https://deaderpool-mccc.com/downloads.html#mccc",
            "description": "Master Controller Command Center (MCCC) - Framework officiel de contrôle et d'histoire pour Les Sims 4.",
            "download_urls": [
                {
                    "name": "McCmdCenter_AllModules.zip",
                    "url": "https://github.com/Deaderpool/MCCC/releases/latest/download/McCmdCenter_AllModules.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Core Framework", "MCCC"],
        },
        {
            "category_id": "dp_mc_woohoo",
            "remote_id": "deaderpool_mcwoohoo",
            "title": "MC WooHoo",
            "author": "Deaderpool",
            "version_str": "2026.2.0",
            "page_url": "https://deaderpool-mccc.com/downloads.html#mcwoohoo",
            "description": "Module officiel MC WooHoo pour MC Command Center (nécessite MCCC Core).",
            "download_urls": [
                {
                    "name": "MCWoohoo_ScriptAndPackage.zip",
                    "url": "https://github.com/Deaderpool/MCCC/releases/latest/download/MCWoohoo_ScriptAndPackage.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "deaderpool",
                    "remote_id": "deaderpool_mccc",
                    "title": "MC Command Center",
                    "url": "https://deaderpool-mccc.com/downloads.html#mccc",
                }
            ],
            "tags": ["Module", "MC WooHoo", "MCCC"],
        },
    ]
