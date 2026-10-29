"""
Date Parser: Flexible, centralized date parsing utility supporting ISO, RFC,
localized human-relative dates (EN/FR) and timestamps across all scrapers.
"""

from datetime import datetime, timedelta
import re
from typing import Optional, Union
from dateutil import parser as du_parser

from src.utils.logger import logger


_RELATIVE_PATTERNS = [
    # English relative patterns
    (re.compile(r"(\d+)\s*(?:sec|second)s?\s*ago", re.IGNORECASE), lambda n: timedelta(seconds=n)),
    (re.compile(r"(\d+)\s*(?:min|minute)s?\s*ago", re.IGNORECASE), lambda n: timedelta(minutes=n)),
    (re.compile(r"(\d+)\s*(?:hour|hr)s?\s*ago", re.IGNORECASE), lambda n: timedelta(hours=n)),
    (re.compile(r"(\d+)\s*(?:day)s?\s*ago", re.IGNORECASE), lambda n: timedelta(days=n)),
    (re.compile(r"(\d+)\s*(?:week)s?\s*ago", re.IGNORECASE), lambda n: timedelta(weeks=n)),
    (re.compile(r"(\d+)\s*(?:month)s?\s*ago", re.IGNORECASE), lambda n: timedelta(days=n * 30)),
    (re.compile(r"(\d+)\s*(?:year)s?\s*ago", re.IGNORECASE), lambda n: timedelta(days=n * 365)),
    # French relative patterns
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:sec|seconde)s?", re.IGNORECASE), lambda n: timedelta(seconds=n)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:min|minute)s?", re.IGNORECASE), lambda n: timedelta(minutes=n)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:heure|h)s?", re.IGNORECASE), lambda n: timedelta(hours=n)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:jour)s?", re.IGNORECASE), lambda n: timedelta(days=n)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:semaine)s?", re.IGNORECASE), lambda n: timedelta(weeks=n)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:mois)", re.IGNORECASE), lambda n: timedelta(days=n * 30)),
    (re.compile(r"il\s+y\s+a\s+(\d+)\s*(?:an|anne)s?", re.IGNORECASE), lambda n: timedelta(days=n * 365)),
]


def parse_flexible_date(
    date_val: Union[str, datetime, int, float, None],
    default: Optional[datetime] = None,
) -> Optional[datetime]:
    """Parses arbitrary date formats into a naive UTC datetime.

    Supports ISO 8601, ForgeCDN strings, relative time strings ('2 hours ago',
    'il y a 3 jours'), Unix epoch timestamps and native datetime objects.
    """
    if date_val is None:
        return default

    if isinstance(date_val, datetime):
        return date_val.replace(tzinfo=None)

    if isinstance(date_val, (int, float)):
        try:
            # Handle millisecond timestamps (e.g. 13 digits)
            ts = date_val / 1000.0 if date_val > 1e11 else float(date_val)
            return datetime.fromtimestamp(ts).replace(tzinfo=None)
        except Exception:
            return default

    s_val = str(date_val).strip()
    if not s_val:
        return default

    now = datetime.now()
    lower_s = s_val.lower()

    if lower_s in ("just now", " l'instant", "a l'instant"):
        return now
    if lower_s in ("today", "aujourd'hui"):
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if lower_s in ("yesterday", "hier"):
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    for pattern, delta_fn in _RELATIVE_PATTERNS:
        match = pattern.search(lower_s)
        if match:
            try:
                count = int(match.group(1))
                return now - delta_fn(count)
            except Exception:
                pass

    try:
        parsed = du_parser.parse(s_val)
        return parsed.replace(tzinfo=None)
    except Exception as exc:
        logger.debug(f"parse_flexible_date: unable to parse '{s_val}': {exc}")
        return default
