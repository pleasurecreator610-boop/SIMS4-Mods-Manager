"""
Special dependency cases registry with official creator site routing
(Deaderpool, Scumbumbo, Lumpinou, WickedWhims / Wicked.cc, Basemental, Sims 4 Studio).
"""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Any, Dict, List, Optional, Tuple

_PARENS_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_STRIP_BRACKETS_RE = re.compile(r"^[\(\[\{]+|[\)\]\}]+$")
_COMPRESS_RE = re.compile(r"[\s\-_.'’]+")
_TRAILING_VERSION_RE = re.compile(r"v?\d+(?:\.\d+)*[a-z]?$")

__all__ = [
    "SPECIAL_DEPENDENCY_CASES",
    "SPECIAL_DEPENDENCY_REMOTE_IDS",
    "OFFICIAL_FRAMEWORK_SOURCES",
    "find_special_dependency_case",
]

OFFICIAL_FRAMEWORK_SOURCES: tuple[str, ...] = (
    "deaderpool",
    "scumbumbo",
    "lumpinou",
    "wickedcc",
    "basemental",
    "sims4studio",
)

SPECIAL_DEPENDENCY_CASES: List[Dict[str, Any]] = [
    # --- 1. WickedWhims / TURBODRIVER (Official site: wicked.cc) ---
    {
        "title": "WickedWhims",
        "remote_id": "3169",
        "url": "https://wicked.cc/download/3169-wickedwhims/",
        "source": "wickedcc",
        "url_patterns": [
            "wicked.cc",
            "wickedwhims.com",
            "loverslab.com/files/file/3169",
            "turbodriver.itch.io/wickedwhims",
        ],
        "aliases": [
            "WW",
            "ww",
            "WickedWhims",
            "wickedwhims",
            "Wicked-Whims",
            "wicked-whims",
            "Wicked_Whims",
            "wicked_whims",
            "Wicked Whims",
            "wicked whims",
            "WickedWhim",
            "wickedwhim",
            "Wicked-Whim",
            "wicked-whim",
            "Wicked_Whim",
            "wicked_whim",
            "Wicked Whim",
            "wicked whim",
            "TURBODRIVER WickedWhims",
            "WikiWhem",
            "wikiwhem",
        ],
    },
    {
        "title": "WonderfulWhims",
        "remote_id": "wickedcc_wonderfulwhims",
        "url": "https://wonderfulwhims.com/download/",
        "source": "wickedcc",
        "url_patterns": [
            "wonderfulwhims.com",
            "curseforge.com/sims4/mods/wonderfulwhims",
            "modthesims.info/d/647895",
        ],
        "aliases": [
            "WonderfulWhims",
            "Wonderful Whims",
            "Wonderful-Whims",
            "Wonderful_Whims",
            "TURBODRIVER WonderfulWhims",
        ],
    },
    # --- 2. Deaderpool (Official site: deaderpool-mccc.com) ---
    {
        "title": "MC Command Center",
        "remote_id": "deaderpool_mccc",
        "url": "https://deaderpool-mccc.com/downloads.html#mccc",
        "source": "deaderpool",
        "url_patterns": [
            "deaderpool-mccc.com",
            "curseforge.com/sims4/mods/mc-command-center",
        ],
        "aliases": [
            "MCCC",
            "mccc",
            "MC Command Center",
            "MC-Command-Center",
            "MC_Command_Center",
            "Deaderpool MCCC",
            "Deaderpool MC Command Center",
            "McCmdCenter",
            "Master Controller Command Center",
        ],
    },
    {
        "title": "MC WooHoo",
        "remote_id": "deaderpool_mcwoohoo",
        "url": "https://deaderpool-mccc.com/downloads.html#mcwoohoo",
        "source": "deaderpool",
        "url_patterns": [
            "deaderpool-mccc.com/downloads.html#mcwoohoo",
        ],
        "aliases": [
            "MC WooHoo",
            "MCWooHoo",
            "MC-WooHoo",
            "MC_WooHoo",
            "Deaderpool MC WooHoo",
            "MCCC WooHoo",
        ],
    },
    # --- 3. Scumbumbo (Official site: scumbumbomods.com) ---
    {
        "title": "XML Injector",
        "remote_id": "scumbumbo_xml_injector",
        "url": "https://scumbumbomods.com/xml-injector",
        "source": "scumbumbo",
        "url_patterns": [
            "scumbumbomods.com/xml-injector",
            "scumbumbomods.com/#/xml-injector",
            "curseforge.com/sims4/mods/xml-injector",
        ],
        "aliases": [
            "XML Injector",
            "XmlInjector",
            "XML-Injector",
            "XML_Injector",
            "Scumbumbo XML Injector",
            "Scumbumbo's XML Injector",
            "XML Injector v4",
        ],
    },
    {
        "title": "Teleport Any Sim",
        "remote_id": "scumbumbo_teleport_any_sim",
        "url": "https://scumbumbomods.com/teleport-any-sim",
        "source": "scumbumbo",
        "url_patterns": [
            "scumbumbomods.com/teleport-any-sim",
            "scumbumbomods.com/#/teleport-any-sim",
        ],
        "aliases": [
            "Teleport Any Sim",
            "TeleportAnySim",
            "Scumbumbo Teleport Any Sim",
            "Andrew Teleport Any Sim",
        ],
    },
    {
        "title": "Keep Instruments in Inventory",
        "remote_id": "scumbumbo_keep_instruments",
        "url": "https://scumbumbomods.com/keep-instruments-in-inventory",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/keep-instruments-in-inventory"],
        "aliases": [
            "Keep Instruments in Inventory",
            "Scumbumbo Keep Instruments in Inventory",
        ],
    },
    {
        "title": "Don't Wash Dishes Where You Angry Poop",
        "remote_id": "scumbumbo_dont_wash_dishes",
        "url": "https://scumbumbomods.com/dont-wash-dishes-where-you-angry-poop",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/dont-wash-dishes-where-you-angry-poop"],
        "aliases": [
            "Don't Wash Dishes Where You Angry Poop",
            "Dont Wash Dishes Where You Angry Poop",
        ],
    },
    {
        "title": "Don't Prep Food Where You Angry Poop",
        "remote_id": "scumbumbo_dont_prep_food",
        "url": "https://scumbumbomods.com/dont-prep-food-where-you-angry-poop",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/dont-prep-food-where-you-angry-poop"],
        "aliases": [
            "Don't Prep Food Where You Angry Poop",
            "Dont Prep Food Where You Angry Poop",
        ],
    },
    {
        "title": "Always Keep a Doctor at the Hospital",
        "remote_id": "scumbumbo_keep_doctor",
        "url": "https://scumbumbomods.com/always-keep-a-doctor-at-the-hospital",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/always-keep-a-doctor-at-the-hospital"],
        "aliases": [
            "Always Keep a Doctor at the Hospital",
            "Scumbumbo Always Keep a Doctor at the Hospital",
        ],
    },
    {
        "title": "Packing Crates",
        "remote_id": "scumbumbo_packing_crates",
        "url": "https://scumbumbomods.com/packing-crates",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/packing-crates"],
        "aliases": [
            "Packing Crates",
            "Scumbumbo Packing Crates",
        ],
    },
    {
        "title": "Working Alarm Clocks",
        "remote_id": "scumbumbo_working_alarm_clocks",
        "url": "https://scumbumbomods.com/working-alarm-clocks",
        "source": "scumbumbo",
        "url_patterns": ["scumbumbomods.com/working-alarm-clocks"],
        "aliases": [
            "Working Alarm Clocks",
            "Scumbumbo Working Alarm Clocks",
        ],
    },
    # --- 4. Lumpinou (Official site: lumpinoumods.com) ---
    {
        "title": "Relationship & Pregnancy Overhaul",
        "remote_id": "lumpinou_rpo",
        "url": "https://www.lumpinoumods.com/woohoo-wellness-and-pregnancy-overhaul/",
        "source": "lumpinou",
        "url_patterns": [
            "lumpinoumods.com/woohoo-wellness-and-pregnancy-overhaul",
            "curseforge.com/sims4/mods/rpo-collection",
        ],
        "aliases": [
            "RPO",
            "Relationship & Pregnancy Overhaul",
            "Relationship and Pregnancy Overhaul",
            "WooHoo Wellness",
            "WooHoo Wellness & Pregnancy Overhaul",
            "Lumpinou RPO",
            "Lumpinou's RPO",
            "RPO Core Library",
        ],
    },
    {
        "title": "Mood Pack Mod",
        "remote_id": "lumpinou_mood_pack",
        "url": "https://www.lumpinoumods.com/mood-pack-mod/",
        "source": "lumpinou",
        "url_patterns": [
            "lumpinoumods.com/mood-pack-mod",
            "curseforge.com/sims4/mods/mood-pack-mod",
        ],
        "aliases": [
            "Mood Pack Mod",
            "Lumpinou Mood Pack",
            "Lumpinou's Mood Pack",
            "Lumpinou Mood Pack Mod",
            "Mood Pack",
        ],
    },
    {
        "title": "Lumpinou's Toolbox",
        "remote_id": "lumpinou_toolbox",
        "url": "https://www.lumpinoumods.com/lumpinous-toolbox/",
        "source": "lumpinou",
        "url_patterns": [
            "lumpinoumods.com/lumpinous-toolbox",
            "curseforge.com/sims4/mods/lumpinous-toolbox",
        ],
        "aliases": [
            "Lumpinou's Toolbox",
            "Lumpinou Toolbox",
            "Lumpinous Toolbox",
            "Lumpinou Library",
            "Lumpinou's Library",
        ],
    },
    {
        "title": "LGBTQIA+ Mod",
        "remote_id": "lumpinou_lgbtqia",
        "url": "https://www.lumpinoumods.com/lgbtqia-mod/",
        "source": "lumpinou",
        "url_patterns": ["lumpinoumods.com/lgbtqia-mod"],
        "aliases": [
            "LGBTQIA+ Mod",
            "LGBTQIA Mod",
            "Lumpinou LGBTQIA+ Mod",
            "Lumpinou LGBTQIA",
        ],
    },
    {
        "title": "Open Love Life",
        "remote_id": "lumpinou_open_love_life",
        "url": "https://www.lumpinoumods.com/open-love-life/",
        "source": "lumpinou",
        "url_patterns": ["lumpinoumods.com/open-love-life"],
        "aliases": [
            "Open Love Life",
            "Lumpinou Open Love Life",
        ],
    },
    {
        "title": "SimInfo Manager",
        "remote_id": "lumpinou_siminfo_manager",
        "url": "https://www.lumpinoumods.com/sim-info-manager/",
        "source": "lumpinou",
        "url_patterns": ["lumpinoumods.com/sim-info-manager"],
        "aliases": [
            "SimInfo Manager",
            "Sim Info Manager",
            "Lumpinou SimInfo Manager",
        ],
    },
    {
        "title": "Milestones Expanded",
        "remote_id": "lumpinou_milestones_expanded",
        "url": "https://www.lumpinoumods.com/milestones-expanded/",
        "source": "lumpinou",
        "url_patterns": ["lumpinoumods.com/milestones-expanded"],
        "aliases": [
            "Milestones Expanded",
            "Lumpinou Milestones Expanded",
        ],
    },
    {
        "title": "Talents & Weaknesses",
        "remote_id": "lumpinou_talents_weaknesses",
        "url": "https://www.lumpinoumods.com/talents-and-weaknesses/",
        "source": "lumpinou",
        "url_patterns": ["lumpinoumods.com/talents-and-weaknesses"],
        "aliases": [
            "Talents & Weaknesses",
            "Talents and Weaknesses",
            "Lumpinou Talents & Weaknesses",
        ],
    },
    # --- 5. Basemental (Official site: basementalcc.com) ---
    {
        "title": "Basemental Drugs",
        "remote_id": "basemental_drugs",
        "url": "https://basementalcc.com/adult_mods/basemental-drugs/",
        "source": "basemental",
        "url_patterns": ["basementalcc.com/adult_mods/basemental-drugs"],
        "aliases": [
            "Basemental Drugs",
            "Basemental Drug",
            "BDrugs",
        ],
    },
    {
        "title": "Basemental Gangs",
        "remote_id": "basemental_gangs",
        "url": "https://basementalcc.com/adult_mods/basemental-gangs/",
        "source": "basemental",
        "url_patterns": ["basementalcc.com/adult_mods/basemental-gangs"],
        "aliases": [
            "Basemental Gangs",
            "BGangs",
        ],
    },
    {
        "title": "Universal Venue List",
        "remote_id": "basemental_uvl",
        "url": "https://basementalcc.com/mods/universal-venue-list/",
        "source": "basemental",
        "url_patterns": ["basementalcc.com/mods/universal-venue-list"],
        "aliases": [
            "Universal Venue List",
            "Basemental Universal Venue List",
            "Basemental's Universal Venue List",
            "UVL",
        ],
    },
    # --- 6. Sims 4 Studio / Andrew (Official site: sims4studio.com) ---
    {
        "title": "Andrew's Pose Player",
        "remote_id": "s4s_pose_player",
        "url": "https://sims4studio.com/thread/2617/andrews-studio",
        "source": "sims4studio",
        "url_patterns": ["sims4studio.com/thread/2617/andrews-studio"],
        "aliases": [
            "Andrew's Pose Player",
            "Andrew Pose Player",
            "Pose Player",
            "PosePlayer",
        ],
    },
]

