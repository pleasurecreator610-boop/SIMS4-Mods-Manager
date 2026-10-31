"""
CategoryMappingService: Exhaustive taxonomy mapping across all supported Sims 4 mod platforms.
Provides unified category classifications and bidirectional lookup maps.
"""

from __future__ import annotations

from typing import Any, Dict, List


class CategoryMappingService:
    """Service centralisant la taxonomie unifiée et les correspondances de catégories inter-sites."""

    # 1. Catégories universelles normalisées
    UNIFIED_CATEGORIES: Dict[str, Dict[str, str]] = {
        "gameplay": {
            "name": "Gameplay & Core Mods",
            "icon": "⚙️",
            "description": "Systèmes de jeu, scripts, injecteurs, gameplay overrides",
        },
        "clothing": {
            "name": "Clothing & Outfits",
            "icon": "👗",
            "description": "Vêtements, tenues, tenues de nuit, chaussures",
        },
        "hair": {
            "name": "Hair & Facial Hair",
            "icon": "💇",
            "description": "Coiffures, barbes, sourcils",
        },
        "accessories": {
            "name": "Accessories & Jewelry",
            "icon": "💍",
            "description": "Bijoux, lunettes, chapeaux, sacs, gants",
        },
        "body_makeup": {
            "name": "Body, Skin & Makeup",
            "icon": "💄",
            "description": "Peaux, presets corps, yeux, maquillage, tatouages",
        },
        "build_buy": {
            "name": "Build & Buy Mode",
            "icon": "🪑",
            "description": "Meubles, décoration, objets fonctionnels, murs, sols",
        },
        "lots_housing": {
            "name": "Lots, Rooms & Housing",
            "icon": "🏡",
            "description": "Maisons, terrains communautaires, pièces aménagées",
        },
        "sims_households": {
            "name": "Sims, Pets & Households",
            "icon": "👥",
            "description": "Sims préconçus, foyers, animaux de compagnie",
        },
        "traits_careers": {
            "name": "Traits & Careers",
            "icon": "🎓",
            "description": "Traits de caractère personnalisés, carrières, aspirations",
        },
        "animations_poses": {
            "name": "Animations & Poses",
            "icon": "🎬",
            "description": "Packs de poses, animations de gameplay et WickedWhims",
        },
        "tools_utilities": {
            "name": "Programs & Utilities",
            "icon": "🛠️",
            "description": "Programmes externes, extracteurs, utilitaires de modding",
        },
        "translations": {
            "name": "Translations",
            "icon": "🌐",
            "description": "Packs de traduction multilingue de mods",
        },
        "adult_nsfw": {
            "name": "Adult & NSFW Content (+18)",
            "icon": "🔞",
            "description": "Contenus adultes explicites (WickedWhims, animations +18)",
        },
        "miscellaneous": {
            "name": "Miscellaneous",
            "icon": "📦",
            "description": "Autres créations diverses",
        },
    }

    # 2. Table de correspondance des plateformes vers la taxonomie universelle
    PROVIDER_CATEGORY_MAP: Dict[str, Dict[str, str]] = {
        # LoversLab
        "loverslab": {
            "174": "adult_nsfw",              # WickedWhims
            "201": "animations_poses",         # Animations - WickedWhims
            "215": "translations",             # Translations - WickedWhims
            "202": "animations_poses",         # Animations - Other
            "200": "gameplay",                 # Extensions
            "203": "clothing",                 # Clothing
            "204": "accessories",              # Accessories & Makeup
            "205": "body_makeup",              # Body Parts
            "206": "build_buy",                # Objects
            "404": "build_buy",                # Paintings & Posters
            "207": "lots_housing",             # Lots
            "209": "translations",             # Translations
            "210": "miscellaneous",            # Other
            "216": "miscellaneous",            # Uncategorized
        },
        # NSFWMods
        "nsfwmods": {
            "nsfwmods_287": "adult_nsfw",      # Sims Mods (NSFWMods)
            "nsfwmods_364": "adult_nsfw",      # Adult (NSFWMods)
            "nsfwmods_289": "clothing",        # Clothing
            "nsfwmods_296": "clothing",        # Shoes
            "nsfwmods_292": "accessories",     # Accessories
            "nsfwmods_288": "body_makeup",     # Body Types
            "nsfwmods_290": "hair",            # Hair
            "nsfwmods_294": "body_makeup",     # Skintones
            "nsfwmods_295": "hair",            # Facial Hair
            "nsfwmods_291": "body_makeup",     # Makeup
            "nsfwmods_293": "body_makeup",     # Eyes
        },
        # CurseForge
        "curseforge": {
            "cf_mods_gameplay": "gameplay",           # Mods - Gameplay
            "cf_mods_utilities": "tools_utilities",   # Mods - Utilities
            "cf_mods_poses": "animations_poses",      # Mods - Poses & Animations
            "cf_create_a_sim": "clothing",            # Create a Sim
            "cf_build_buy": "build_buy",              # Build / Buy
            "cf_rooms_lots": "lots_housing",          # Rooms / Lots
            "cf_sims_households": "sims_households",  # Sims / Households
            "cf_worlds": "lots_housing",              # Worlds
            "cf_translations": "translations",        # Translations
        },
        # The Sims Resource (TSR)
        "thesimsresource": {
            "tsr_mods": "gameplay",            # Mods
            "tsr_clothing": "clothing",        # Clothing
            "tsr_hair": "hair",                # Hair
            "tsr_shoes": "clothing",           # Shoes
            "tsr_accessories": "accessories",  # Accessories
            "tsr_makeup": "body_makeup",       # Makeup
            "tsr_skintones": "body_makeup",    # Skintones
            "tsr_eyecolors": "body_makeup",    # Eye Colors
            "tsr_objects": "build_buy",        # Objects
            "tsr_sets": "build_buy",           # Sets
            "tsr_lots_rooms": "lots_housing",  # Lots & Rooms
            "tsr_sims": "sims_households",     # Sims
        },
        # ModTheSims (MTS)
        "modthesims": {
            "mts_game_mods": "gameplay",              # Game Mods
            "mts_traits": "traits_careers",           # Traits
            "mts_careers": "traits_careers",          # Careers
            "mts_build_mode": "build_buy",            # Build Mode
            "mts_buy_mode": "build_buy",              # Buy Mode
            "mts_body_shop": "clothing",              # Body Shop
            "mts_lots_housing": "lots_housing",       # Lots & Housing
            "mts_sims": "sims_households",            # Sims
            "mts_pets": "sims_households",            # Pets
            "mts_programs_utilities": "tools_utilities", # Programs and Utilities
            "mts_miscellaneous": "miscellaneous",     # Miscellaneous
        },
        # SimsFinds
        "simsfinds": {
            "sfinds_hairstyles": "hair",
            "sfinds_clothing": "clothing",
            "sfinds_accessories": "accessories",
            "sfinds_shoes": "shoes",
            "sfinds_makeup": "body_makeup",
            "sfinds_skintones": "body_makeup",
            "sfinds_eyebrows": "body_makeup",
            "sfinds_objects": "build_buy",
            "sfinds_build_mode": "build_buy",
            "sfinds_mods": "gameplay",
            "sfinds_sims": "sims_households",
            "sfinds_tattoos": "body_makeup",
            "sfinds_poses": "animations_poses",
        },
        # Nexus Mods
        "nexusmods": {
            "nexus_gameplay": "gameplay",
            "nexus_utilities": "tools_utilities",
            "nexus_user_interface": "tools_utilities",
            "nexus_clothing": "clothing",
            "nexus_cas": "hair",
            "nexus_build_mode": "build_buy",
            "nexus_buy_mode": "build_buy",
            "nexus_decorations": "build_buy",
            "nexus_careers": "traits_careers",
            "nexus_miscellaneous": "miscellaneous",
        },
        # Maxis Match CC World
        "mmccworld": {
            "mmccw_clothing": "clothing",
            "mmccw_hair": "hair",
            "mmccw_accessories": "accessories",
            "mmccw_shoes": "shoes",
            "mmccw_build_buy": "build_buy",
            "mmccw_gameplay": "gameplay",
            "mmccw_poses": "animations_poses",
            "mmccw_miscellaneous": "miscellaneous",
        },
    }

    @classmethod
    def get_unified_category(cls, provider: str, native_category_id: str) -> str:
        """Résout la catégorie universelle d'un mod à partir de son provider et de son ID natif."""
        prov_map = cls.PROVIDER_CATEGORY_MAP.get(provider.lower(), {})
        return prov_map.get(str(native_category_id), "miscellaneous")

    @classmethod
    def get_unified_details(cls, unified_key: str) -> Dict[str, str]:
        """Retourne le nom et l'icône de la catégorie universelle."""
        return cls.UNIFIED_CATEGORIES.get(
            unified_key,
            {"name": "Miscellaneous", "icon": "📦", "description": "Catégorie non classifiée"},
        )

    @classmethod
    def list_all_unified(cls) -> List[Dict[str, Any]]:
        """Liste exhaustive des catégories unifiées pour les menus de filtre."""
        return [
            {"id": key, **info}
            for key, info in cls.UNIFIED_CATEGORIES.items()
        ]
