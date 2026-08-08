"""Security helpers: Fernet encryption for credential secrets + log redaction."""
from __future__ import annotations

import os
import re

from cryptography.fernet import Fernet, InvalidToken

from .config import SECRET_KEY_PATH, ensure_dirs

_fernet: Fernet | None = None


def _load_or_create_key() -> bytes:
    env_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if env_key:
        return env_key.encode()
    ensure_dirs()
    if SECRET_KEY_PATH.exists():
        return SECRET_KEY_PATH.read_bytes().strip()
    key = Fernet.generate_key()
    # write with 0600 permissions
    fd = os.open(SECRET_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_secret(plain: str) -> str:
    return get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("无法解密 credential secret（密钥不匹配？）") from e


def mask_secret(plain: str) -> str:
    """'****ab12' style mask — last 4 chars only."""
    if not plain:
        return "****"
    return "****" + plain[-4:]


_SK_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]+")


def redact(text: str) -> str:
    """Redact API-key-looking tokens in log text: 'sk-****<last4>'."""
    if not text:
        return text

    def _sub(m: re.Match) -> str:
        token = m.group(0)
        return f"sk-****{token[-4:]}"

    return _SK_RE.sub(_sub, text)


def redact_value(value):
    """Recursively redact secrets in arbitrary JSON-ish values."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: ("****" if k.lower() in {"api_key", "secret", "secret_encrypted"} else redact_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    return value
