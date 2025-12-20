"""Database models for HOMEPOT Client.

This module re-exports the User model and Base from the main homepot.models module
to maintain backward compatibility while avoiding duplicate model definitions.
"""

from homepot.models import Base, User

__all__ = ["Base", "User"]
