"""Plugin fournisseur CurseForge Sims 4 (https://www.curseforge.com/sims4)."""

from .provider import CurseForgeProvider, parse_curseforge_search_html

__all__ = ["CurseForgeProvider", "parse_curseforge_search_html"]
