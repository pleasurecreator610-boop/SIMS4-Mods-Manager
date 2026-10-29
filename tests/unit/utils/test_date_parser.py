"""
Unit tests for centralized date parser utility.
"""

from datetime import datetime
from src.utils.date_parser import parse_flexible_date


def test_parse_flexible_date_none_and_empty():
    assert parse_flexible_date(None) is None
    assert parse_flexible_date("") is None
    fallback = datetime(2025, 1, 1)
    assert parse_flexible_date("", default=fallback) == fallback


def test_parse_flexible_date_datetime_passthrough():
    dt = datetime(2026, 5, 10, 14, 30, 0)
    res = parse_flexible_date(dt)
    assert res == dt


def test_parse_flexible_date_timestamps():
    # Epoch timestamp for 2026-01-01 00:00:00 UTC approx
    ts = 1767225600
    res = parse_flexible_date(ts)
    assert res is not None
    assert res.year == 2026

    # Millisecond timestamp
    res_ms = parse_flexible_date(ts * 1000)
    assert res_ms is not None
    assert res_ms.year == 2026


def test_parse_flexible_date_iso_and_strings():
    res = parse_flexible_date("2026-03-24T12:00:00Z")
    assert res is not None
    assert res.year == 2026
    assert res.month == 3
    assert res.day == 24
    assert res.hour == 12


def test_parse_flexible_date_relative_en():
    res = parse_flexible_date("2 hours ago")
    assert res is not None
    delta = datetime.now() - res
    assert 7100 <= delta.total_seconds() <= 7300


def test_parse_flexible_date_relative_fr():
    res = parse_flexible_date("il y a 3 jours")
    assert res is not None
    delta = datetime.now() - res
    assert 2.9 <= delta.total_seconds() / 86400 <= 3.1
