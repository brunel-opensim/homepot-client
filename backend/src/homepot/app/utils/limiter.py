"""Rate Limiting Utilities for the HomePot system."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize the limiter to use the client's IP address
limiter = Limiter(key_func=get_remote_address)
