"""Tests unitaires pour le module de cryptographie AES-256-GCM et le modèle AccountSession."""

import json
from src.core.crypto import (
    encrypt_data,
    decrypt_data,
    encrypt_dict,
    decrypt_to_dict,
)
from src.infrastructure.database.models import AccountSession


def test_encrypt_decrypt_raw_bytes():
    raw = b"SecretToken12345!@#"
    encrypted = encrypt_data(raw)
    assert encrypted.startswith("gcm:")
    decrypted = decrypt_data(encrypted)
    assert decrypted == raw


def test_encrypt_decrypt_string():
    raw_str = "Texte_confidentiel_avec_accents_éàç"
    encrypted = encrypt_data(raw_str)
    assert encrypted.startswith("gcm:")
    decrypted = decrypt_data(encrypted)
    assert decrypted is not None
    assert decrypted.decode("utf-8") == raw_str


def test_encrypt_decrypt_dict():
    data = {
        "session_id": "abc-987-xyz",
        "member_id": 123456,
        "is_supporter": True,
        "tokens": ["tok1", "tok2"],
    }
    encrypted = encrypt_dict(data)
    assert encrypted.startswith("gcm:")
    decrypted = decrypt_to_dict(encrypted)
    assert decrypted == data


def test_decrypt_invalid_payload():
    assert decrypt_data("") is None
    assert decrypt_data("not_an_encrypted_payload") is None
    assert decrypt_data("gcm:invalid_nonce:invalid_cipher") is None
    assert decrypt_to_dict("corrupted_payload") == {}


def test_decrypt_legacy_formats():
    import base64

    # 1. Test legacy base64 'enc:' prefix
    raw_dict = {"ips4_member_id": "42", "ips4_IPSSessionFront": "xyz"}
    raw_json = json.dumps(raw_dict).encode("utf-8")
    legacy_enc = f"enc:{base64.b64encode(raw_json).decode('ascii')}"

    decrypted = decrypt_to_dict(legacy_enc)
    assert decrypted == raw_dict

    # 2. Test raw unencrypted json
    raw_json_str = json.dumps(raw_dict)
    assert decrypt_to_dict(raw_json_str) == raw_dict


def test_account_session_model_encryption():
    session = AccountSession(provider_name="loverslab")
    cookies = {"ips4_IPSSessionFront": "abc12345", "ips4_hasAcceptedAge": "1"}

    session.set_cookies_dict(cookies)
    assert isinstance(session.cookies_data, str)
    assert session.cookies_data.startswith("gcm:")

    restored = session.get_cookies_dict()
    assert restored == cookies
