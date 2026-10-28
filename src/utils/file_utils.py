import random
import re
import unicodedata
from pathlib import Path
from typing import Optional


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_filename(name: str) -> str:
    """Sanitizes file names to be strictly safe and valid on Windows and cross-platform."""
    if not name:
        return "Mod"
    # Supprimer les caractères nuls, de contrôle ASCII et non imprimables
    clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", name)
    # Remplacer les séparateurs de chemin et caractères interdits Windows
    clean = re.sub(r'[\\/*?:"<>|]', "", clean)
    clean = clean.strip(". ").replace(" ", "_")

    # Protection contre les noms de périphériques réservés sous Windows
    stem = Path(clean).stem.upper()
    if stem in WINDOWS_RESERVED_NAMES:
        clean = f"mod_{clean}"

    return clean or "Mod"


def sanitize_content_disposition(content_disposition: str) -> Optional[str]:
    """Extrait et assainit en toute sécurité le nom de fichier d'un en-tête HTTP Content-Disposition."""
    if not content_disposition:
        return None
    # Extraction regex du paramètre filename="..." ou filename=...
    match = re.search(r'filename\*?=(?:UTF-8\'\')?(?:"([^"]+)"|([^;]+))', content_disposition, re.IGNORECASE)
    if not match:
        return None
    raw_name = match.group(1) or match.group(2) or ""
    clean = sanitize_filename(raw_name.strip("'\" \t\r\n"))
    return clean if clean and clean != "Mod" else None


def sanitize_mod_folder_name(name: str) -> str:
    """
    Sanitizes a name to contain ONLY alphanumeric characters (A-Z, a-z, 0-9) and underscores.
    Strips spaces, apostrophes (', ’, `), accents/diacritics, and special characters.
    """
    if not name:
        return "Mod"
    # 1. Unicode decomposition to strip accents (e.g. 'é' -> 'e', 'ü' -> 'u')
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    # 2. Remove apostrophes completely
    normalized = normalized.replace("'", "").replace("’", "").replace("`", "")
    # 3. Replace any character that is NOT alphanumeric or underscore with an underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", normalized)
    # 4. Collapse multiple underscores into one and trim edges
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "Mod"


def generate_unique_mod_folder_name(source: str, title: str, mods_dir: Optional[Path] = None) -> str:
    """
    Generates a folder name with strictly alphanumeric characters and underscores,
    ending with a random 3-digit number `_xxx` to eliminate collision risks.
    Format: `{clean_source}_{clean_title}_{random_3_digits}`
    """
    clean_source = sanitize_mod_folder_name(source)
    clean_title = sanitize_mod_folder_name(title)

    for _ in range(50):
        rand_suffix = f"{random.randint(100, 999)}"
        folder_name = f"{clean_source}_{clean_title}_{rand_suffix}"
        if not mods_dir or not (mods_dir / folder_name).exists():
            return folder_name

    return f"{clean_source}_{clean_title}_{random.randint(1000, 9999)}"


def cleanup_temp_download_files(temp_dir: Path, ttl_seconds: int = 86400) -> int:
    """Purge les fichiers temporaires orphelins (.tmp, .part, .crdownload, etc.) plus vieux que ttl_seconds."""
    if not temp_dir.exists():
        return 0
    import time

    now = time.time()
    deleted_count = 0
    temp_extensions = {".tmp", ".part", ".crdownload", ".download"}
    for p in temp_dir.glob("*"):
        if p.is_file() and (p.suffix.lower() in temp_extensions or p.name.startswith("tmp_")):
            try:
                if now - p.stat().st_mtime > ttl_seconds:
                    p.unlink(missing_ok=True)
                    deleted_count += 1
            except Exception:
                pass
    return deleted_count
