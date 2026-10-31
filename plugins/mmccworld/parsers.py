"""
Parsers pour Maxis Match CC World (maxismatchccworld.tumblr.com).
Extrait et normalise les créations de contenu, liens de redirection (SFS, Patreon)
et sépare strictement les dépendances (MOD vs COMMENT).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from src.domain.models.category_mapping import CategoryMappingService


def extract_post_id(url: str) -> Optional[str]:
    """Extrait l'ID numérique d'un billet Tumblr depuis son URL."""
    if not url:
        return None
    m = re.search(r"/post/(\d+)", url)
    if m:
        return m.group(1)
    return None


def extract_mmccworld_requirements(html_or_text: str) -> List[Dict[str, Any]]:
    """
    Analyse le contenu d'un post Maxis Match CC World et sépare strictement :
    - 'MOD' : mesh 3D requis, composant binaire ou framework indispensable.
    - 'COMMENT' : consignes de placement, notes d'auteur, compatibilité de jeu à épurer.
    """
    requirements: List[Dict[str, Any]] = []
    if not html_or_text:
        return requirements

    soup = BeautifulSoup(html_or_text, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Patterns de prérequis ou consignes
    patterns = [
        r"(?:requires|required|mesh required|needed mesh|prérequis)[\s:]+([^\n\r]+?)(?:\.\s|\n|\r|$)",
        r"(?:note|important|attention|cheat)[\s:]+([^\n\r]+?)(?:\.\s|\n|\r|$)",
        r"(?:compatible|compatibility)[\s:]+([^\n\r]+?)(?:\.\s|\n|\r|$)",
    ]

    for pat in patterns:
        for match in re.findall(pat, text, re.IGNORECASE):
            clean = match.strip()
            if len(clean) < 4:
                continue

            # Classifier entre MOD et COMMENT
            is_mod = any(
                kw in clean.lower()
                for kw in ["mesh", "injector", "xml", "framework", "library", "rig", "slider", "base mesh"]
            ) and not any(
                kw in clean.lower()
                for kw in [
                    "base game",
                    "moveobjects",
                    "laptop mode",
                    "delete",
                    "update",
                    "pc",
                    "mac",
                    "patch",
                    "compatible",
                    "friendly",
                ]
            )

            requirements.append(
                {
                    "name": clean,
                    "type": "MOD" if is_mod else "COMMENT",
                    "resolved": False,
                }
            )

    return requirements


def extract_download_links(html_or_text: str) -> List[Dict[str, Any]]:
    """Extrait les liens cibles de téléchargement (SimFileShare, Patreon, Google Drive)."""
    links: List[Dict[str, Any]] = []
    if not html_or_text:
        return links

    soup = BeautifulSoup(html_or_text, "html.parser")
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href in seen_urls:
            continue

        label = a.get_text(strip=True) or "Download"
        h_lower = href.lower()

        if any(
            h in h_lower
            for h in ["simfileshare.net", "patreon.com", "drive.google.com", "mediafire.com", "curseforge.com"]
        ):
            seen_urls.add(href)
            source_type = "sfs" if "simfileshare" in h_lower else ("patreon" if "patreon" in h_lower else "external")
            links.append(
                {
                    "label": label,
                    "url": href,
                    "type": source_type,
                }
            )

    return links


def parse_mmccworld_rss(
    xml_content: str,
    category: Dict[str, Any],
    source: str = "mmccworld",
) -> List[Dict[str, Any]]:
    """Convertit le flux RSS officiel de Maxis Match CC World en liste de mods normalisés."""
    mods: List[Dict[str, Any]] = []
    if not xml_content:
        return mods

    soup = BeautifulSoup(xml_content, "xml")
    items = soup.find_all("item")

    native_cat_id = category.get("id", "mmccw_clothing")
    unified_cat = CategoryMappingService.get_unified_category(source, native_cat_id)

    for it in items:
        link = it.link.text.strip() if it.link else ""
        post_id = extract_post_id(link) or str(abs(hash(link)) % 10000000)
        raw_title = it.title.text.strip() if it.title else f"MMCCW Creation #{post_id}"

        # Épuration du titre pour retirer les hashtags et caractères HTML
        clean_title = re.sub(r"#\w+", "", raw_title).strip()
        clean_title = re.sub(r"\s+", " ", clean_title)
        if len(clean_title) < 3:
            clean_title = f"MMCCW Mod #{post_id}"

        desc_html = it.description.text.strip() if it.description else ""
        desc_soup = BeautifulSoup(desc_html, "html.parser")
        desc_text = desc_soup.get_text(" ", strip=True)

        # Image preview
        thumb_url = ""
        img_elem = desc_soup.find("img", src=True)
        if img_elem:
            thumb_url = img_elem["src"]

        # Extraction des créateurs et liens
        author = "Maxis Match Creator"
        author_link = desc_soup.select_one("a.tumblr_blog")
        if author_link:
            author = author_link.get_text(strip=True)

        reqs = extract_mmccworld_requirements(desc_html)
        dl_links = extract_download_links(desc_html)

        mods.append(
            {
                "remote_id": f"mmccworld_{post_id}",
                "title": clean_title,
                "description": desc_text[:400],
                "page_url": link,
                "author": author,
                "category": unified_cat,
                "native_category_id": native_cat_id,
                "thumbnail_url": thumb_url,
                "source": source,
                "requirements": reqs,
                "download_urls": dl_links,
                "tags": ["mmccworld", "tumblr", "maxis-match"],
            }
        )

    return mods
