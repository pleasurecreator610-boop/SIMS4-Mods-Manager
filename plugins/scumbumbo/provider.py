"""
ScumbumboProvider : Intégration officielle du portail mémorial scumbumbomods.com
pour la résolution et l'installation directe de XML Injector, Teleport Any Sim et tous les mods de Scumbumbo.
"""

from __future__ import annotations

from src.providers.common.portal_base import BasePortalProvider
from src.providers.registry import ProviderRegistry

__all__ = ["ScumbumboProvider"]


@ProviderRegistry.register_provider("scumbumbo")
class ScumbumboProvider(BasePortalProvider):
    """Fournisseur officiel Scumbumbo (scumbumbomods.com)."""

    provider_name = "scumbumbo"
    display_name = "Scumbumbo Mods"
    base_url = "https://scumbumbomods.com"
    default_author = "Scumbumbo"
    is_adult_provider = False
    requires_account_card = False
    supports_comments = False

    CATEGORIES = [
        {
            "id": "scumbumbo_core",
            "name": "Core Libraries & Utilities (Scumbumbo)",
            "slug": "core-utilities",
            "url": "https://scumbumbomods.com",
            "default_pages": 1,
        },
        {
            "id": "scumbumbo_gameplay",
            "name": "Gameplay Mods (Scumbumbo)",
            "slug": "gameplay-mods",
            "url": "https://scumbumbomods.com/#/mods",
            "default_pages": 1,
        },
    ]

    REFERENCE_MODS = [
        {
            "category_id": "scumbumbo_core",
            "remote_id": "scumbumbo_xml_injector",
            "title": "XML Injector",
            "author": "Scumbumbo / Triplis",
            "version_str": "4.2",
            "page_url": "https://scumbumbomods.com/xml-injector",
            "description": "Bibliothèque d'injection de snippets XML indispensable à des centaines de mods Les Sims 4.",
            "download_urls": [
                {
                    "name": "XmlInjector_Script_v4.2.zip",
                    "url": "https://scumbumbomods.com/files/XmlInjector_Script_v4.2.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Core Library", "XML Injector", "Utilities"],
        },
        {
            "category_id": "scumbumbo_core",
            "remote_id": "scumbumbo_teleport_any_sim",
            "title": "Teleport Any Sim",
            "author": "Scumbumbo / Andrew",
            "version_str": "2.1",
            "page_url": "https://scumbumbomods.com/teleport-any-sim",
            "description": "Statue de téléportation permettant de placer n'importe quel Sim pour les poses et animations.",
            "download_urls": [
                {
                    "name": "MTS_Scumbumbo_TeleportAnySim.zip",
                    "url": "https://scumbumbomods.com/files/MTS_Scumbumbo_TeleportAnySim.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Poses", "Utilities", "Teleport Any Sim"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_keep_instruments",
            "title": "Keep Instruments in Inventory",
            "author": "Scumbumbo",
            "version_str": "1.4",
            "page_url": "https://scumbumbomods.com/keep-instruments-in-inventory",
            "description": "Empêche les Sims de poser leurs instruments de musique au sol après en avoir joué.",
            "download_urls": [
                {
                    "name": "Scumbumbo_KeepInstrumentsInInventory.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_KeepInstrumentsInInventory.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Autonomy"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_dont_wash_dishes",
            "title": "Don't Wash Dishes Where You Angry Poop",
            "author": "Scumbumbo / LeRoiDeTout",
            "version_str": "1.6",
            "page_url": "https://scumbumbomods.com/dont-wash-dishes-where-you-angry-poop",
            "description": "Permet de désactiver le lavage de la vaisselle sur les lavabos de salle de bain.",
            "download_urls": [
                {
                    "name": "Scumbumbo_DontWashDishesWhereYouAngryPoop.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_DontWashDishesWhereYouAngryPoop.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Autonomy"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_dont_prep_food",
            "title": "Don't Prep Food Where You Angry Poop",
            "author": "Scumbumbo",
            "version_str": "1.4",
            "page_url": "https://scumbumbomods.com/dont-prep-food-where-you-angry-poop",
            "description": "Permet de désactiver la préparation des repas sur les comptoirs de salle de bain.",
            "download_urls": [
                {
                    "name": "Scumbumbo_DontPrepFoodWhereYouAngryPoop.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_DontPrepFoodWhereYouAngryPoop.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Autonomy"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_keep_doctor",
            "title": "Always Keep a Doctor at the Hospital",
            "author": "Scumbumbo",
            "version_str": "1.2",
            "page_url": "https://scumbumbomods.com/always-keep-a-doctor-at-the-hospital",
            "description": "Garantit la présence permanente d'un médecin à l'hôpital dans Au Travail.",
            "download_urls": [
                {
                    "name": "Scumbumbo_AlwaysKeepADoctorAtTheHospital.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_AlwaysKeepADoctorAtTheHospital.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Gameplay", "Hospital"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_packing_crates",
            "title": "Packing Crates",
            "author": "Scumbumbo",
            "version_str": "1.3",
            "page_url": "https://scumbumbomods.com/packing-crates",
            "description": "Caisses de déménagement permettant d'emporter ses meubles et objets.",
            "download_urls": [
                {
                    "name": "Scumbumbo_PackingCrates.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_PackingCrates.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Objects", "Gameplay"],
        },
        {
            "category_id": "scumbumbo_gameplay",
            "remote_id": "scumbumbo_working_alarm_clocks",
            "title": "Working Alarm Clocks",
            "author": "Scumbumbo",
            "version_str": "1.4",
            "page_url": "https://scumbumbomods.com/working-alarm-clocks",
            "description": "Réveils fonctionnels programmables pour réveiller automatiquement vos Sims.",
            "download_urls": [
                {
                    "name": "Scumbumbo_WorkingAlarmClocks.zip",
                    "url": "https://scumbumbomods.com/files/Scumbumbo_WorkingAlarmClocks.zip",
                }
            ],
            "requirements_mods": [],
            "tags": ["Objects", "Gameplay"],
        },
    ]
