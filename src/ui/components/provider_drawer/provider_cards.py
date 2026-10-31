"""
Provider status cards for ProviderDrawer (multi-provider detailed scraper cards and Patreon status card).
Re-exports specialized cards to maintain backwards compatibility.
"""

from src.ui.components.provider_drawer.loverslab_card import (
    ProviderScraperDrawerCard,
    LoversLabDrawerCard,
    LOVERSLAB_SUBCATS,
    NSFWMODS_SUBCATS,
    CURSEFORGE_SUBCATS,
    TSR_SUBCATS,
    MODTHESIMS_SUBCATS,
    SIMSFINDS_SUBCATS,
    NEXUSMODS_SUBCATS,
    MMCCWORLD_SUBCATS,
)
from src.ui.components.provider_drawer.patreon_card import PatreonDrawerCard

__all__ = [
    "ProviderScraperDrawerCard",
    "LoversLabDrawerCard",
    "PatreonDrawerCard",
    "LOVERSLAB_SUBCATS",
    "NSFWMODS_SUBCATS",
    "CURSEFORGE_SUBCATS",
    "TSR_SUBCATS",
    "MODTHESIMS_SUBCATS",
    "SIMSFINDS_SUBCATS",
    "NEXUSMODS_SUBCATS",
    "MMCCWORLD_SUBCATS",
]
