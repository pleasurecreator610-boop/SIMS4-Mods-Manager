"""Fournisseur LoversLab (IPS4) pour The Sims 4."""

from __future__ import annotations

from typing import Dict

from plugins.loverslab.requirements_extractor import KNOWN_MOD_ALIASES
from src.providers.common.ips_base import BaseIPSForumProvider
from src.providers.registry import ProviderRegistry


@ProviderRegistry.register_provider("loverslab")
class LoversLabProvider(BaseIPSForumProvider):
    """Fournisseur officiel pour LoversLab The Sims 4 (catégorie 161 et ses 14 sous-catégories)."""

    provider_name = "loverslab"
    display_name = "LoversLab"
    base_url = "https://www.loverslab.com"
    category_url = "https://www.loverslab.com/files/category/161-the-sims-4/"
    login_url = "https://www.loverslab.com/login/"
    check_direct_redirect_in_details = True

    CATEGORIES = [
        {
            "id": "174",
            "name": "WickedWhims",
            "slug": "174-wickedwhims",
            "url": "https://www.loverslab.com/files/category/174-wickedwhims/",
            "default_pages": 16,
        },
        {
            "id": "201",
            "name": "Animations - WickedWhims",
            "slug": "201-animations-wickedwhims",
            "url": "https://www.loverslab.com/files/category/201-animations-wickedwhims/",
            "default_pages": 7,
        },
        {
            "id": "215",
            "name": "Translations - WickedWhims",
            "slug": "215-translations-wickedwhims",
            "url": "https://www.loverslab.com/files/category/215-translations-wickedwhims/",
            "default_pages": 5,
        },
        {
            "id": "202",
            "name": "Animations - Other",
            "slug": "202-animations-other",
            "url": "https://www.loverslab.com/files/category/202-animations-other/",
            "default_pages": 7,
        },
        {
            "id": "200",
            "name": "Extensions",
            "slug": "200-extensions",
            "url": "https://www.loverslab.com/files/category/200-extensions/",
            "default_pages": 3,
        },
        {
            "id": "203",
            "name": "Clothing",
            "slug": "203-clothing",
            "url": "https://www.loverslab.com/files/category/203-clothing/",
            "default_pages": 128,
        },
        {
            "id": "204",
            "name": "Accessories & Makeup",
            "slug": "204-accessories-makeup",
            "url": "https://www.loverslab.com/files/category/204-accessories-makeup/",
            "default_pages": 16,
        },
        {
            "id": "205",
            "name": "Body Parts",
            "slug": "205-body-parts",
            "url": "https://www.loverslab.com/files/category/205-body-parts/",
            "default_pages": 12,
        },
        {
            "id": "206",
            "name": "Objects",
            "slug": "206-objects",
            "url": "https://www.loverslab.com/files/category/206-objects/",
            "default_pages": 86,
        },
        {
            "id": "404",
            "name": "Paintings & Posters",
            "slug": "404-paintings-posters",
            "url": "https://www.loverslab.com/files/category/404-paintings-posters/",
            "default_pages": 14,
        },
        {
            "id": "207",
            "name": "Lots",
            "slug": "207-lots",
            "url": "https://www.loverslab.com/files/category/207-lots/",
            "default_pages": 18,
        },
        {
            "id": "209",
            "name": "Translations",
            "slug": "209-translations",
            "url": "https://www.loverslab.com/files/category/209-translations/",
            "default_pages": 35,
        },
        {
            "id": "210",
            "name": "Other",
            "slug": "210-other",
            "url": "https://www.loverslab.com/files/category/210-other/",
            "default_pages": 23,
        },
        {
            "id": "216",
            "name": "Uncategorized",
            "slug": "216-uncategorized",
            "url": "https://www.loverslab.com/files/category/216-uncategorized/",
            "default_pages": 27,
        },
    ]

    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = KNOWN_MOD_ALIASES
