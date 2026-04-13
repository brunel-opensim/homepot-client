"""Device model export for app-layer imports.

This module follows the app/models folder structure while reusing the canonical
SQLAlchemy Device model declared in homepot.models to avoid duplicate tables.
"""

from homepot.models import Base, Device

__all__ = ["Base", "Device"]

