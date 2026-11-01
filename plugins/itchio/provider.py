"""
ItchIoProvider : Intégration de la catégorie Sims 4 sur Itch.io (itch.io/game-mods/tag-sims-4)
avec prise en charge des téléchargements directs et des commentaires communautaires authentifiés.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["ItchIoProvider"]


@ProviderRegistry.register_provider("itchio")
class ItchIoProvider(BasePortalProvider):
    """Fournisseur officiel pour Itch.io (Tag Sims 4 Mods & CC Packs)."""

    provider_name = "itchio"
    display_name = "Itch.io (Sims 4)"
    base_url = "https://itch.io"
    login_url = "https://itch.io/login"
    default_author = "Itch.io Creator"
    is_adult_provider = False
    requires_account_card = True
    supports_comments = True

    CATEGORIES = [
        {
            "id": "itchio_game_mods",
            "name": "Game Mods : Sims 4 (Itch.io)",
            "slug": "game-mods",
            "url": "https://itch.io/game-mods/tag-sims-4",
            "default_pages": 3,
        },
        {
            "id": "itchio_cc_packs",
            "name": "Stuff Packs & Custom Content (Itch.io)",
            "slug": "cc-packs",
            "url": "https://itch.io/game-mods/newest/tag-sims-4",
            "default_pages": 3,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "itchio_game_mods",
            "remote_id": "itchio_spinningplumbobs_werewolves",
            "title": "Expanded Occults & Lore Pack (Itch.io Release)",
            "author": "SpinningPlumbobs",
            "version_str": "3.1",
            "page_url": "https://itch.io/game-mods/sims4-expanded-occults",
            "description": "Extension majeure de gameplay surnaturel hébergée sur Itch.io.",
            "download_urls": [
                {
                    "name": "Expanded_Occults_ItchIo.zip",
                    "url": "https://itch.io/game-mods/sims4-expanded-occults/download",
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
            "tags": ["Gameplay", "Occults", "Itch.io"],
        },
        {
            "category_id": "itchio_cc_packs",
            "remote_id": "itchio_cozy_bistro_stuff_pack",
            "title": "Cozy Parisian Bistro Fan Stuff Pack",
            "author": "IndieSimStudio",
            "version_str": "1.4",
            "page_url": "https://itch.io/game-mods/cozy-parisian-bistro-pack",
            "description": "Kit d'objets communautaire Maxis Match complet (35 objets Build/Buy & CAS).",
            "download_urls": [
                {
                    "name": "CozyParisianBistro_StuffPack.zip",
                    "url": "https://itch.io/game-mods/cozy-parisian-bistro-pack/download",
                }
            ],
            "requirements_mods": [],
            "tags": ["Build / Buy", "Stuff Pack", "Itch.io"],
        },
    ]
