"""
ModTheSims Parsers: Extraction of items, metadata, direct download files and requirements.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup


def extract_item_id(url_or_id: str, soup: Optional[BeautifulSoup] = None, html_text: str = "") -> Optional[str]:
    """Extracts numeric thread/item ID from ModTheSims URL or HTML content."""
    if not url_or_id:
        return None
    cleaned = str(url_or_id).strip()
    if cleaned.isdigit():
        return cleaned

    # 1. URL pattern: /d/701054/... or /download.php?t=701054 or /showthread.php?t=701054
    m = re.search(r"/(?:d|downloads)/(\d+)", cleaned, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"[?&]t=(\d+)", cleaned, re.IGNORECASE)
    if m:
        return m.group(1)

    # 2. HTML inspection
    if soup:
        a_tag = soup.find("a", href=re.compile(r"/download\.php\?t=(\d+)"))
        if a_tag:
            m = re.search(r"/download\.php\?t=(\d+)", a_tag["href"])
            if m:
                return m.group(1)

    if html_text:
        m = re.search(r'name="id"\s+value="(\d+)"', html_text)
        if m:
            return m.group(1)
        m = re.search(r"/metadatat/(\d+)/", html_text)
        if m:
            return m.group(1)

    return None


def parse_mts_browse_html(
    html: str,
    category: Dict[str, Any],
    base_url: str = "https://modthesims.info",
    page: int = 1,
    source: str = "modthesims",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """Parses ModTheSims category/browse page and extracts mod cards."""
    mods: List[Dict[str, Any]] = []
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select("li.smol-card-component")
    for card in cards:
        try:
            link_el = card.find("a", href=re.compile(r"/d/\d+/"))
            if not link_el:
                continue
            href = link_el["href"].strip()
            item_id = extract_item_id(href)
            if not item_id:
                continue

            full_url = urllib.parse.urljoin(base_url, href)

            # Title
            title_el = card.select_one(".downloadtitle a") or link_el
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                m_slug = re.search(r"/d/\d+/(.*)\.html", href)
                title = m_slug.group(1).replace("-", " ").title() if m_slug else f"Mod #{item_id}"

            # Image
            thumb_el = card.select_one("img.featuredimage, img.thumbimage-small, img")
            thumb_url = None
            if thumb_el:
                src = thumb_el.get("src") or thumb_el.get("data-src") or ""
                if src.startswith("//"):
                    src = f"https:{src}"
                elif src.startswith("/"):
                    src = urllib.parse.urljoin(base_url, src)
                thumb_url = src if src.startswith("http") else None

            # Author
            creator_el = card.select_one(".downloadcreatorname a, a[href*='/m/']")
            author = creator_el.get_text(strip=True) if creator_el else "ModTheSims Creator"

            # Preview / Description snippet
            desc_el = card.select_one(".downloadPreview")
            desc = desc_el.get_text(" ", strip=True) if desc_el else ""
            desc = re.sub(r"more\.\.\.$", "", desc).strip()

            # Date
            creator_p = card.select_one(".downloadcreator")
            date_str = ""
            if creator_p:
                p_text = creator_p.get_text(" ", strip=True)
                m_date = re.search(r"(\d+(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})", p_text)
                if m_date:
                    date_str = m_date.group(1)

            mods.append(
                {
                    "remote_id": item_id,
                    "title": title,
                    "author": author,
                    "version": "1.0",
                    "source": source,
                    "page_url": full_url,
                    "thumbnail_url": thumb_url,
                    "category": category.get("name", "Game Mods"),
                    "tags": ["modthesims", category.get("slug", "ts4")],
                    "short_description": desc,
                    "updated_at": date_str,
                    "is_adult": False,
                    "requires_subscription": False,
                }
            )
        except Exception:
            continue

    # Detected total pages
    detected_pages: Optional[int] = None
    page_links = soup.find_all("a", href=re.compile(r"[?&]p=(\d+)"))
    if page_links:
        max_p = 1
        for a in page_links:
            m = re.search(r"[?&]p=(\d+)", a["href"])
            if m:
                p_num = int(m.group(1))
                if p_num > max_p:
                    max_p = p_num
        detected_pages = max_p

    return mods, detected_pages


def extract_mts_download_links(soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
    """Extracts direct download file links from an MTS mod page."""
    files: List[Dict[str, Any]] = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "getfile.php" in href:
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                href = urllib.parse.urljoin("https://chii.modthesims.info", href)

            if href not in seen_urls:
                seen_urls.add(href)
                name = a.get_text(strip=True)
                if not name or name.lower() in ("download", "telecharger"):
                    m_file = re.search(r"file=(\d+)", href)
                    name = f"MTS_File_{m_file.group(1)}.zip" if m_file else "MTS_Download.zip"
                files.append(
                    {
                        "name": name,
                        "url": href,
                        "size": 0,
                    }
                )

    return files


def extract_mts_requirements(
    soup: BeautifulSoup,
    page_text: str = "",
    own_id: str = "",
    base_url: str = "https://modthesims.info",
    provider_name: str = "modthesims",
) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    """Extracts prerequisite modules and instructions mentioned on MTS."""
    req_items: List[Dict[str, Any]] = []
    raw_html = ""

    # Look for description sections or requirements boxes
    desc_box = soup.select_one("#descriptionbox, .downloadDescription, #actualcontent1")
    if desc_box:
        raw_html = str(desc_box)

    text_to_search = (desc_box.get_text("\n") if desc_box else page_text) or ""
    lines = text_to_search.splitlines()

    req_section_started = False
    for line in lines:
        l_str = line.strip()
        if not l_str:
            continue
        l_lower = l_str.lower()
        if any(h in l_lower for h in ["requirement", "requires:", "needed:", "prerequisite", "what you need"]):
            req_section_started = True
            continue

        if req_section_started:
            if any(h in l_lower for h in ["changelog", "credits", "installation:", "features:", "thanks"]):
                break
            clean_item = re.sub(r"^[-*•\d.]+\s*", "", l_str).strip()
            if clean_item and len(clean_item) > 3:
                req_items.append(
                    {
                        "title": clean_item,
                        "remote_id": f"mts_req_{len(req_items) + 1}",
                        "source": provider_name,
                        "is_installed": False,
                        "notes": "Extrait de la description ModTheSims",
                    }
                )

    item_id = extract_item_id(own_id, soup=soup, html_text=page_text)
    return item_id, raw_html, req_items
