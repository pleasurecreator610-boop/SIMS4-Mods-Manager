"""Tests unitaires complets pour le plugin SimsFindsProvider (plugins/simsfinds/)."""

from plugins.simsfinds import SimsFindsProvider
from plugins.simsfinds.parsers import (
    extract_item_id,
    extract_simsfinds_download_links,
    extract_simsfinds_requirements,
    parse_simsfinds_browse_html,
)
from src.providers.registry import ProviderRegistry


SAMPLE_SIMSFINDS_BROWSE_HTML = """
<html>
<body>
<div class="row">
  <div class="col-6 col-md-3">
    <a href="/en/downloads/401435/warm-and-wicked-living-room-part-2-sims4">
      <img src="https://static.simsfinds.com/images/401435.jpg" />
      <span>Warm And Wicked Living Room Part 2</span>
    </a>
  </div>
  <div class="col-6 col-md-3">
    <a href="/en/downloads/399812/chroma-nails-by-trillyke-sims4">
      <img src="https://static.simsfinds.com/images/399812.jpg" />
      <span>Chroma Nails by trillyke</span>
    </a>
  </div>
</div>
</body>
</html>
"""

SAMPLE_SIMSFINDS_DETAIL_HTML = """
<html>
<body>
<div class="post-title">Warm And Wicked Living Room Part 2</div>
<div class="creator-name"><a href="/en/creators/syboulette">Syboulette</a></div>
<div class="post-content">
  <p>A lovely dark gothic living room set for The Sims 4.</p>
  <p>Requires: XML Injector v4 Mesh Library</p>
  <p>Note: Laptop mode must be turned off to see shaders properly.</p>
</div>
<div class="download-button">
  <a href="https://click.simsfinds.com/go?url=https%3A%2F%2Fwww.curseforge.com%2Fsims4%2Fmods%2Fxml-injector">Direct Download</a>
</div>
</body>
</html>
"""


def test_simsfinds_registered_and_categories_configured():
    """Vérifie que SimsFindsProvider est correctement enregistré dans ProviderRegistry."""
    ProviderRegistry.initialize()
    prov = ProviderRegistry.get_provider("simsfinds")
    assert prov is not None
    assert isinstance(prov, SimsFindsProvider)
    assert prov.provider_name == "simsfinds"
    assert prov.base_url == "https://www.simsfinds.com"
    assert len(prov.CATEGORIES) >= 10
    ids = [c["id"] for c in prov.CATEGORIES]
    assert "sfinds_hairstyles" in ids
    assert "sfinds_clothing" in ids
    assert "sfinds_accessories" in ids


def test_parse_simsfinds_browse_html():
    """Vérifie l'extraction des éléments depuis le HTML de catalogue SimsFinds."""
    cat = {"id": "sfinds_hairstyles", "slug": "hairstyles"}
    mods = parse_simsfinds_browse_html(SAMPLE_SIMSFINDS_BROWSE_HTML, cat)
    assert len(mods) == 2
    assert mods[0]["remote_id"] == "simsfinds_401435"
    assert "Warm And Wicked" in mods[0]["title"]
    assert mods[1]["remote_id"] == "simsfinds_399812"


def test_extract_item_id():
    """Vérifie l'extraction de l'ID numérique."""
    assert extract_item_id("https://www.simsfinds.com/downloads/401435/mod-title") == "401435"
    assert extract_item_id("/downloads/12345/something") == "12345"
    assert extract_item_id("https://www.simsfinds.com/?id=98765") == "98765"
    assert extract_item_id("invalid-url") is None


def test_extract_simsfinds_requirements():
    """Vérifie la distinction stricte MOD vs COMMENT."""
    reqs = extract_simsfinds_requirements(SAMPLE_SIMSFINDS_DETAIL_HTML)
    assert len(reqs) >= 2
    # XML Injector v4 Mesh Library should be detected as MOD
    matched_mod = any(r["type"] == "MOD" and "Injector" in r["name"] for r in reqs)
    # Laptop mode note should be detected as COMMENT
    matched_comment = any(r["type"] == "COMMENT" and "Laptop mode" in r["name"] for r in reqs)
    assert matched_mod
    assert matched_comment


def test_extract_simsfinds_download_links():
    """Vérifie l'extraction de l'URL cible de redirection."""
    links = extract_simsfinds_download_links(SAMPLE_SIMSFINDS_DETAIL_HTML)
    assert len(links) >= 1
    assert any("curseforge.com" in link["url"] for link in links)
