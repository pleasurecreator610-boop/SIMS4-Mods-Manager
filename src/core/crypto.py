"""Module de cryptographie sécurisée multiplateforme pour le stockage des sessions et identifiants.

Utilise le chiffrement symétrique authentifié AES-256-GCM avec dérivation de clé PBKDF2 (SHA-256).
Assure la rétrocompatibilité avec les formats historiques (Windows DPAPI et repli Base64).
"""

import base64
import json
import os
import platform
from pathlib import Path
from typing import Any, Dict, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from src.core.config import AppConfig
from src.utils.logger import logger


_SALT_FILE_NAME = ".crypto_salt"
_CACHE_KEY: Optional[bytes] = None


def _get_machine_identifier() -> bytes:
    """Génère une chaîne d'identification machine stable et locale à l'utilisateur."""
    parts = [
        platform.node(),
        platform.machine(),
        os.environ.get("USERNAME") or os.environ.get("USER") or "default_user",
        str(Path.home()),
    ]
    return ":".join(parts).encode("utf-8")


def _get_or_create_salt() -> bytes:
    """Récupère ou initialise un sel cryptographique aléatoire de 16 octets persistant."""
    base_dir = Path(AppConfig.get_db_path()).parent
    base_dir.mkdir(parents=True, exist_ok=True)
    salt_file = base_dir / _SALT_FILE_NAME

    if salt_file.exists():
        try:
            salt = salt_file.read_bytes()
            if len(salt) == 16:
                return salt
        except Exception:
            pass

    new_salt = os.urandom(16)
    try:
        salt_file.write_bytes(new_salt)
        if os.name == "nt":
            # Attribut caché sur Windows
            import ctypes

            ctypes.windll.kernel32.SetFileAttributesW(str(salt_file), 0x02)  # FILE_ATTRIBUTE_HIDDEN
    except Exception as e:
        logger.debug(f"Impossible de sauvegarder le sel cryptographique : {e}")
    return new_salt


def _derive_aes_key() -> bytes:
    """Dérive une clé AES-256 (32 octets) via PBKDF2-HMAC-SHA256."""
    global _CACHE_KEY
    if _CACHE_KEY is not None:
        return _CACHE_KEY

    salt = _get_or_create_salt()
    secret = _get_machine_identifier()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    _CACHE_KEY = kdf.derive(secret)
    return _CACHE_KEY


def _dpapi_decrypt(enc_bytes: bytes) -> Optional[bytes]:
    """Déchiffre des octets via Windows DPAPI (CryptUnprotectData)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(enc_bytes, len(enc_bytes))
        in_blob = DATA_BLOB(len(enc_bytes), buf)
        out_blob = DATA_BLOB()
        if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)):
            try:
                return ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None
    return None


def encrypt_data(raw_data: Union[bytes, str]) -> str:
    """Chiffre une donnée avec AES-256-GCM.

    Format retourné : 'gcm:<nonce_b64>:<ciphertext_b64>'
    """
    if isinstance(raw_data, str):
        raw_bytes = raw_data.encode("utf-8")
    else:
        raw_bytes = raw_data

    key = _derive_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce standard pour GCM
    ciphertext = aesgcm.encrypt(nonce, raw_bytes, None)

    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    cipher_b64 = base64.b64encode(ciphertext).decode("ascii")
    return f"gcm:{nonce_b64}:{cipher_b64}"


def decrypt_data(payload: Union[str, bytes]) -> Optional[bytes]:
    """Déchiffre un payload chiffré (gcm:, dpapi: ou enc:).

    Retourne les octets déchiffrés ou None si échec.
    """
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None

    if not isinstance(payload, str) or not payload:
        return None

    # 1. Format moderne AES-256-GCM
    if payload.startswith("gcm:"):
        parts = payload.split(":", 2)
        if len(parts) == 3:
            try:
                nonce = base64.b64decode(parts[1])
                ciphertext = base64.b64decode(parts[2])
                key = _derive_aes_key()
                aesgcm = AESGCM(key)
                return aesgcm.decrypt(nonce, ciphertext, None)
            except Exception as e:
                logger.error(f"Échec du déchiffrement AES-GCM : {e}")
                return None

    # 2. Format historique DPAPI
    if payload.startswith("dpapi:"):
        try:
            enc_raw = base64.b64decode(payload[6:])
            return _dpapi_decrypt(enc_raw)
        except Exception:
            return None

    # 3. Format historique Base64 simple
    if payload.startswith("enc:"):
        try:
            return base64.b64decode(payload[4:])
        except Exception:
            return None

    return None


def encrypt_dict(data: Dict[str, Any]) -> str:
    """Sérialise en JSON et chiffre un dictionnaire en AES-256-GCM."""
    raw_json = json.dumps(data or {}).encode("utf-8")
    return encrypt_data(raw_json)


def decrypt_to_dict(payload: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """Déchiffre un payload et le désérialise en dictionnaire Python."""
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}

    decrypted_bytes = decrypt_data(payload)
    if decrypted_bytes is not None:
        try:
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception:
            return {}

    # Si c'est du JSON en clair direct (ex: base non chiffrée initiale)
    if isinstance(payload, str) and payload.strip().startswith("{"):
        try:
            return json.loads(payload)
        except Exception:
            return {}

    return {}
