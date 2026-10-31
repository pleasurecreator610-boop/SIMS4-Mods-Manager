"""Fonctions d'analyse et de nettoyage HTML pour les plateformes IPS4 (LoversLab, NSFWMods)."""

from __future__ import annotations

import copy
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.utils.logger import logger

__all__ = [
    "extract_gallery_screenshots",
    "sanitize_description_html",
    "parse_category_page_html",
]


def parse_category_page_html(
    soup: BeautifulSoup,
    category: Dict[str, Any],
    base_url: str = "https://www.loverslab.com",
    page: int = 1,
    source_name: str = "loverslab",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """Analyse une page de catégorie IPS4 pour extraire la liste des mods et le nombre total de pages."""
    detected_pages: Optional[int] = None
    if page == 1:
        pag = soup.select_one("[data-pages]")
        if pag and pag.get("data-pages"):
            try:
                detected_pages = int(pag["data-pages"])
            except Exception:
                pass
        if not detected_pages:
            p_nums = []
            for a in soup.select("ul.ipsPagination a[href*='/page/']"):
                m = re.search(r"/page/(\d+)", a.get("href", ""))
                if m:
                    p_nums.append(int(m.group(1)))
            if p_nums:
                detected_pages = max(p_nums)

    items = soup.select("li.ipsDataItem, li[data-rowid]")
    results: List[Dict[str, Any]] = []

    for item in items:
        title_elem = item.select_one(
            ".ipsDataItem_title a[href*='/files/file/'], "
            "h4.ipsDataItem_title a, "
            ".ipsDataItem_title a, "
            "h4 a[href*='/files/file/']"
        )
        if not title_elem or not title_elem.get("href"):
            title_elem = item.select_one("a[href*='/files/file/']")
        if not title_elem or not title_elem.get("href"):
            continue

        page_url = title_elem["href"]
        if "files/file/" not in page_url:
            continue

        remote_id_match = re.search(r"/files/file/(\d+)", page_url)
        remote_id = remote_id_match.group(1) if remote_id_match else page_url

        title = title_elem.get_text(strip=True) if title_elem else ""
        title = title.replace("\u200b", "").replace("\ufeff", "").strip()
        if title in ["''", '""']:
            title = ""

        if not title and title_elem and title_elem.get("title"):
            raw_title = title_elem["title"]
            cleaned = re.sub(
                r'^(View the file\s*|More information about\s*["\'\\]?)', "", raw_title, flags=re.IGNORECASE
            )
            cleaned = re.sub(r'["\'\\]?\s*$', "", cleaned)
            title = cleaned.replace("\u200b", "").replace("\ufeff", "").strip()

        if not title or title in ["''", '""']:
            slug_match = re.search(r"/files/file/\d+-([^/]+)", urllib.parse.unquote(page_url))
            if slug_match:
                title = (
                    slug_match.group(1)
                    .replace("-", " ")
                    .replace("—", "-")
                    .replace("\u200b", "")
                    .replace("\ufeff", "")
                    .strip()
                    .title()
                )
            else:
                title = f"Mod LoversLab #{remote_id}"

        author_elem = item.select_one(".ipsDataItem_author, a[data-ipshover]")
        author = author_elem.get_text(strip=True) if author_elem else "Inconnu"
        author = author.replace("\u200b", "").replace("\ufeff", "").strip()

        thumbnail_url = ""
        thumb_elem = item.select_one(
            "img.ipsItem_coverImage, img[data-src], img[src*='monthly_'], img[src*='uploads/'], img"
        )
        if thumb_elem:
            thumbnail_url = (
                thumb_elem.get("data-src") or thumb_elem.get("data-loaded-src") or thumb_elem.get("src") or ""
            )

        if not thumbnail_url:
            cover_elem = item.select_one("[style*='background-image'], .cFileView_cover, .ipsCoverImage")
            if cover_elem and cover_elem.get("style"):
                bg_match = re.search(r'url\(["\'\\]?([^"\'\\)]+)["\'\\]?\)', cover_elem["style"])
                if bg_match:
                    thumbnail_url = bg_match.group(1)

        if thumbnail_url:
            if thumbnail_url.startswith("//"):
                thumbnail_url = "https:" + thumbnail_url
            elif thumbnail_url.startswith("/"):
                thumbnail_url = base_url + thumbnail_url

        time_elem = item.select_one("time[datetime]")
        updated_date = None
        if time_elem and time_elem.get("datetime"):
            try:
                updated_date = date_parser.parse(time_elem["datetime"]).replace(tzinfo=None)
            except Exception:
                logger.debug(f"Could not parse date for item {remote_id}: {time_elem.get('datetime')}")

        tags = [t.get_text(strip=True) for t in item.select(".ipsBadge, .ipsTag") if t.get_text(strip=True)]
        if category.get("name") and category["name"] not in tags:
            tags.append(category["name"])

        results.append(
            {
                "source": source_name,
                "remote_id": remote_id,
                "title": title,
                "author": author,
                "category": category.get("name", ""),
                "tags": tags,
                "page_url": page_url,
                "thumbnail_url": thumbnail_url,
                "updated_date": updated_date,
                "published_date": updated_date,
                "patreon_status": "NONE",
                "patreon_tier": "",
            }
        )

    return results, detected_pages


def extract_gallery_screenshots(soup: BeautifulSoup, base_url: str = "https://www.loverslab.com") -> List[str]:
    """Extrait les captures d'écran haute résolution des pages de fichiers IPS4."""
    gallery_screenshots: List[str] = []
    carousel_candidates = []

    art_elem = soup.select_one("article")
    if art_elem:
        prev_car = art_elem.find_previous(class_="ipsCarousel")
        if prev_car:
            carousel_candidates.append(prev_car)
    if not carousel_candidates:
        for car in soup.select(".cFileTop .ipsCarousel, .cFileView_screenshots"):
            if car not in carousel_candidates:
                carousel_candidates.append(car)

    for car in carousel_candidates:
        for it in car.select("[data-fullurl], li, .ipsThumb"):
            u = it.get("data-fullurl")
            if not u:
                f_el = it.select_one("[data-fullurl]")
                if f_el:
                    u = f_el.get("data-fullurl")
            if not u:
                img_el = it.select_one("img")
                if img_el:
                    u = img_el.get("data-src") or img_el.get("src")
            if not u:
                bg = it.get("style", "")
                m_bg = re.search(r'url\(\s*["\']?(.*?)["\']?\s*\)', bg)
                if m_bg:
                    u = m_bg.group(1)
            if u:
                if u.startswith("/"):
                    u = f"{base_url}{u}"
                if u.startswith("http") and not any(
                    j in u.lower() for j in ["/themes/", "/reactions/", "icon_", "avatar", "logo", ".svg"]
                ):
                    if u not in gallery_screenshots:
                        gallery_screenshots.append(u)

    for a in soup.select(
        "a[data-ipsLightbox], a[href*='/screenshots/'], .cFileTop a[href$='.jpg'], .cFileTop a[href$='.png'], .cFileTop a[href$='.webp']"
    ):
        h = a.get("href")
        if (
            h
            and h.startswith("http")
            and not any(j in h.lower() for j in ["/themes/", "/reactions/", "icon_", "avatar", "logo", ".svg"])
        ):
            if h not in gallery_screenshots:
                gallery_screenshots.append(h)

    return gallery_screenshots


def sanitize_description_html(content_elem, base_url: str = "https://www.loverslab.com") -> Tuple[str, List[str]]:
    """Nettoie les scripts/styles inline et retourne le HTML assaini ainsi que la liste des images du corps."""
    clean_elem = copy.deepcopy(content_elem)
    for junk in clean_elem.select(
        ".cFileChangelog, [data-role='changelog'], div#changeLogData, .ipsMenu, script, style, iframe, form, button, input, noscript, h2, hr, p.ipsType_light"
    ):
        junk.decompose()

    for tag in clean_elem.find_all(True):
        st = tag.get("style", "")
        if st:
            new_st = re.sub(r"background(?:-color)?\s*:\s*[^;]+;?", "", st, flags=re.IGNORECASE)
            new_st = re.sub(r"color\s*:\s*[^;]+;?", "", new_st, flags=re.IGNORECASE)
            new_st = new_st.strip()
            if new_st:
                tag["style"] = new_st
            else:
                del tag["style"]

    body_imgs: List[str] = []
    for img in clean_elem.select("img"):
        src = img.get("data-src") or img.get("src")
        if src:
            if src.startswith("/"):
                src = f"{base_url}{src}"
            img["src"] = src
            body_imgs.append(src)
        for attr in ["data-ratio", "data-fileid", "srcset", "sizes", "class", "loading"]:
            if attr in img.attrs:
                del img.attrs[attr]
        img["style"] = "max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block;"

    for a_tag in clean_elem.select("a[href]"):
        href = a_tag.get("href", "")
        if isinstance(href, str) and href.startswith("/"):
            a_tag["href"] = f"{base_url}{href}"

    clean_body_html = clean_elem.decode_contents().strip()
    return clean_body_html, body_imgs
