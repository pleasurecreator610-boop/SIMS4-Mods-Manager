"""
The Sims Resource (TSR) Parsers: Parsing HTML browse cards, embedded `data-item` JSON,
item IDs, and requirement extraction.
"""

from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup

from src.utils.date_parser import parse_flexible_date


TSR_KNOWN_CROSS_DEPENDENCIES: List[Tuple[str, Dict[str, str]]] = [
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
        "sims 4 community library",
        {
            "source": "nsfwmods",
            "remote_id": "742",
            "title": "Sims 4 Community Library",
            "url": "https://nsfwmods.com/files/file/742-sims-4-community-library/",
        },
    ),
]


def _parse_tsr_timestamp(raw_val: Any) -> Optional[datetime]:
    """Converts a TSR UNIX timestamp or date string into a naive datetime."""
    if not raw_val:
        return None
    val_str = str(raw_val).strip()
    if not val_str or val_str == "0":
        return None
    if val_str.isdigit():
        try:
            ts = int(val_str)
            if ts > 100000000:
                return datetime.fromtimestamp(ts)
        except Exception:
            pass
    return parse_flexible_date(val_str)


def parse_tsr_browse_html(
    soup_or_html: Any,
    category: Any = None,
    base_url: str = "https://www.thesimsresource.com",
    page: int = 1,
    category_name: Optional[str] = None,
    source: str = "thesimsresource",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """Parses a The Sims Resource browse HTML page (`div.item-wrapper[data-item]` and `.item-link` fallback)

    and returns `(mods_list, detected_pages)`.
    """
    soup = (
        BeautifulSoup(soup_or_html, "html.parser")
        if isinstance(soup_or_html, str)
        else soup_or_html
    )
    cat_dict: Dict[str, Any] = (
        category
        if isinstance(category, dict)
        else {"name": category_name or (str(category) if category else "Mods (TSR)")}
    )

    detected_pages: Optional[int] = None
    if page == 1:
        page_nums: List[int] = []
        for a in soup.select("a[href*='/page/']"):
            href = a.get("href", "")
            m_cnt = re.search(r"/cnt/(\d+)", href)
            if m_cnt:
                total_items = int(m_cnt.group(1))
                page_nums.append(max(1, (total_items + 19) // 20))
            m_pg = re.search(r"/page/(\d+)", href)
            if m_pg:
                page_nums.append(int(m_pg.group(1)))
        if page_nums:
            detected_pages = min(max(page_nums), 50)

    results: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for wrapper in soup.select("div.item-wrapper[data-item]"):
        raw_json = wrapper.get("data-item", "")
        item_data: Dict[str, Any] = {}
        if raw_json:
            try:
                item_data = json.loads(raw_json)
            except Exception:
                item_data = {}

        link_el = wrapper.select_one("a.item-link[href]")
        raw_href = link_el["href"] if link_el else ""

        remote_id = str(item_data.get("ID") or item_data.get("ItemID") or "").strip()
        if not remote_id and raw_href:
            m_id = re.search(r"/id/(\d+)", raw_href)
            if m_id:
                remote_id = m_id.group(1)

        if not remote_id or remote_id in seen_ids:
            continue
        seen_ids.add(remote_id)

        title = str(item_data.get("title") or "").strip()
        if not title and link_el:
            title = link_el.get_text(strip=True)
        if not title:
            title = f"TSR Item #{remote_id}"

        author = str(item_data.get("creator") or item_data.get("creatorName") or "Unknown").strip()
        page_url = (
            urllib.parse.urljoin(base_url, raw_href)
            if raw_href
            else f"{base_url}/downloads/details/id/{remote_id}"
        )

        thumbnail_url = ""
        img_div = wrapper.select_one(".item-image[style]")
        if img_div and img_div.get("style"):
            m_bg = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", img_div["style"])
            if m_bg:
                thumbnail_url = urllib.parse.urljoin(base_url, m_bg.group(1))
        if not thumbnail_url and item_data.get("featuredImage"):
            fi = str(item_data["featuredImage"])
            thumbnail_url = fi if fi.startswith("http") else urllib.parse.urljoin(base_url, f"/scaled/{fi}")

        updated_date = (
            _parse_tsr_timestamp(item_data.get("lastUpdated"))
            or _parse_tsr_timestamp(item_data.get("publishDate"))
            or _parse_tsr_timestamp(item_data.get("submittedDate"))
        )
        published_date = (
            _parse_tsr_timestamp(item_data.get("publishDate"))
            or updated_date
        )

        tags: List[str] = []
        kw_raw = item_data.get("keywordsArr") or item_data.get("keywords")
        if isinstance(kw_raw, list):
            tags.extend(str(k).strip() for k in kw_raw if str(k).strip())
        elif isinstance(kw_raw, str) and kw_raw.strip():
            tags.extend(k.strip() for k in kw_raw.split(",") if k.strip())
        cat_label = cat_dict.get("name", "Mods (TSR)")
        if cat_label and cat_label not in tags:
            tags.append(cat_label)

        req_mods: List[Dict[str, Any]] = []
        req_items = item_data.get("RequiredItems") or item_data.get("requiredDownloads") or []
        if isinstance(req_items, list):
            for ri in req_items:
                if isinstance(ri, dict):
                    r_id = str(ri.get("ID") or ri.get("id") or ri.get("itemId") or "").strip()
                    r_title = str(ri.get("title") or ri.get("name") or f"TSR Required Mesh #{r_id}").strip()
                    if r_id and r_id != remote_id and not any(x["remote_id"] == r_id for x in req_mods):
                        req_mods.append(
                            {
                                "source": source,
                                "remote_id": r_id,
                                "title": r_title,
                                "url": f"{base_url}/downloads/details/id/{r_id}",
                                "type": "MOD",
                            }
                        )

        revision = str(item_data.get("revision") or "1").strip()
        ver_str = f"v{revision}" if revision else ""
        req_text = "\n".join(m["title"] for m in req_mods) if req_mods else None

        results.append(
            {
                "source": source,
                "remote_id": str(remote_id),
                "title": title,
                "author": author,
                "category": cat_dict.get("name", "Mods (TSR)"),
                "tags": tags,
                "page_url": page_url,
                "thumbnail_url": thumbnail_url,
                "updated_date": updated_date,
                "published_date": published_date,
                "version": ver_str,
                "version_str": ver_str,
                "patreon_status": "NONE",
                "patreon_tier": "",
                "requirements_text": req_text,
                "requirements_status": "FOUND" if req_mods else "NONE",
                "requirements_mods": req_mods,
            }
        )

    return results, detected_pages


def extract_item_id(
    url_or_id: str,
    soup: Optional[BeautifulSoup] = None,
    html_text: str = "",
) -> Optional[str]:
    """Extracts numeric TSR item ID from URL or HTML page."""
    clean = str(url_or_id).strip()
    if clean.isdigit():
        return clean
    for pattern in [
        r"/id/(\d+)",
        r"/itemId/(\d+)",
        r"[?&]itemid=(\d+)",
        r"/downloads/(\d{5,10})(?:[/?#]|$)",
    ]:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return m.group(1)

    if soup:
        dl_btn = soup.select_one("[itemid], [data-itemid], [data-item-id]")
        if dl_btn:
            val = dl_btn.get("itemid") or dl_btn.get("data-itemid") or dl_btn.get("data-item-id")
            if val and str(val).strip().isdigit():
                return str(val).strip()

    if html_text:
        m_raw = re.search(r'itemid="(\d{5,10})"', html_text)
        if m_raw:
            return m_raw.group(1)
    return None


def extract_requirements(
    soup: BeautifulSoup,
    own_id: str = "",
    base_url: str = "https://www.thesimsresource.com",
    provider_name: str = "thesimsresource",
) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    """Extracts required meshes and dependencies from TSR detail page DOM."""
    req_mods: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_rids: set[str] = set()

    def _add_req(dep_dict: Dict[str, str]) -> None:
        key = dep_dict["title"].strip().lower()
        rid = dep_dict.get("remote_id", "").strip().lower()
        if key and key not in seen_keys and (not rid or rid not in seen_rids):
            seen_keys.add(key)
            if rid:
                seen_rids.add(rid)
            req_mods.append(dep_dict)

    for req_container in soup.select(".required-items, #required-items, .required-downloads, .item-required"):
        for a in req_container.find_all("a", href=True):
            href = a["href"]
            m_id = re.search(r"/id/(\d+)|/downloads/(\d+)", href)
            if m_id:
                rid = m_id.group(1) or m_id.group(2)
                if rid and rid != own_id:
                    t_txt = a.get_text(strip=True) or f"TSR Required Mesh #{rid}"
                    _add_req(
                        {
                            "source": provider_name,
                            "remote_id": rid,
                            "title": t_txt,
                            "url": urllib.parse.urljoin(base_url, href),
                        }
                    )

    desc_el = soup.select_one(".item-description, #item-description, .description, article")
    if desc_el:
        desc_text_lower = desc_el.get_text(" ", strip=True).lower()
        for a in desc_el.find_all("a", href=True):
            href = a["href"]
            m_tsr = re.search(
                r"thesimsresource\.com/downloads/details/(?:[^\"']*?/)?id/(\d+)|^/downloads/details/(?:[^\"']*?/)?id/(\d+)",
                href,
            )
            if m_tsr:
                rid = m_tsr.group(1) or m_tsr.group(2)
                if rid and rid != own_id:
                    t_txt = a.get_text(strip=True)
                    if not t_txt or t_txt.lower() in {"here", "link", "mesh", "download", "tsr"}:
                        m_title_slug = re.search(r"/title/([^/]+)/", href)
                        t_txt = (
                            m_title_slug.group(1).replace("-", " ").title()
                            if m_title_slug
                            else f"TSR Required Mesh #{rid}"
                        )
                    _add_req(
                        {
                            "source": provider_name,
                            "remote_id": rid,
                            "title": t_txt,
                            "url": urllib.parse.urljoin(base_url, href),
                        }
                    )

        for kw, dep_info in TSR_KNOWN_CROSS_DEPENDENCIES:
            if kw in desc_text_lower:
                _add_req(dict(dep_info))

    if not req_mods:
        return None, "NONE", []

    req_text = "\n".join(m["title"] for m in req_mods)
    return req_text, "FOUND", req_mods
