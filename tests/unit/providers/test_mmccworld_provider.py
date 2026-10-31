"""Tests unitaires complets pour le plugin MMCCWorldProvider et la résolution SimFileShare."""

from plugins.mmccworld import MMCCWorldProvider
from plugins.mmccworld.parsers import (
    extract_download_links,
    extract_mmccworld_requirements,
    extract_post_id,
    parse_mmccworld_rss,
)
from src.core.session_manager import SessionManager
from src.domain.models.category_mapping import CategoryMappingService
from src.providers.registry import ProviderRegistry


SAMPLE_MMCCWORLD_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Maxis Match CC World</title>
    <link>https://maxismatchccworld.tumblr.com/</link>
    <item>
      <title>#trillyke Cozy Autumn Sweater Collection</title>
      <link>https://maxismatchccworld.tumblr.com/post/745485207111680001</link>
      <pubDate>Wed, 20 Mar 2024 16:54:55 +0100</pubDate>
      <description><![CDATA[
        <p><a class="tumblr_blog" href="https://trillyke.tumblr.com/">trillyke</a>:</p>
        <p>A set of cozy oversized sweaters for cold winter days.</p>
        <p>Requires: Trillyke Knit Base Mesh</p>
        <p>Note: Base Game compatible - Maxis Match friendly.</p>
        <p><a href="http://www.simfileshare.net/download/123456/">Download on SFS</a></p>
        <p><a href="https://www.patreon.com/posts/autumn-sweater-987654">Early Access on Patreon</a></p>
      ]]></description>
    </item>
    <item>
      <title>#sixamcc Rustic Farmhouse Kitchen Counters and Cabinets</title>
      <link>https://maxismatchccworld.tumblr.com/post/745485207111680002</link>
      <pubDate>Wed, 20 Mar 2024 16:50:00 +0100</pubDate>
      <description><![CDATA[
        <p><a class="tumblr_blog" href="https://sixamcc.tumblr.com/">sixamcc</a>:</p>
        <p>Rustic wooden kitchen set with custom textures.</p>
        <p>Mesh required: SixamCC Modular Counter Mesh Rig</p>
        <p>Important: Use bb.moveobjects on when placing overhead cabinets.</p>
        <p><a href="https://simfileshare.net/download/789101/">SFS Download</a></p>
      ]]></description>
    </item>
  </channel>
</rss>
"""


def test_mmccworld_registered_and_categories_configured():
    """Vérifie que MMCCWorldProvider est bien enregistré dans ProviderRegistry."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("mmccworld")
    assert prov is not None
    assert isinstance(prov, MMCCWorldProvider)
    assert prov.provider_name == "mmccworld"
    assert prov.base_url == "https://maxismatchccworld.tumblr.com"
    assert len(prov.CATEGORIES) == 8
    cat_ids = [c["id"] for c in prov.CATEGORIES]
    assert "mmccw_clothing" in cat_ids
    assert "mmccw_hair" in cat_ids
    assert "mmccw_build_buy" in cat_ids


def test_extract_post_id():
    """Vérifie l'extraction de l'ID numérique de billet Tumblr."""
    assert (
        extract_post_id("https://maxismatchccworld.tumblr.com/post/745485207111680001/autumn") == "745485207111680001"
    )
    assert extract_post_id("/post/12345") == "12345"
    assert extract_post_id("invalid-url") is None


def test_parse_mmccworld_rss():
    """Vérifie le parsing complet du flux RSS Maxis Match CC World."""
    cat = {"id": "mmccw_clothing", "slug": "clothing"}
    mods = parse_mmccworld_rss(SAMPLE_MMCCWORLD_RSS, cat)
    assert len(mods) == 2

    assert mods[0]["remote_id"] == "mmccworld_745485207111680001"
    assert "Cozy Autumn Sweater" in mods[0]["title"]
    assert mods[0]["author"] == "trillyke"
    assert mods[0]["category"] == "clothing"
    assert len(mods[0]["download_urls"]) == 2

    assert mods[1]["remote_id"] == "mmccworld_745485207111680002"
    assert "Rustic Farmhouse Kitchen" in mods[1]["title"]
    assert mods[1]["author"] == "sixamcc"


def test_extract_mmccworld_requirements_distinction_mod_vs_comment():
    """
    Vérifie la séparation stricte entre :
    - MOD : dépendance binaire / mesh (Trillyke Knit Base Mesh, SixamCC Modular Counter Mesh Rig).
    - COMMENT : consignes de jeu ou de placement (Base Game compatible, bb.moveobjects on).
    """
    html_1 = """
    <p>Requires: Trillyke Knit Base Mesh</p>
    <p>Note: Base Game compatible - Maxis Match friendly.</p>
    """
    reqs_1 = extract_mmccworld_requirements(html_1)
    assert len(reqs_1) >= 2

    mod_dep_1 = next((r for r in reqs_1 if r["type"] == "MOD"), None)
    comment_dep_1 = next((r for r in reqs_1 if r["type"] == "COMMENT"), None)

    assert mod_dep_1 is not None
    assert "Trillyke Knit Base Mesh" in mod_dep_1["name"]
    assert mod_dep_1["resolved"] is False

    assert comment_dep_1 is not None
    assert "Base Game compatible" in comment_dep_1["name"]
    assert comment_dep_1["resolved"] is False

    html_2 = """
    <p>Mesh required: SixamCC Modular Counter Mesh Rig</p>
    <p>Important: Use bb.moveobjects on when placing overhead cabinets.</p>
    """
    reqs_2 = extract_mmccworld_requirements(html_2)
    assert len(reqs_2) >= 2

    mod_dep_2 = next((r for r in reqs_2 if r["type"] == "MOD"), None)
    comment_dep_2 = next((r for r in reqs_2 if r["type"] == "COMMENT"), None)

    assert mod_dep_2 is not None
    assert "SixamCC Modular Counter Mesh Rig" in mod_dep_2["name"]

    assert comment_dep_2 is not None
    assert "moveobjects" in comment_dep_2["name"]


def test_extract_download_links_sfs_routing():
    """Vérifie l'extraction et l'identification des liens de téléchargement SFS et Patreon."""
    html = """
    <p><a href="http://www.simfileshare.net/download/123456/">Download on SFS</a></p>
    <p><a href="https://www.patreon.com/posts/autumn-sweater-987654">Early Access on Patreon</a></p>
    """
    links = extract_download_links(html)
    assert len(links) == 2
    assert links[0]["type"] == "sfs"
    assert "simfileshare.net" in links[0]["url"]
    assert links[1]["type"] == "patreon"
    assert "patreon.com" in links[1]["url"]


def test_mmccworld_category_mapping():
    """Vérifie le mappage des catégories universelles pour Maxis Match CC World."""
    assert CategoryMappingService.get_unified_category("mmccworld", "mmccw_clothing") == "clothing"
    assert CategoryMappingService.get_unified_category("mmccworld", "mmccw_hair") == "hair"
    assert CategoryMappingService.get_unified_category("mmccworld", "mmccw_build_buy") == "build_buy"
    assert CategoryMappingService.get_unified_category("mmccworld", "mmccw_poses") == "animations_poses"
    assert CategoryMappingService.get_unified_category("mmccworld", "unknown") == "miscellaneous"


def test_simfileshare_verify_session_success():
    """Vérifie que la vérification de session pour SimFileShare réussit sans erreur UnboundLocalError."""
    ok, msg = SessionManager.verify_session("simfileshare")
    assert ok is True
    assert "SimFileShare" in msg
