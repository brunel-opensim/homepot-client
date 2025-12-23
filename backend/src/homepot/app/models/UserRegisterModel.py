"""Database models for HOMEPOT Client.

This module re-exports the User model from the main homepot.models module
to maintain backward compatibility while avoiding duplicate model definitions.
"""

from homepot.models import User

__all__ = ["User"]
