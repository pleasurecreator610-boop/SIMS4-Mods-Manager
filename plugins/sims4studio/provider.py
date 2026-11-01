"""
Sims4StudioProvider : Intégration de sims4studio.com (Creator Studios & Andrew's Studio)
pour la résolution d'Andrew's Pose Player, des packs de poses et des créations communautaires.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["Sims4StudioProvider"]


@ProviderRegistry.register_provider("sims4studio")
class Sims4StudioProvider(BasePortalProvider):
    """Fournisseur officiel pour Sims 4 Studio (Creator Studios & Andrew's Studio)."""

    provider_name = "sims4studio"
    display_name = "Sims 4 Studio"
    base_url = "https://sims4studio.com"
    login_url = "https://sims4studio.com/login"
    default_author = "Andrew / S4S Creator"
    is_adult_provider = False
    requires_account_card = True
    supports_comments = True

    CATEGORIES = [
        {
            "id": "s4s_andrews_studio",
            "name": "Andrew's Studio & Core Tools (Pose Player)",
            "slug": "andrews-studio",
            "url": "https://sims4studio.com/thread/2617/andrews-studio",
            "default_pages": 1,
        },
        {
            "id": "s4s_creator_studios",
            "name": "Creator Studios & Custom Content (S4S)",
            "slug": "creator-studios",
            "url": "https://sims4studio.com/board/23/creator-studios",
            "default_pages": 3,
        },
        {
            "id": "s4s_poses_animations",
            "name": "Poses & Animations Packs (S4S)",
            "slug": "poses-animations",
            "url": "https://sims4studio.com/board/26/animations-poses",
            "default_pages": 2,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "s4s_andrews_studio",
            "remote_id": "s4s_pose_player",
            "title": "Andrew's Pose Player",
            "author": "Andrew",
            "version_str": "1.8",
            "page_url": "https://sims4studio.com/thread/2617/andrews-studio",
            "description": "Mod fondamental d'exécution de poses et d'animations personnalisées dans Les Sims 4.",
            "download_urls": [
                {
                    "name": "Andrew_PosePlayer.zip",
                    "url": "https://sims4studio.com/files/Andrew_PosePlayer.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "scumbumbo",
                    "remote_id": "scumbumbo_teleport_any_sim",
                    "title": "Teleport Any Sim",
                    "url": "https://scumbumbomods.com/teleport-any-sim",
                }
            ],
            "tags": ["Poses", "Core Utility", "Sims 4 Studio"],
        },
        {
            "category_id": "s4s_poses_animations",
            "remote_id": "s4s_family_portrait_poses",
            "title": "Family & Couple Portrait Pose Pack",
            "author": "S4SPoseArtist",
            "version_str": "1.2",
            "page_url": "https://sims4studio.com/thread/15001/family-couple-portrait-poses",
            "description": "Pack de 15 poses familiales et de couple pour Andrew's Pose Player.",
            "download_urls": [
                {
                    "name": "S4S_FamilyPortraitPoses.zip",
                    "url": "https://sims4studio.com/files/S4S_FamilyPortraitPoses.zip",
                }
            ],
            "requirements_mods": [
                {
                    "source": "sims4studio",
                    "remote_id": "s4s_pose_player",
                    "title": "Andrew's Pose Player",
                    "url": "https://sims4studio.com/thread/2617/andrews-studio",
                },
                {
                    "source": "scumbumbo",
                    "remote_id": "scumbumbo_teleport_any_sim",
                    "title": "Teleport Any Sim",
                    "url": "https://scumbumbomods.com/teleport-any-sim",
                },
            ],
            "tags": ["Poses", "Sims 4 Studio"],
        },
    ]
