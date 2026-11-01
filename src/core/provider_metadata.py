"""Registre central immuable des métadonnées des fournisseurs de mods (Single Source of Truth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Spécification immuable d'une plateforme de mods (métadonnées Core, API et UI)."""

    name: str
    display_name: str
    filter_label: str
    filter_data: str
    is_adult: bool
    account_supported: bool
    in_catalog_filter: bool = True
    in_sync_tracker: bool = True
    badge_style: str = "background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;"
    login_url: Optional[str] = None
    aliases: Tuple[str, ...] = ()


PROVIDER_SPECS: Dict[str, ProviderSpec] = {
    "curseforge": ProviderSpec(
        name="curseforge",
        display_name="CurseForge",
        filter_label="CurseForge",
        filter_data="CurseForge",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #431407; color: #fb923c; border: 1px solid #c2410c;",
        login_url="https://www.curseforge.com/login",
    ),
    "thesimsresource": ProviderSpec(
        name="thesimsresource",
        display_name="The Sims Resource",
        filter_label="The Sims Resource",
        filter_data="The Sims Resource",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #042f2e; color: #2dd4bf; border: 1px solid #0f766e;",
        login_url="https://www.thesimsresource.com/account/login",
        aliases=("the sims resource", "tsr"),
    ),
    "modthesims": ProviderSpec(
        name="modthesims",
        display_name="ModTheSims",
        filter_label="ModTheSims",
        filter_data="ModTheSims",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7;",
        login_url="https://modthesims.info/member.php?action=login",
    ),
    "simsfinds": ProviderSpec(
        name="simsfinds",
        display_name="SimsFinds",
        filter_label="SimsFinds",
        filter_data="SimsFinds",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #1e1b4b; color: #818cf8; border: 1px solid #4f46e5;",
        login_url="https://www.simsfinds.com/en/downloads/sims4",
    ),
    "nexusmods": ProviderSpec(
        name="nexusmods",
        display_name="Nexus Mods",
        filter_label="Nexus Mods",
        filter_data="Nexus Mods",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #78350f; color: #fbbf24; border: 1px solid #d97706;",
        login_url="https://users.nexusmods.com/auth/sign_in?redirect_url=https%3A%2F%2Fwww.nexusmods.com%2Fthesims4",
        aliases=("nexus mods",),
    ),
    "mmccworld": ProviderSpec(
        name="mmccworld",
        display_name="Maxis Match CC World",
        filter_label="Maxis Match CC World",
        filter_data="Maxis Match CC World",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #14532d; color: #86efac; border: 1px solid #16a34a;",
        login_url="https://www.tumblr.com/login?redirect_to=https%3A%2F%2Fmaxismatchccworld.tumblr.com%2F",
        aliases=("maxis match cc world", "maxismatchccworld"),
    ),
    "deaderpool": ProviderSpec(
        name="deaderpool",
        display_name="Deaderpool (MCCC)",
        filter_label="Deaderpool (MCCC)",
        filter_data="deaderpool",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #1e3a8a; color: #93c5fd; border: 1px solid #2563eb;",
        aliases=("deaderpool (mccc)",),
    ),
    "scumbumbo": ProviderSpec(
        name="scumbumbo",
        display_name="Scumbumbo Mods",
        filter_label="Scumbumbo Mods",
        filter_data="scumbumbo",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669;",
        aliases=("scumbumbo mods",),
    ),
    "lumpinou": ProviderSpec(
        name="lumpinou",
        display_name="Lumpinou Mods",
        filter_label="Lumpinou Mods",
        filter_data="lumpinou",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #312e81; color: #a5b4fc; border: 1px solid #4f46e5;",
        aliases=("lumpinou mods",),
    ),
    "gamebanana": ProviderSpec(
        name="gamebanana",
        display_name="GameBanana",
        filter_label="GameBanana",
        filter_data="gamebanana",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #422006; color: #fde047; border: 1px solid #ca8a04;",
        login_url="https://gamebanana.com/members/account/login",
    ),
    "thesimscatalog": ProviderSpec(
        name="thesimscatalog",
        display_name="The Sims Catalog",
        filter_label="The Sims Catalog",
        filter_data="thesimscatalog",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #134e4a; color: #5eead4; border: 1px solid #0d9488;",
        aliases=("the sims catalog",),
    ),
    "itchio": ProviderSpec(
        name="itchio",
        display_name="Itch.io (Sims 4)",
        filter_label="Itch.io (Sims 4)",
        filter_data="itchio",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #7c2d12; color: #fdba74; border: 1px solid #ea580c;",
        login_url="https://itch.io/login",
        aliases=("itch.io (sims 4)",),
    ),
    "sims4studio": ProviderSpec(
        name="sims4studio",
        display_name="Sims 4 Studio",
        filter_label="Sims 4 Studio",
        filter_data="sims4studio",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #172554; color: #60a5fa; border: 1px solid #1d4ed8;",
        login_url="https://sims4studio.com/login",
        aliases=("sims 4 studio",),
    ),
    "littlemssam": ProviderSpec(
        name="littlemssam",
        display_name="LittleMsSam Mods",
        filter_label="LittleMsSam Mods",
        filter_data="littlemssam",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #065f46; color: #34d399; border: 1px solid #10b981;",
        aliases=("littlemssam mods",),
    ),
    "sixamcc": ProviderSpec(
        name="sixamcc",
        display_name="Sixam CC",
        filter_label="Sixam CC",
        filter_data="sixamcc",
        is_adult=False,
        account_supported=False,
        badge_style="background-color: #3f3f46; color: #e4e4e7; border: 1px solid #71717a;",
        aliases=("sixam cc",),
    ),
    "wickedcc": ProviderSpec(
        name="wickedcc",
        display_name="Wicked.cc (Official WW)",
        filter_label="Wicked.cc (Official WW)",
        filter_data="wickedcc",
        is_adult=True,
        account_supported=False,
        badge_style="background-color: #701a75; color: #f0abfc; border: 1px solid #a21caf;",
        aliases=("wicked.cc (official ww)",),
    ),
    "basemental": ProviderSpec(
        name="basemental",
        display_name="Basemental CC",
        filter_label="Basemental CC",
        filter_data="basemental",
        is_adult=True,
        account_supported=False,
        badge_style="background-color: #4c0519; color: #fda4af; border: 1px solid #be123c;",
        aliases=("basemental cc",),
    ),
    "synthira": ProviderSpec(
        name="synthira",
        display_name="Synthira",
        filter_label="Synthira",
        filter_data="synthira",
        is_adult=True,
        account_supported=True,
        badge_style="background-color: #581c87; color: #d8b4fe; border: 1px solid #7e22ce;",
        login_url="https://synthira.ru/index/1",
    ),
    "f95zone": ProviderSpec(
        name="f95zone",
        display_name="F95zone",
        filter_label="F95zone",
        filter_data="f95zone",
        is_adult=True,
        account_supported=True,
        badge_style="background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c;",
        login_url="https://f95zone.to/login/",
    ),
    "smutbase": ProviderSpec(
        name="smutbase",
        display_name="SmutBase",
        filter_label="SmutBase",
        filter_data="smutbase",
        is_adult=True,
        account_supported=False,
        badge_style="background-color: #4a044e; color: #e879f9; border: 1px solid #86198f;",
    ),
    "loverslab": ProviderSpec(
        name="loverslab",
        display_name="LoversLab",
        filter_label="LoversLab",
        filter_data="LoversLab",
        is_adult=True,
        account_supported=True,
        badge_style="background-color: #831843; color: #f472b6; border: 1px solid #9d174d;",
        login_url="https://www.loverslab.com/login/",
    ),
    "nsfwmods": ProviderSpec(
        name="nsfwmods",
        display_name="NSFWMods",
        filter_label="NSFWMods",
        filter_data="NSFWMods",
        is_adult=True,
        account_supported=True,
        badge_style="background-color: #3b0764; color: #c084fc; border: 1px solid #6b21a8;",
        login_url="https://nsfwmods.com/login/",
    ),
    "patreon": ProviderSpec(
        name="patreon",
        display_name="Patreon",
        filter_label="Patreon",
        filter_data="Patreon",
        is_adult=False,
        account_supported=True,
        badge_style="background-color: #7c2d12; color: #fb923c; border: 1px solid #9a3412;",
        login_url="https://www.patreon.com/login",
    ),
    "simfileshare": ProviderSpec(
        name="simfileshare",
        display_name="SimFileShare",
        filter_label="SimFileShare",
        filter_data="simfileshare",
        is_adult=False,
        account_supported=True,
        in_catalog_filter=False,
        in_sync_tracker=False,
        login_url="https://simfileshare.net/",
    ),
}