SPECIAL_DEPENDENCY_REMOTE_IDS = {case["remote_id"] for case in SPECIAL_DEPENDENCY_CASES if "remote_id" in case}

_CASE_BY_REMOTE_ID: Dict[str, Dict[str, Any]] = {}
_CASE_BY_LOWER_ALIAS: Dict[str, Dict[str, Any]] = {}
_CASE_BY_COMPRESSED_ALIAS: Dict[str, Dict[str, Any]] = {}
_SUBSTRING_ALIASES: List[Tuple[str, Dict[str, Any]]] = []
_URL_PATTERNS: List[Tuple[str, Dict[str, Any]]] = []

for _case in SPECIAL_DEPENDENCY_CASES:
    _rid = _case.get("remote_id")
    if _rid:
        _CASE_BY_REMOTE_ID[str(_rid)] = _case
    for _pat in _case.get("url_patterns", []):
        _URL_PATTERNS.append((_pat.lower(), _case))
    for _alias in _case.get("aliases", []):
        _alias_low = _alias.strip().lower()
        _alias_comp = _COMPRESS_RE.sub("", _alias_low)
        _CASE_BY_LOWER_ALIAS.setdefault(_alias_low, _case)
        if _alias_comp:
            _CASE_BY_COMPRESSED_ALIAS.setdefault(_alias_comp, _case)
            if len(_alias_comp) >= 5:
                _SUBSTRING_ALIASES.append((_alias_comp, _case))


