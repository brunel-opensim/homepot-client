"""Repository layer for agent device and telemetry database operations."""

from datetime import datetime
from typing import Any, Iterable, Optional, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.models.AnalyticsModel import DeviceMetrics
from homepot.models import Device, Site


class AgentRepository:
    """Repository class encapsulating SQLAlchemy operations for agent workflows."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with an active SQLAlchemy session."""
        self.db = db

    def get_device_by_device_id(self, device_id: str) -> Optional[Device]:
        """Return a device by business device_id, or None if it does not exist."""
        result = self.db.execute(select(Device).where(Device.device_id == device_id))
        return result.scalars().first()

    def get_site_by_site_id(self, site_id: str) -> Optional[Site]:
        """Return a site by business site_id, or None if not found."""
        result = self.db.execute(select(Site).where(Site.site_id == site_id))
        return result.scalars().first()

    def create_device(
        self,
        *,
        device_id: str,
        name: str,
        device_type: str,
        site_pk: int,
        mac_address: Optional[str],
        os_details: Optional[str],
        local_ip: Optional[str],
        wan_ip: Optional[str],
    ) -> Device:
        """Create and persist a new device record."""
        device = Device(
            device_id=device_id,
            name=name,
            device_type=device_type,
            site_id=site_pk,
            mac_address=mac_address,
            os_details=os_details,
            local_ip=local_ip,
            wan_ip=wan_ip,
            is_active=True,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update_device_registration(
        self,
        device: Device,
        *,
        mac_address: Optional[str],
        os_details: Optional[str],
        local_ip: Optional[str],
        wan_ip: Optional[str],
    ) -> Device:
        """Update device DNA fields during registration."""
        device_obj = cast(Any, device)
        device_obj.mac_address = mac_address
        device_obj.os_details = os_details
        device_obj.local_ip = local_ip
        device_obj.wan_ip = wan_ip
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update_last_heartbeat(self, device: Device, heartbeat_at: datetime) -> Device:
        """Update the latest heartbeat timestamp for a device."""
        cast(Any, device).last_heartbeat_at = heartbeat_at
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def save_device(self, device: Device) -> Device:
        """Persist generic device changes and return refreshed entity."""
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def save_telemetry_entry(
        self,
        *,
        device_pk: int,
        cpu_usage: float,
        memory_usage: float,
        disk_usage: float,
        timestamp: datetime,
    ) -> DeviceMetrics:
        """Persist a single telemetry entry for a device."""
        metric = DeviceMetrics(
            device_id=device_pk,
            cpu_percent=cpu_usage,
            memory_percent=memory_usage,
            disk_percent=disk_usage,
            timestamp=timestamp,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def save_telemetry_bulk(
        self, *, device_pk: int, entries: Iterable[dict]
    ) -> list[DeviceMetrics]:
        """Persist multiple telemetry entries for a device."""
        metrics: list[DeviceMetrics] = []
        for entry in entries:
            metric = DeviceMetrics(
                device_id=device_pk,
                cpu_percent=entry["cpu_usage"],
                memory_percent=entry["memory_usage"],
                disk_percent=entry["disk_usage"],
                timestamp=entry["timestamp"],
            )
            metrics.append(metric)

        self.db.add_all(metrics)
        self.db.commit()

        for metric in metrics:
            self.db.refresh(metric)

        return metrics
