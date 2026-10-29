"""Tests unitaires pour les DTOs ScrapedModDTO et ScrapedFileDTO."""

from datetime import datetime
from src.domain.models.scraped_mod import ScrapedModDTO, ScrapedFileDTO


def test_scraped_file_dto():
    f = ScrapedFileDTO(
        file_id="12345",
        file_name="awesome_mod_v1.zip",
        download_url="https://example.com/download/12345",
        file_size_bytes=1048576,
        version_str="1.0.0",
        is_primary=True,
    )
    assert f.file_id == "12345"
    assert f.file_name == "awesome_mod_v1.zip"
    assert f.is_primary is True


def test_scraped_mod_dto_to_catalog_dict():
    now = datetime(2026, 10, 29, 12, 0, 0)
    dto = ScrapedModDTO(
        source="curseforge",
        remote_id="999888",
        title="Modern Furniture Pack",
        author="DesignerSim",
        category="Build / Buy",
        page_url="https://curseforge.com/sims4/mods/furniture",
        thumbnail_url="https://curseforge.com/thumb.png",
        published_date=now,
        tags=["furniture", "decor"],
    )

    d = dto.to_catalog_dict()
    assert d["source"] == "curseforge"
    assert d["remote_id"] == "999888"
    assert d["title"] == "Modern Furniture Pack"
    assert d["tags"] == ["furniture", "decor"]
    assert d["thumbnail_url"] == "https://curseforge.com/thumb.png"
    assert d["patreon_status"] == "NONE"
