"""
CurseForge Parsers: Parsing HTML search cards, detail pages, project/file IDs,
and CurseForge dependency mappings.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup

from src.utils.date_parser import parse_flexible_date


CURSEFORGE_KNOWN_DEPENDENCIES: List[Tuple[str, Dict[str, str]]] = [
    (
        "xml injector",
        {
            "source": "curseforge",
            "remote_id": "xml-injector",
            "title": "XML Injector",
            "url": "https://www.curseforge.com/sims4/mods/xml-injector",
        },
    ),
    (
        "lot 51 core library",
        {
            "source": "curseforge",
            "remote_id": "lot-51-core-library",
            "title": "Lot 51 Core Library",
            "url": "https://www.curseforge.com/sims4/mods/lot-51-core-library",
        },
    ),
    (
        "lot51 core library",
        {
            "source": "curseforge",
            "remote_id": "lot-51-core-library",
            "title": "Lot 51 Core Library",
            "url": "https://www.curseforge.com/sims4/mods/lot-51-core-library",
        },
    ),
    (
        "smart core script",
        {
            "source": "curseforge",
            "remote_id": "smart-core-script",
            "title": "Smart Core Script",
            "url": "https://www.curseforge.com/sims4/mods/smart-core-script",
        },
    ),
    (
        "sims 4 community library",
        {
            "source": "nsfwmods",
            "remote_id": "742",
            "title": "Sims 4 Community Library",
            "url": "https://nsfwmods.com/files/file/742-sims-4-community-library/",
        },
    ),
]


def parse_curseforge_search_html(
    soup_or_html: Any,
    category: Any = None,
    base_url: str = "https://www.curseforge.com",
    page: int = 1,
    category_name: Optional[str] = None,
    source: str = "curseforge",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """Parses a CurseForge Sims 4 search/category HTML page to extract `.project-card` entries

    and detected pagination count.
    """
    soup = BeautifulSoup(soup_or_html, "html.parser") if isinstance(soup_or_html, str) else soup_or_html
    cat_dict: Dict[str, Any] = (
        category
        if isinstance(category, dict)
        else {"name": category_name or (str(category) if category else "Mods (CurseForge)")}
    )
    detected_pages: Optional[int] = None
    if page == 1:
        page_nums: List[int] = []
        for a in soup.select("a[href*='page=']"):
            m = re.search(r"[?&]page=(\d+)", a.get("href", ""))
            if m:
                try:
                    page_nums.append(int(m.group(1)))
                except ValueError:
                    pass
        for btn in soup.select(".pagination-item, [class*='pagination'] button, [class*='pagination'] a"):
            txt = btn.get_text(strip=True)
            if txt.isdigit():
                page_nums.append(int(txt))
        if page_nums:
            detected_pages = min(max(page_nums), 50)

    cards = soup.select(".project-card")
    results: List[Dict[str, Any]] = []

    for card in cards:
        name_el = card.select_one("a.name, a.overlay-link")
        if not name_el or not name_el.get("href"):
            continue

        raw_href = name_el["href"].split("?")[0].rstrip("/")
        page_url = urllib.parse.urljoin(base_url, raw_href)
        slug = raw_href.rstrip("/").split("/")[-1]

        title = name_el.get_text(strip=True)
        if not title:
            title = slug.replace("-", " ").title()

        remote_id = slug
        for a in card.select("a[href*='/sims4/']"):
            href = a.get("href", "")
            m_s = re.search(r"/sims4/(?:mods|create-a-sim)/([^/?#]+)", href)
            if m_s:
                remote_id = m_s.group(1)
                break

        author_el = card.select_one("a.author-name, .author-name, a[href*='/members/']")
        author = author_el.get_text(strip=True) if author_el else "Auteur Inconnu"

        img_el = card.select_one("img.art, img.row-image, .project-avatar img, img")
        thumbnail_url = ""
        if img_el:
            thumbnail_url = img_el.get("src") or img_el.get("data-src") or ""
            if thumbnail_url.startswith("//"):
                thumbnail_url = "https:" + thumbnail_url
            elif thumbnail_url.startswith("/"):
                thumbnail_url = urllib.parse.urljoin(base_url, thumbnail_url)

        updated_date = None
        date_el = card.select_one("li.detail-updated span, .date-updated, time")
        if date_el:
            raw_date = date_el.get("datetime") or date_el.get("title") or date_el.get_text(strip=True)
            updated_date = parse_flexible_date(raw_date)

        cat_names = [cat_dict.get("name", "Mods (CurseForge)")]
        for c_link in card.select("a.category-link, a[href*='category='], .categories a"):
            c_text = c_link.get_text(strip=True)
            if c_text and c_text not in cat_names:
                cat_names.append(c_text)

        dl_file_id: Optional[str] = None
        for dl_a in card.select("a[href*='/download/'], a[href*='/files/']"):
            m_fid = re.search(r"/(?:download|files)/(\d+)", dl_a.get("href", ""))
            if m_fid:
                dl_file_id = m_fid.group(1)
                break

        entry: Dict[str, Any] = {
            "source": source,
            "remote_id": str(remote_id),
            "title": title,
            "author": author,
            "category": cat_dict.get("name", "Mods (CurseForge)"),
            "tags": cat_names,
            "page_url": page_url,
            "thumbnail_url": thumbnail_url,
            "updated_date": updated_date,
            "published_date": updated_date,
            "patreon_status": "NONE",
            "patreon_tier": "",
        }
        if dl_file_id:
            entry["latest_file_id"] = dl_file_id
        results.append(entry)

    return results, detected_pages


def extract_project_and_file_ids(soup: BeautifulSoup, html_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts numeric Project ID and latest File ID from a CurseForge mod page."""
    project_id: Optional[str] = None
    for dt in soup.find_all(["dt", "span", "div", "li", "section", "dl"]):
        txt = dt.get_text(" ", strip=True)
        m_pid = re.search(r"Project\s+ID\s*[:#]?\s*(\d{4,10})", txt, re.IGNORECASE)
        if m_pid:
            project_id = m_pid.group(1)
            break
    if not project_id:
        m_raw = re.search(r"Project\s+ID</dt>\s*<dd[^>]*>\s*(\d{4,10})\s*</dd>", html_text, re.IGNORECASE)
        if m_raw:
            project_id = m_raw.group(1)
    if not project_id:
        m_api = re.search(r"/api/v1/mods/(\d{4,10})", html_text)
        if m_api:
            project_id = m_api.group(1)
    if not project_id:
        m_json_pid = re.search(r'"project"\s*:\s*\{[^}]*"id"\s*:\s*(\d{4,10})', html_text)
        if m_json_pid:
            project_id = m_json_pid.group(1)

    file_id: Optional[str] = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m_f = re.search(r"/(?:files|download)/(\d{5,12})(?:[/?#]|$)", href)
        if m_f:
            file_id = m_f.group(1)
            break
    if not file_id:
        m_f_raw = re.search(r"/(?:files|download)/(\d{5,12})", html_text)
        if m_f_raw:
            file_id = m_f_raw.group(1)
    if not file_id:
        m_json_fid = re.search(r'"mainFile"\s*:\s*\{[^}]*"id"\s*:\s*(\d{5,12})', html_text)
        if m_json_fid:
            file_id = m_json_fid.group(1)

    return project_id, file_id


