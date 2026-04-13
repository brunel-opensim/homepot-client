"""Service layer for agent registration, heartbeat, telemetry, and provisioning."""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Sequence

from sqlalchemy.orm import Session

from homepot.app.auth_utils import hash_password
from homepot.app.repositories.agent_repository import AgentRepository
from homepot.app.schemas.agent import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentTelemetryRequest,
)
from homepot.app.schemas.provision import DeviceProvisionRequest


def _utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class AgentService:
    """Service class that contains business logic for agent APIs."""

    def __init__(self, db: Session) -> None:
        """Initialize service with a database-backed repository."""
        self.repository = AgentRepository(db)

    def update_device(self, payload: AgentRegisterRequest) -> dict:
        """Update existing device DNA or create a new device."""
        try:
            device = self.repository.get_device_by_device_id(payload.device_id)

            if device:
                updated = self.repository.update_device_registration(
                    device=device,
                    mac_address=payload.mac_address,
                    os_details=payload.os_details,
                    local_ip=payload.local_ip,
                    wan_ip=payload.wan_ip,
                )

                return {
                    "device_id": updated.device_id,
                    "site_id": updated.site.site_id if updated.site else None,
                    "mac_address": updated.mac_address,
                    "os_details": updated.os_details,
                    "local_ip": updated.local_ip,
                    "wan_ip": updated.wan_ip,
                    "created": False,
                }

            if not payload.site_id:
                raise ValueError("site_id is required to create a new device")

            site = self.repository.get_site_by_site_id(payload.site_id)
            if not site or not site.id:
                raise LookupError(f"Site '{payload.site_id}' not found")

            created = self.repository.create_device(
                device_id=payload.device_id,
                name=payload.device_name or payload.device_id,
                device_type=payload.device_type,
                site_pk=int(site.id),
                mac_address=payload.mac_address,
                os_details=payload.os_details,
                local_ip=payload.local_ip,
                wan_ip=payload.wan_ip,
            )

            return {
                "device_id": created.device_id,
                "site_id": site.site_id,
                "mac_address": created.mac_address,
                "os_details": created.os_details,
                "local_ip": created.local_ip,
                "wan_ip": created.wan_ip,
                "created": True,
            }

        except Exception as e:
            raise e

    def update_heartbeat(self, payload: AgentHeartbeatRequest) -> dict:
        """Update a device heartbeat timestamp and return heartbeat metadata."""
        try:
            device = self.repository.get_device_by_device_id(payload.device_id)
            if not device:
                raise LookupError(f"Device '{payload.device_id}' not found")

            updated = self.repository.update_last_heartbeat(device, payload.timestamp)
            return {
                "device_id": updated.device_id,
                "last_heartbeat_at": (
                    updated.last_heartbeat_at.isoformat()
                    if updated.last_heartbeat_at
                    else payload.timestamp.isoformat()
                ),
            }
        except Exception as e:
            raise e

    def save_telemetry(
        self,
        payload: AgentTelemetryRequest | Sequence[AgentTelemetryRequest],
    ) -> dict:
        """Store one or many telemetry records for a device."""
        try:
            if isinstance(payload, AgentTelemetryRequest):
                device = self.repository.get_device_by_device_id(payload.device_id)
                if not device or not device.id:
                    raise LookupError(f"Device '{payload.device_id}' not found")

                self.repository.save_telemetry_entry(
                    device_pk=int(device.id),
                    timestamp=payload.timestamp,
                    cpu_usage=payload.cpu_usage,
                    memory_usage=payload.memory_usage,
                    disk_usage=payload.disk_usage,
                )

                return {
                    "device_id": payload.device_id,
                    "saved_count": 1,
                }

            entries = list(payload)
            if not entries:
                raise ValueError("Telemetry payload list cannot be empty")

            first_device_id = entries[0].device_id
            if any(item.device_id != first_device_id for item in entries):
                raise ValueError("All telemetry entries must have the same device_id")

            device = self.repository.get_device_by_device_id(first_device_id)
            if not device or not device.id:
                raise LookupError(f"Device '{first_device_id}' not found")

            serialized_entries = [
                {
                    "cpu_usage": item.cpu_usage,
                    "memory_usage": item.memory_usage,
                    "disk_usage": item.disk_usage,
                    "timestamp": item.timestamp,
                }
                for item in entries
            ]

            self.repository.save_telemetry_bulk(
                device_pk=int(device.id),
                entries=serialized_entries,
            )

            return {
                "device_id": first_device_id,
                "saved_count": len(entries),
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid telemetry data: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to save telemetry: {str(e)}")

    def provision_device(self, payload: DeviceProvisionRequest) -> dict:
        """Provision a new device and return one-time credentials."""
        try:
            if not payload.user_identity.strip():
                raise ValueError("user_identity is required")

            site = self.repository.get_site_by_site_id(payload.site_id)
            if not site or not site.id:
                raise LookupError(f"Site '{payload.site_id}' not found")

            device_id = f"{payload.device_type}-{secrets.token_hex(4)}"
            api_key = secrets.token_urlsafe(32)
            device_token = secrets.token_urlsafe(24)

            created = self.repository.create_device(
                device_id=device_id,
                name=payload.device_name or device_id,
                device_type=payload.device_type,
                site_pk=int(site.id),
                mac_address=None,
                os_details=None,
                local_ip=None,
                wan_ip=None,
            )

            created.api_key_hash = hash_password(api_key)

            existing_config = created.config or {}
            existing_config.update(
                {
                    "provisioned_by": payload.user_identity,
                    "provisioning_method": (
                        "sso" if payload.sso_token else "manual_identity"
                    ),
                    "device_token": device_token,
                }
            )
            created.config = existing_config
            created.last_heartbeat_at = None

            self.repository.save_device(created)

            return {
                "device_id": created.device_id,
                "api_key": api_key,
                # Backward-compatible aliases for existing clients.
                "secret_key": api_key,
                "device_token": device_token,
                "site_id": site.site_id,
                "created_at": created.created_at,
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid provision request: {str(e)}")
        except Exception:
            raise Exception("Failed to provision device")

    def get_device_status(self, device_id: str) -> dict:
        """Return computed ONLINE/OFFLINE status based on heartbeat recency."""
        try:
            device = self.repository.get_device_by_device_id(device_id)
            if not device:
                raise LookupError(f"Device '{device_id}' not found")

            heartbeat = device.last_heartbeat_at
            if not heartbeat:
                return {
                    "device_id": device.device_id,
                    "last_heartbeat": None,
                    "status": "OFFLINE",
                }

            heartbeat_utc = heartbeat
            if heartbeat_utc.tzinfo is None:
                heartbeat_utc = heartbeat_utc.replace(tzinfo=timezone.utc)

            current_time = _utc_now()
            is_online = (current_time - heartbeat_utc) < timedelta(minutes=2)

            return {
                "device_id": device.device_id,
                "last_heartbeat": heartbeat_utc.isoformat(),
                "status": "ONLINE" if is_online else "OFFLINE",
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid device status request: {str(e)}")
        except Exception:
            raise Exception("Failed to fetch device status")
