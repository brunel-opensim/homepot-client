"""Canonical identifier generation for sites and devices.

Both site and device IDs use the same unambiguous uppercase alphabet
(``A-HJ-KM-NP-Z2-9``, excluding the easily-confused characters ``0/O``
and ``1/I/L``) so they can be read aloud and typed without errors during
device enrollment.

Formats
-------
* Site:   ``SITE-XXXX-XXXX``
* Device: ``DEVICE-XXXX-XXXX-XXXX``
"""

import re
import secrets
from typing import List

# Unambiguous alphabet: excludes 0/O, 1/I/L.
_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
# Character class form of the alphabet for regexes.
_ID_CHARS = "A-HJ-KM-NP-Z2-9"

_GROUP_LENGTH = 4

_SITE_ID_PATTERN = re.compile(
    rf"^SITE-[{_ID_CHARS}]{{{_GROUP_LENGTH}}}-[{_ID_CHARS}]{{{_GROUP_LENGTH}}}$"
)
_DEVICE_ID_PATTERN = re.compile(
    rf"^DEVICE-[{_ID_CHARS}]{{{_GROUP_LENGTH}}}-[{_ID_CHARS}]{{{_GROUP_LENGTH}}}"
    rf"-[{_ID_CHARS}]{{{_GROUP_LENGTH}}}$"
)


def _generate_group() -> str:
    """Return a single group of unambiguous uppercase alphanumerics."""
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(_GROUP_LENGTH))


def _canonical_id(prefix: str, groups: int) -> str:
    """Generate ``PREFIX-XXXX-...`` with ``groups`` groups of 4 chars."""
    parts: List[str] = [_generate_group() for _ in range(groups)]
    return f"{prefix}-{'-'.join(parts)}"


def generate_site_id() -> str:
    """Generate a canonical site ID: ``SITE-XXXX-XXXX``."""
    return _canonical_id("SITE", 2)


def generate_device_id() -> str:
    """Generate a canonical device ID: ``DEVICE-XXXX-XXXX-XXXX``."""
    return _canonical_id("DEVICE", 3)