def extract_requirements(
    soup: BeautifulSoup,
    rel_soup: Optional[BeautifulSoup] = None,
) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    """Extracts and classifies required mods/dependencies from CurseForge Relations tab or page text."""
    req_mods: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    soups_to_check = [rel_soup] if rel_soup is not None else []
    soups_to_check.append(soup)

    for s in soups_to_check:
        if s is None:
            continue
        rel_cards = s.select(".dependency-card, .relation-card, div[data-relation-type='required'], a.relation-item")
        for rc in rel_cards:
            name_el = rc.select_one(".name, h3, strong, .title")
            url_el = rc.select_one("a[href*='/sims4/']") or (rc if rc.name == "a" else None)
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            href = url_el.get("href", "") if url_el else ""
            if href and not href.startswith("http"):
                href = f"https://www.curseforge.com{href}"
            m_id = re.search(r"/sims4/(?:mods|create-a-sim)/([^/?#]+)", href)
            dep_id = m_id.group(1) if m_id else name.lower().replace(" ", "-")
            if dep_id not in seen_ids:
                seen_ids.add(dep_id)
                req_mods.append(
                    {
                        "source": "curseforge",
                        "remote_id": dep_id,
                        "title": name,
                        "url": href,
                        "type": "MOD",
                    }
                )

    page_text = soup.get_text(separator=" ", strip=True).lower()
    for kw, dep_dict in CURSEFORGE_KNOWN_DEPENDENCIES:
        if kw in page_text:
            dep_id = dep_dict["remote_id"]
            if dep_id not in seen_ids:
                seen_ids.add(dep_id)
                req_mods.append(
                    {
                        "source": dep_dict["source"],
                        "remote_id": dep_id,
                        "title": dep_dict["title"],
                        "url": dep_dict["url"],
                        "type": "MOD",
                    }
                )

    if not req_mods:
        return None, "NONE", []

    req_text = "\n".join(m["title"] for m in req_mods)
    return req_text, "FOUND", req_mods
