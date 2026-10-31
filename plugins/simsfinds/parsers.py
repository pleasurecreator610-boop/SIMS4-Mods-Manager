"""
Parsers pour SimsFinds (simsfinds.com / sims4mods.cc).
Extrait les métadonnées, images, prérequis et liens de téléchargement.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from src.domain.models.category_mapping import CategoryMappingService
from src.utils.logger import logger


def extract_item_id(url: str) -> Optional[str]:
    """Extrait l'identifiant numérique d'un mod SimsFinds depuis son URL."""
    if not url:
        return None
    m = re.search(r"/downloads/(\d+)(?:/|$)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]i(?:d)?=(\d+)", url)
    if m:
        return m.group(1)
    return None


def parse_simsfinds_browse_html(
    content: str,
    category: Dict[str, Any],
    base_url: str = "https://www.simsfinds.com",
    source: str = "simsfinds",
) -> List[Dict[str, Any]]:
    """
    Parse le contenu d'une page catalogue SimsFinds (HTML standard ou JSON AJAX carregar-downloads).
    """
    mods: List[Dict[str, Any]] = []
    if not content:
        return mods

    # Cas 1 : Réponse JSON via carregar-downloads.php
    trimmed = content.strip()
    if trimmed.startswith("{") and "items" in trimmed:
        try:
            payload = json.loads(trimmed)
            items = payload.get("items", [])
            for it in items:
                mid = str(it.get("id", ""))
                if not mid:
                    continue
                title = it.get("title") or f"SimsFinds Mod #{mid}"
                seo = it.get("seo") or "mod"
                page_url = f"{base_url}/downloads/{mid}/{seo}-sims4"

                # Image resolution
                thumb_url = ""
                raw_img = it.get("image")
                if isinstance(raw_img, str) and raw_img.startswith("{"):
                    try:
                        img_dict = json.loads(raw_img)
                        size_obj = img_dict.get("size", {})
                        rel_path = size_obj.get("gnd") or size_obj.get("big") or ""
                        if rel_path:
                            thumb_url = f"https://img.simsfinds.com.br/downloads/{rel_path}"
                    except Exception:
                        pass
                elif isinstance(raw_img, dict):
                    size_obj = raw_img.get("size", {})
                    rel_path = size_obj.get("gnd") or size_obj.get("big") or ""
                    if rel_path:
                        thumb_url = f"https://img.simsfinds.com.br/downloads/{rel_path}"

                unified_cat = CategoryMappingService.get_unified_category(source, category.get("id", ""))

                mods.append(
                    {
                        "remote_id": f"simsfinds_{mid}",
                        "title": title,
                        "description": it.get("description", ""),
                        "page_url": page_url,
                        "author": str(it.get("creator", "SimsFinds Creator")),
                        "category": unified_cat,
                        "native_category_id": category.get("id", ""),
                        "thumbnail_url": thumb_url,
                        "source": source,
                        "tags": ["simsfinds", category.get("slug", "ts4")],
                    }
                )
            return mods
        except Exception as e:
            logger.debug(f"Erreur parsing JSON SimsFinds: {e}")

    # Cas 2 : Parse HTML DOM
    soup = BeautifulSoup(content, "html.parser")
    seen_ids = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        mid = extract_item_id(href)
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)

        full_page_url = urllib.parse.urljoin(base_url, href)
        title = a.get_text(strip=True)
        if not title:
            # Look inside parent card for title
            parent = a.find_parent(["div", "article", "li"])
            if parent:
                title_elem = parent.find(["h2", "h3", "h4", "p", "strong", "span"])
                if title_elem:
                    title = title_elem.get_text(strip=True)
        if not title:
            title = f"SimsFinds Mod #{mid}"

        thumb_url = ""
        img_elem = a.find("img") or (parent.find("img") if parent else None)
        if img_elem and img_elem.get("src"):
            thumb_url = urllib.parse.urljoin(base_url, img_elem["src"])

        unified_cat = CategoryMappingService.get_unified_category(source, category.get("id", ""))

        mods.append(
            {
                "remote_id": f"simsfinds_{mid}",
                "title": title,
                "description": "",
                "page_url": full_page_url,
                "author": "SimsFinds Creator",
                "category": unified_cat,
                "native_category_id": category.get("id", ""),
                "thumbnail_url": thumb_url,
                "source": source,
                "tags": ["simsfinds", category.get("slug", "ts4")],
            }
        )

    return mods


def extract_simsfinds_requirements(html: str) -> List[Dict[str, Any]]:
    """
    Analyse le contenu HTML d'une page SimsFinds pour extraire et classifier :
    - 'MOD' : véritable prérequis ou mesh requis indispensable au fonctionnement.
    - 'COMMENT' : notes de compatibilité, patchs ou consignes d'auteurs à épurer.
    """
    requirements: List[Dict[str, Any]] = []
    if not html:
        return requirements

    soup = BeautifulSoup(html, "html.parser")
    # Conserver les retours à la ligne entre balises pour éviter la fusion de paragraphes
    text_content = soup.get_text("\n", strip=True)

    # Détection de motifs de prérequis ou consignes
    req_patterns = [
        r"(?:required|requires|prérequis|necessite|mesh required)[\s:]+([^\n\r.]+)",
        r"(?:note|important|attention)[\s:]+([^\n\r.]+)",
    ]

    for pat in req_patterns:
        matches = re.findall(pat, text_content, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            if len(clean) < 4:
                continue

            # Classifier entre MOD et COMMENT
            is_mod_requirement = any(
                kw in clean.lower()
                for kw in ["mesh", "injector", "xml", "framework", "library", "slider", "rig", "pack"]
            ) and not any(
                kw in clean.lower()
                for kw in ["patch", "pc", "mac", "moveobjects", "laptop mode", "delete", "supprimer"]
            )

            requirements.append(
                {
                    "name": clean,
                    "type": "MOD" if is_mod_requirement else "COMMENT",
                    "resolved": False,
                }
            )

    return requirements


def extract_simsfinds_download_links(
    html: str,
    base_url: str = "https://www.simsfinds.com",
) -> List[Dict[str, Any]]:
    """
    Extrait les liens de redirection ou de téléchargement depuis une page SimsFinds.
    Supporte les liens directs click.simsfinds.com/go?url= et les redirections externes.
    """
    links: List[Dict[str, Any]] = []
    if not html:
        return links

    soup = BeautifulSoup(html, "html.parser")

    # 1. Liens click.simsfinds.com/go?url=
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "click.simsfinds.com/go?url=" in href:
            target_url = href.split("go?url=", 1)[1]
            links.append(
                {
                    "url": target_url,
                    "tracking_url": href,
                    "title": a.get_text(strip=True) or "External Creator Link",
                    "is_direct": False,
                }
            )
        elif any(k in href for k in ["patreon.com", "simfileshare.net", "curseforge.com", "mediafire.com"]):
            links.append(
                {
                    "url": href,
                    "tracking_url": href,
                    "title": a.get_text(strip=True) or "Direct External Host",
                    "is_direct": True,
                }
            )

    # 2. Boutons de téléchargement avec data attributes
    for btn in soup.find_all(attrs={"data-download": True}):
        dl_target = btn.get("data-download")
        if dl_target:
            links.append(
                {
                    "url": dl_target,
                    "tracking_url": dl_target,
                    "title": "SimsFinds Direct Download",
                    "is_direct": True,
                }
            )

    return links