@lru_cache(maxsize=2048)
def find_special_dependency_case(
    name: str,
    url: str = "",
    remote_id: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Recherche en O(1) (index pré-calculé + cache LRU) si un nom de mod, une URL ou un identifiant
    correspond à l'un des frameworks officiels définis dans SPECIAL_DEPENDENCY_CASES afin de router
    systématiquement la dépendance vers le site officiel de son créateur.
    """
    r_id_clean = (remote_id or "").strip()
    if r_id_clean and r_id_clean in _CASE_BY_REMOTE_ID:
        return _CASE_BY_REMOTE_ID[r_id_clean]

    url_lower = (url or "").strip().lower()
    if url_lower:
        for pat_low, case in _URL_PATTERNS:
            if pat_low in url_lower:
                return case

    if not name:
        return None

    cleaned_name = name.strip()
    without_parens = _PARENS_RE.sub("", cleaned_name).strip()
    target_candidates = [cleaned_name]
    if without_parens and without_parens != cleaned_name:
        target_candidates.append(without_parens)

    for cand in target_candidates:
        stripped_name = _STRIP_BRACKETS_RE.sub("", cand).strip()
        raw_lower = stripped_name.lower()
        if raw_lower in _CASE_BY_LOWER_ALIAS:
            return _CASE_BY_LOWER_ALIAS[raw_lower]

        compressed = _COMPRESS_RE.sub("", raw_lower)
        if compressed in _CASE_BY_COMPRESSED_ALIAS:
            return _CASE_BY_COMPRESSED_ALIAS[compressed]

        compressed_no_ver = _TRAILING_VERSION_RE.sub("", compressed)
        if compressed_no_ver in _CASE_BY_COMPRESSED_ALIAS:
            return _CASE_BY_COMPRESSED_ALIAS[compressed_no_ver]

        for alias_comp, case in _SUBSTRING_ALIASES:
            if alias_comp in compressed:
                return case

    return None
