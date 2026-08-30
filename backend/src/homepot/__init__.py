"""HOMEPOT Client - Homogenous Cyber Management of End-Points and OT.

This package provides a unified client system for managing and communicating
with diverse end-points and operational technology devices across different
platforms.

The HOMEPOT Client is designed for:
- Retail operations (POS systems, inventory management)
- Hospitality management (room automation, guest services)
- Industrial control (manufacturing systems, process control)

Copyright 2025 HOMEPOT Consortium
Licensed under the Apache License, Version 2.0
"""

__version__ = "0.1.0"
__author__ = "HOMEPOT Consortium"
__email__ = "contact@homepot-consortium.org"
__license__ = "Apache-2.0"

# passlib 1.7.4 reads `bcrypt.__about__.__version__` to detect the bcrypt
# backend, but bcrypt >= 4.1 removed the private `__about__` module. Without
# this shim passlib traps an AttributeError and logs a warning on first use.
try:
    import types as _types

    import bcrypt as _bcrypt

    if not hasattr(_bcrypt, "__about__"):
        setattr(
            _bcrypt,
            "__about__",
            _types.SimpleNamespace(
                __version__=getattr(_bcrypt, "__version__", "4.1.3")
            ),
        )
except ImportError:
    pass

# Package metadata
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
]
