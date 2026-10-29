"""Tests unitaires pour la validation et sanitisation des URLs (Anti-SSRF)."""

from src.infrastructure.network.url_sanitizer import (
    validate_download_url,
    sanitize_url_for_logging,
    is_domain_allowed,
    is_ip_private_or_reserved,
)


def test_is_ip_private_or_reserved():
    assert is_ip_private_or_reserved("127.0.0.1") is True
    assert is_ip_private_or_reserved("10.0.0.1") is True
    assert is_ip_private_or_reserved("192.168.1.100") is True
    assert is_ip_private_or_reserved("172.16.0.5") is True
    assert is_ip_private_or_reserved("169.254.169.254") is True
    assert is_ip_private_or_reserved("::1") is True

    # Adresses publiques
    assert is_ip_private_or_reserved("8.8.8.8") is False
    assert is_ip_private_or_reserved("1.1.1.1") is False

    # Nom d'hôte non-IP
    assert is_ip_private_or_reserved("example.com") is False


def test_is_domain_allowed():
    assert is_domain_allowed("curseforge.com") is True
    assert is_domain_allowed("media.forgecdn.net") is True
    assert is_domain_allowed("static.thesimsresource.com") is True
    assert is_domain_allowed("www.loverslab.com") is True
    assert is_domain_allowed("nsfwmods.com") is True
    assert is_domain_allowed("c10.patreonusercontent.com") is True

    # Domaines suspects ou non autorisés
    assert is_domain_allowed("evil-attacker.com") is False
    assert is_domain_allowed("fakecurseforge.com.evil.net") is False


def test_validate_download_url_valid():
    assert validate_download_url("https://media.forgecdn.net/files/1234/mod.zip") is True
    assert validate_download_url("https://www.thesimsresource.com/ajax.php?c=downloads&a=get&itemid=123") is True
    assert validate_download_url("https://simfileshare.net/download/99999/") is True


def test_validate_download_url_ssrf_attacks():
    # Loopback et réseau privé
    assert validate_download_url("http://127.0.0.1/admin") is False
    assert validate_download_url("http://localhost:8000/api") is False
    assert validate_download_url("https://192.168.1.1/router") is False
    assert validate_download_url("http://10.0.0.1/secret") is False

    # Métadonnées Cloud AWS / GCP / Azure
    assert validate_download_url("http://169.254.169.254/latest/meta-data/") is False
    assert validate_download_url("http://metadata.google.internal/computeMetadata/v1/") is False

    # Protocoles non HTTP(S)
    assert validate_download_url("file:///etc/passwd") is False
    assert validate_download_url("ftp://ftp.example.com/file.zip") is False
    assert validate_download_url("gopher://127.0.0.1/") is False


def test_sanitize_url_for_logging():
    url = "https://example.com/api?token=secret123&author=JohnDoe&apiKey=my-key-999"
    sanitized = sanitize_url_for_logging(url)

    assert "secret123" not in sanitized
    assert "my-key-999" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "author=JohnDoe" in sanitized
