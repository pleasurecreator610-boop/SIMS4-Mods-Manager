"""
GameBananaProvider : Intégration de la section The Sims 4 sur GameBanana (gamebanana.com/games/6249)
avec support du scraping HTML et de l'API JSON publique (_aRecords / _aFiles) ainsi que des commentaires authentifiés.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry
from src.utils.logger import logger

__all__ = ["GameBananaProvider"]


@ProviderRegistry.register_provider("gamebanana")
class GameBananaProvider(BasePortalProvider):
    """Fournisseur officiel pour GameBanana - The Sims 4 (Game ID 6249)."""

    provider_name = "gamebanana"
    display_name = "GameBanana"
    base_url = "https://gamebanana.com"
    login_url = "https://gamebanana.com/members/account/login"
    default_author = "GameBanana Creator"
    is_adult_provider = False
    requires_account_card = True
    supports_comments = True

    CATEGORIES = [
        {
            "id": "gb_mods_gameplay",
            "name": "Gameplay & Scripts (GameBanana)",
            "slug": "mods-gameplay",
            "url": "https://gamebanana.com/mods/games/6249",
            "default_pages": 3,
        },
        {
            "id": "gb_skins_cas",
            "name": "Skins & CAS (GameBanana)",
            "slug": "skins-cas",
            "url": "https://gamebanana.com/mods/cats/14800",
            "default_pages": 2,
        },
        {
            "id": "gb_ui_sounds",
            "name": "UI & Sounds (GameBanana)",
            "slug": "ui-sounds",
            "url": "https://gamebanana.com/sounds/games/6249",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "gb_mods_gameplay",
            "remote_id": "gamebanana_ts4_lighting_overhaul",
            "title": "TS4 Dynamic Lighting & Gameplay Overhaul",
            "author": "GBModder",
            "version_str": "2.4",
            "page_url": "https://gamebanana.com/mods/501234",
            "description": "Refonte de l'éclairage dynamique et des interactions sociales sur GameBanana Sims 4.",
            "download_urls": [
                {
                    "name": "TS4_Dynamic_Lighting_Overhaul.zip",
                    "url": "https://gamebanana.com/dl/1122334",
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
            "tags": ["Gameplay", "Lighting", "GameBanana"],
        },
        {
            "category_id": "gb_skins_cas",
            "remote_id": "gamebanana_anime_cas_pack",
            "title": "Stylized Anime & Cosplay CAS Pack",
            "author": "SimCosplay",
            "version_str": "1.2",
            "page_url": "https://gamebanana.com/mods/501235",
            "description": "Collection de tenues et coiffures stylisées pour Create-A-Sim.",
            "download_urls": [
                {
                    "name": "Stylized_CAS_Pack.zip",
                    "url": "https://gamebanana.com/dl/1122335",
                }
            ],
            "requirements_mods": [],
            "tags": ["CAS", "Clothing", "GameBanana"],
        },
    ]

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Supporte les réponses JSON API GameBanana (_aRecords) ainsi que le HTML standard."""
        if ShutdownManager.is_shutting_down():
            return [], 0

        session = SessionManager.get_http_session(self.provider_name)
        self._pace_request(session)
        cat_url = category.get("url", self.base_url)
        url = cat_url if page <= 1 else f"{cat_url.rstrip('/')}?_nPage={page}"

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and resp.text.lstrip().startswith("{"):
                data = resp.json()
                records = data.get("_aRecords", [])
                if records:
                    results: List[Dict[str, Any]] = []
                    for rec in records[:limit]:
                        rid = str(rec.get("_idRow") or f"gb_{len(results) + 1}")
                        title = str(rec.get("_sName") or f"GameBanana Mod #{rid}")
                        sub = rec.get("_aSubmitter") or {}
                        author = str(sub.get("_sName") or self.default_author)
                        p_url = str(rec.get("_sProfileUrl") or f"{self.base_url}/mods/{rid}")
                        results.append(
                            {
                                "source": self.provider_name,
                                "remote_id": f"gamebanana_{rid}" if not rid.startswith("gamebanana_") else rid,
                                "title": title,
                                "author": author,
                                "page_url": p_url,
                                "thumbnail_url": "",
                                "description": title,
                                "category": category.get("name", "GameBanana"),
                                "patreon_status": "PUBLIC",
                                "tags": [category.get("name", "GameBanana")],
                            }
                        )
                    return results, int(
                        data.get("_aMetadata", {}).get("_nTotalPages", category.get("default_pages", 1))
                    )
        except Exception as e:
            logger.debug(f"[gamebanana] Repli HTML/Référence sur {url}: {e}")

        return super().scrape_category_page(category, page=page, limit=limit)
