"""Module de sanitisation et de validation d'URLs réseau (Protection Anti-SSRF et Whitelist).

Empêche les attaques SSRF (Server-Side Request Forgery) vers les plages d'adresses privées
ou les métadonnées cloud, et masque les paramètres sensibles dans les journaux.
"""

import ipaddress
import re
from typing import Optional, Set
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


DEFAULT_ALLOWED_DOMAINS: Set[str] = {
    "curseforge.com",
    "forgecdn.net",
    "thesimsresource.com",
    "loverslab.com",
    "nsfwmods.com",
    "patreon.com",
    "patreonusercontent.com",
    "simfileshare.net",
    "mediafire.com",
    "mega.nz",
    "google.com",
    "googleapis.com",
    "github.com",
    "githubusercontent.com",
    "gitlab.com",
}

_SENSITIVE_PARAM_NAMES = {
    "token",
    "auth",
    "key",
    "apikey",
    "api_key",
    "password",
    "secret",
    "sig",
    "signature",
    "session",
    "sessionid",
    "session_id",
    "csrf",
    "csrfkey",
}


def is_ip_private_or_reserved(host: str) -> bool:
    """Vérifie si une adresse IP (IPv4 ou IPv6) appartient à une plage privée ou réservée."""
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def is_domain_allowed(hostname: str, allowed_domains: Optional[Set[str]] = None) -> bool:
    """Vérifie si le nom d'hôte correspond à un domaine autorisé ou à l'un de ses sous-domaines."""
    if not hostname:
        return False

    host_lower = hostname.lower().strip(".")
    domains = allowed_domains or DEFAULT_ALLOWED_DOMAINS

    for dom in domains:
        dom_lower = dom.lower().strip(".")
        if host_lower == dom_lower or host_lower.endswith(f".{dom_lower}"):
            return True
    return False


def validate_download_url(
    url: str,
    allowed_domains: Optional[Set[str]] = None,
    allow_local: bool = False,
) -> bool:
    """Valide la sécurité d'une URL de téléchargement ou d'accès distant.

    Vérifie le protocole, l'absence de redirection SSRF vers réseau privé/metadata,
    et la correspondance aux domaines de confiance autorisés.
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_lower = hostname.lower()

    # Protection contre les métadonnées Cloud (AWS/GCP/Azure)
    if hostname_lower == "169.254.169.254" or hostname_lower.endswith(".internal"):
        return False

    # Protection contre les accès localhost / loopback en production
    if not allow_local:
        if hostname_lower in ("localhost", "127.0.0.1", "::1", str(ipaddress.IPv4Address(0))):
            return False
        if is_ip_private_or_reserved(hostname_lower):
            return False

    # Validation du domaine autorisé
    if allowed_domains is not None and not is_domain_allowed(hostname_lower, allowed_domains):
        return False

    return True


def sanitize_url_for_logging(url: str) -> str:
    """Masque les jetons d'authentification et clés API présents dans les paramètres d'URL."""
    if not url or not isinstance(url, str):
        return ""

    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url

        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sanitized_params = {}

        for k, v in query_params.items():
            if k.lower() in _SENSITIVE_PARAM_NAMES:
                sanitized_params[k] = ["[REDACTED]"]
            else:
                sanitized_params[k] = v

        new_query = urlencode(sanitized_params, doseq=True, safe="[]:")
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return re.sub(r"([?&](?:token|key|sig|auth)=)[^&]+", r"\1[REDACTED]", url, flags=re.IGNORECASE)
