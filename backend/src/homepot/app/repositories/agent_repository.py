"""Repository layer for agent device and telemetry database operations."""

from datetime import datetime
from typing import Any, Iterable, Optional, cast

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from homepot.app.models.AnalyticsModel import DeviceMetrics
from homepot.app.schemas.permissions import derive_capabilities
from homepot.models import (
    ConnectivityState,
    Device,
    DeviceStatus,
    HealthState,
    LifecycleState,
    Site,
)


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

    def device_name_exists_in_site(self, site_pk: int, name: str) -> bool:
        """Return True if a live device in the site already uses this name.

        Matching is case-insensitive and whitespace-trimmed. Retired and
        unpaired devices are excluded so names can be reused after a device
        is decommissioned.
        """
        active_states = [
            LifecycleState.PENDING.value,
            LifecycleState.ACTIVE.value,
            LifecycleState.SUSPENDED.value,
        ]
        result = self.db.execute(
            select(Device).where(
                Device.site_id == site_pk,
                func.lower(Device.name) == name.strip().lower(),
                Device.lifecycle_state.in_(active_states),
            )
        )
        return result.scalars().first() is not None

    def get_latest_metrics(self, device_pk: int) -> Optional[DeviceMetrics]:
        """Return the most recent telemetry entry for a device, or None."""
        result = self.db.execute(
            select(DeviceMetrics)
            .where(DeviceMetrics.device_id == device_pk)
            .order_by(desc(DeviceMetrics.timestamp))
            .limit(1)
        )
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
        ip_address: Optional[str] = None,
        firmware_version: Optional[str] = None,
        lifecycle_state: str = LifecycleState.ACTIVE.value,
        enrollment_method: Optional[str] = None,
        is_simulated: bool = False,
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
            ip_address=ip_address,
            firmware_version=firmware_version,
            is_active=True,
            lifecycle_state=lifecycle_state,
            enrollment_method=enrollment_method,
            is_simulated=is_simulated,
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
        ip_address: Optional[str] = None,
        firmware_version: Optional[str] = None,
        peripherals: Optional[dict] = None,
    ) -> Device:
        """Update device DNA fields during registration."""
        device_obj = cast(Any, device)
        device_obj.mac_address = mac_address
        device_obj.os_details = os_details
        device_obj.capabilities = derive_capabilities(os_details)
        device_obj.local_ip = local_ip
        device_obj.wan_ip = wan_ip
        if ip_address is not None:
            device_obj.ip_address = ip_address
        if firmware_version is not None:
            device_obj.firmware_version = firmware_version
        if peripherals is not None:
            device_obj.peripherals = peripherals
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update_last_heartbeat(
        self, device: Device, heartbeat_at: datetime, *, online: bool = True
    ) -> Device:
        """Record a device heartbeat.

        ``online=False`` is a graceful-shutdown signal: the device is marked
        OFFLINE and its heartbeat timestamp cleared so connectivity reflects
        the offline state immediately instead of waiting out the online window.
        """
        cast(Any, device).last_seen = heartbeat_at
        if not online:
            cast(Any, device).last_heartbeat_at = None
            cast(Any, device).status = DeviceStatus.OFFLINE.value
            cast(Any, device).health_state = HealthState.ERROR.value
        else:
            cast(Any, device).last_heartbeat_at = heartbeat_at
            cast(Any, device).status = ConnectivityState.ONLINE.value
            cast(Any, device).health_state = HealthState.HEALTHY.value
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
        uptime_seconds: int | None = None,
        network_latency_ms: float | None = None,
        provenance: str | None = None,
        collection_interval_seconds: int | None = None,
    ) -> DeviceMetrics:
        """Persist a single telemetry entry for a device."""
        metric = DeviceMetrics(
            device_id=device_pk,
            cpu_percent=cpu_usage,
            memory_percent=memory_usage,
            disk_percent=disk_usage,
            timestamp=timestamp,
            network_latency_ms=network_latency_ms,
            provenance=provenance,
            collection_interval_seconds=collection_interval_seconds,
            extra_metrics=(
                {"uptime_seconds": uptime_seconds}
                if uptime_seconds is not None
                else None
            ),
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def save_telemetry_bulk(
        self,
        *,
        device_pk: int,
        entries: Iterable[dict],
        provenance: str | None = None,
        collection_interval_seconds: int | None = None,
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
                network_latency_ms=entry.get("network_latency_ms"),
                provenance=provenance,
                collection_interval_seconds=collection_interval_seconds,
                extra_metrics=(
                    {"uptime_seconds": entry["uptime_seconds"]}
                    if entry.get("uptime_seconds") is not None
                    else None
                ),
            )
            metrics.append(metric)

        self.db.add_all(metrics)
        self.db.commit()

        for metric in metrics:
            self.db.refresh(metric)

        return metrics
