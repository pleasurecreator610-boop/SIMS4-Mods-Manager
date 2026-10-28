"""Plugin provider pour The Sims Resource (https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/)."""

from plugins.thesimsresource.scraper import (
    TheSimsResourceProvider,
    parse_tsr_browse_html,
)

__all__ = ["TheSimsResourceProvider", "parse_tsr_browse_html"]