def get_adult_providers() -> Tuple[str, ...]:
    """Retourne le tuple ordonné des fournisseurs +18."""
    return (
        "loverslab",
        "nsfwmods",
        *(k for k, spec in PROVIDER_SPECS.items() if spec.is_adult and k not in ("loverslab", "nsfwmods")),
    )


def get_account_supported_providers() -> Tuple[str, ...]:
    """Retourne le tuple ordonné des fournisseurs supportant un compte ou une session."""
    preferred_order = (
        "loverslab",
        "nsfwmods",
        "curseforge",
        "thesimsresource",
        "modthesims",
        "simsfinds",
        "patreon",
        "nexusmods",
        "simfileshare",
        "mmccworld",
        "sims4studio",
        "f95zone",
        "itchio",
        "gamebanana",
        "synthira",
    )
    return tuple(k for k in preferred_order if k in PROVIDER_SPECS and PROVIDER_SPECS[k].account_supported)


def get_public_no_account_providers() -> Tuple[str, ...]:
    """Retourne le tuple ordonné des fournisseurs 100% publics sans compte."""
    return tuple(k for k, spec in PROVIDER_SPECS.items() if not spec.account_supported)


def build_source_mapping() -> Dict[str, str]:
    """Construit le dictionnaire de correspondance insensible à la casse pour FilterAdapter."""
    mapping: Dict[str, str] = {}
    for key, spec in PROVIDER_SPECS.items():
        if not spec.in_catalog_filter:
            continue
        mapping[key] = key
        mapping[spec.display_name.lower()] = key
        mapping[spec.filter_data.lower()] = key
        for alias in spec.aliases:
            mapping[alias.lower()] = key
    return mapping


def build_providers_login_urls() -> Dict[str, str]:
    """Construit le dictionnaire des URLs de connexion par fournisseur (et alias)."""
    urls: Dict[str, str] = {}
    for key, spec in PROVIDER_SPECS.items():
        if spec.login_url:
            urls[key] = spec.login_url
            for alias in spec.aliases:
                if " " not in alias:
                    urls[alias.lower()] = spec.login_url
    return urls


def build_initial_providers_status() -> Dict[str, str]:
    """Construit l'état initial 'OK' pour SyncTracker.providers_status."""
    return {key: "OK" for key, spec in PROVIDER_SPECS.items() if spec.in_sync_tracker}
