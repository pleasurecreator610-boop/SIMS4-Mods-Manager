"""Fournisseur NSFWMods (IPS4) pour The Sims 4."""

from __future__ import annotations

from typing import Dict

from plugins.loverslab.requirements_extractor import KNOWN_MOD_ALIASES
from src.providers.common.ips_base import BaseIPSForumProvider
from src.providers.registry import ProviderRegistry


@ProviderRegistry.register_provider("nsfwmods")
class NSFWModsProvider(BaseIPSForumProvider):
    """Fournisseur officiel pour NSFWMods The Sims 4 (catégorie 287 et ses 10 sous-catégories)."""

    provider_name = "nsfwmods"
    display_name = "NSFWMods"
    base_url = "https://nsfwmods.com"
    category_url = "https://nsfwmods.com/files/category/287-sims-mods/"
    login_url = "https://nsfwmods.com/login/"
    check_direct_redirect_in_details = False

    CATEGORIES = [
        {
            "id": "nsfwmods_287",
            "name": "Sims Mods (NSFWMods)",
            "slug": "287-sims-mods",
            "url": "https://nsfwmods.com/files/category/287-sims-mods/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_364",
            "name": "Adult (NSFWMods)",
            "slug": "364-adult",
            "url": "https://nsfwmods.com/files/category/364-adult/",
            "default_pages": 4,
        },
        {
            "id": "nsfwmods_289",
            "name": "Clothing (NSFWMods)",
            "slug": "289-clothing",
            "url": "https://nsfwmods.com/files/category/289-clothing/",
            "default_pages": 5,
        },
        {
            "id": "nsfwmods_296",
            "name": "Shoes (NSFWMods)",
            "slug": "296-shoes",
            "url": "https://nsfwmods.com/files/category/296-shoes/",
            "default_pages": 7,
        },
        {
            "id": "nsfwmods_292",
            "name": "Accessories (NSFWMods)",
            "slug": "292-accessories",
            "url": "https://nsfwmods.com/files/category/292-accessories/",
            "default_pages": 3,
        },
        {
            "id": "nsfwmods_288",
            "name": "Body Types (NSFWMods)",
            "slug": "288-body-types",
            "url": "https://nsfwmods.com/files/category/288-body-types/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_290",
            "name": "Hair (NSFWMods)",
            "slug": "290-hair",
            "url": "https://nsfwmods.com/files/category/290-hair/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_294",
            "name": "Skintones (NSFWMods)",
            "slug": "294-skintones",
            "url": "https://nsfwmods.com/files/category/294-skintones/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_295",
            "name": "Facial Hair (NSFWMods)",
            "slug": "295-facial-hair",
            "url": "https://nsfwmods.com/files/category/295-facial-hair/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_291",
            "name": "Makeup (NSFWMods)",
            "slug": "291-makeup",
            "url": "https://nsfwmods.com/files/category/291-makeup/",
            "default_pages": 1,
        },
        {
            "id": "nsfwmods_293",
            "name": "Eyes (NSFWMods)",
            "slug": "293-eyes",
            "url": "https://nsfwmods.com/files/category/293-eyes/",
            "default_pages": 1,
        },
    ]

    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = KNOWN_MOD_ALIASES
