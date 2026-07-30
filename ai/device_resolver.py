"""Service for resolving public Device UUIDs to internal Integer IDs."""

from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homepot.models import Device


class DeviceResolver:
    """Helper to resolve string UUIDs to integer PKs with caching within a session scope."""

    def __init__(self, session: AsyncSession):
        """Initialize the resolver with a database session.

        Args:
            session: The async database session to use for queries.
        """
        self.session = session
        self._cache: Dict[str, int] = {}

    async def resolve(self, device_id_str: str) -> Optional[int]:
        """Resolve a device UUID string to its internal integer ID.

        Args:
            device_id_str: The public UUID of the device.

        Returns:
            The internal integer ID, or None if not found.
        """
        if not device_id_str:
            return None

        if device_id_str in self._cache:
            return self._cache[device_id_str]

        stmt = select(Device.id).where(Device.device_id == device_id_str)
        result = await self.session.execute(stmt)
        device_int_id = result.scalar_one_or_none()

        if device_int_id:
            self._cache[device_id_str] = device_int_id

        return device_int_id
