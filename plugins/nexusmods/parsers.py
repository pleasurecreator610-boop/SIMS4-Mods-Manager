"""
Parsers pour Nexus Mods (nexusmods.com/thesims4).
Extrait et normalise les métadonnées de mods, prérequis (MOD vs COMMENT), et fichiers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from bs4 import BeautifulSoup

from src.domain.models.category_mapping import CategoryMappingService


def extract_nexusmods_requirements(mod_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait et catégorise strictement les prérequis d'un mod Nexus Mods :
    - 'MOD' : composant binaire ou mod tiers requis (ex: WickedWhims, XML Injector).
    - 'COMMENT' : consignes de l'auteur, avertissements de patch, instructions d'installation.
    """
    requirements: List[Dict[str, Any]] = []
    if not mod_data:
        return requirements

    reqs_block = mod_data.get("modRequirements") or {}

    # 1. Nexus Requirements internes
    nexus_reqs = reqs_block.get("nexusRequirements") or {}
    nexus_nodes = nexus_reqs.get("nodes", []) if isinstance(nexus_reqs, dict) else []
    for req in nexus_nodes:
        mod_name = (req.get("modName") or "").strip()
        url = req.get("url") or ""
        notes = (req.get("notes") or "").strip()

        if mod_name:
            requirements.append({
                "name": mod_name,
                "type": "MOD",
                "resolved": False,
                "url": url,
            })

        if notes:
            requirements.append({
                "name": notes,
                "type": "COMMENT",
                "resolved": False,
            })

    # 2. External Requirements
    ext_reqs = reqs_block.get("externalRequirements") or {}
    ext_nodes = ext_reqs.get("nodes", []) if isinstance(ext_reqs, dict) else []
    for req in ext_nodes:
        mod_name = (req.get("modName") or "").strip()
        url = req.get("url") or ""
        notes = (req.get("notes") or "").strip()

        if mod_name:
            requirements.append({
                "name": mod_name,
                "type": "MOD",
                "resolved": False,
                "url": url,
            })

        if notes:
            requirements.append({
                "name": notes,
                "type": "COMMENT",
                "resolved": False,
            })

    # 3. DLC Requirements
    dlc_reqs = reqs_block.get("dlcRequirements") or []
    if isinstance(dlc_reqs, list):
        for dlc in dlc_reqs:
            d_name = dlc.get("name") if isinstance(dlc, dict) else str(dlc)
            if d_name:
                requirements.append({
                    "name": f"DLC requis: {d_name}",
                    "type": "COMMENT",
                    "resolved": False,
                })

    # 4. Fallback analyse textuelle de la description si aucun prérequis formel
    desc = mod_data.get("description") or ""
    if not requirements and desc:
        soup = BeautifulSoup(desc, "html.parser")
        text = soup.get_text("\n", strip=True)
        patterns = [
            r"(?:required|requires|prérequis|nécessite)[\s:]+([^\n\r.]+)",
            r"(?:note|important|warning|attention)[\s:]+([^\n\r.]+)",
        ]
        for pat in patterns:
            for match in re.findall(pat, text, re.IGNORECASE):
                clean = match.strip()
                if len(clean) < 4:
                    continue
                is_mod = any(
                    kw in clean.lower()
                    for kw in ["injector", "xml", "whims", "mccc", "command center", "framework", "mesh", "library"]
                ) and not any(
                    kw in clean.lower()
                    for kw in ["patch", "pc", "mac", "moveobjects", "delete", "supprimer", "update"]
                )
                requirements.append({
                    "name": clean,
                    "type": "MOD" if is_mod else "COMMENT",
                    "resolved": False,
                })

    return requirements


def parse_nexusmods_graphql_mods(
    nodes: List[Dict[str, Any]],
    category: Dict[str, Any],
    source: str = "nexusmods",
) -> List[Dict[str, Any]]:
    """
    Convertit une liste de nœuds GraphQL Nexus Mods en dictionnaires normalisés.
    """
    mods: List[Dict[str, Any]] = []
    if not nodes:
        return mods

    native_cat_id = category.get("id", "nexus_miscellaneous")
    unified_cat = CategoryMappingService.get_unified_category(source, native_cat_id)

    for node in nodes:
        mod_id = node.get("modId")
        if not mod_id:
            continue

        name = node.get("name") or f"Nexus Mod #{mod_id}"
        summary = node.get("summary") or ""
        author = node.get("author") or "Nexus Mods Creator"
        picture_url = node.get("pictureUrl") or node.get("thumbnailUrl") or ""
        version = node.get("version") or "1.0"
        page_url = f"https://www.nexusmods.com/thesims4/mods/{mod_id}"

        reqs = extract_nexusmods_requirements(node)

        mods.append({
            "remote_id": f"nexusmods_{mod_id}",
            "title": name,
            "description": summary,
            "page_url": page_url,
            "author": author,
            "version": version,
            "category": unified_cat,
            "native_category_id": native_cat_id,
            "thumbnail_url": picture_url,
            "source": source,
            "downloads_count": node.get("downloads", 0),
            "likes_count": node.get("endorsements", 0),
            "requirements": reqs,
            "tags": ["nexusmods", category.get("slug", "ts4")],
        })

    return mods
