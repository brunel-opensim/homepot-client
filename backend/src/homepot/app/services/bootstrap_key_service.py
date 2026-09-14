"""Stored bootstrap keys: encrypted-at-rest plaintext + bcrypt verification.

Device bootstrap uses ``Site.bootstrap_key_hash`` (bcrypt) for enrolment, and
operators can now retrieve the plaintext key again via the API so they can
reuse it on the User App for additional devices. The plaintext is stored in
``Site.bootstrap_key_enc`` encrypted at rest with Fernet, keyed from the
server auth secret, so a database leak does not expose usable keys without
also compromising the server key.
"""

import base64
import hashlib
from typing import Optional, cast

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext

from homepot.config import get_secret_key
from homepot.models import Site

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _fernet() -> Fernet:
    """Build a Fernet cipher keyed from the server auth secret."""
    digest = hashlib.sha256(get_secret_key().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_plaintext_key(plaintext: str) -> str:
    """Encrypt a plaintext bootstrap key for storage at rest."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_ciphertext_key(ciphertext: str) -> Optional[str]:
    """Decrypt a stored bootstrap key, returning ``None`` on failure."""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def store_bootstrap_key(site: Site, plaintext: str) -> None:
    """Store a site bootstrap key as a bcrypt hash plus encrypted plaintext.

    The hash keeps existing device enrolment verification unchanged; the
    encrypted value lets operators re-display the key without regenerating.
    """
    site.bootstrap_key_hash = pwd_context.hash(plaintext)  # type: ignore[assignment]
    site.bootstrap_key_enc = encrypt_plaintext_key(plaintext)  # type: ignore[assignment]


def clear_bootstrap_key(site: Site) -> None:
    """Drop both the verification hash and the stored encryption."""
    site.bootstrap_key_hash = None  # type: ignore[assignment]
    site.bootstrap_key_enc = None  # type: ignore[assignment]


def reveal_bootstrap_key(site: Site) -> Optional[str]:
    """Return the stored plaintext key, or ``None`` when unset/unreadable."""
    ciphertext = cast(Optional[str], site.bootstrap_key_enc)
    if not ciphertext:
        return None
    return decrypt_ciphertext_key(ciphertext)
