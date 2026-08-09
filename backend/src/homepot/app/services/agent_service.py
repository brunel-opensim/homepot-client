"""Service layer for agent registration, heartbeat, telemetry, and provisioning."""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, Sequence, cast
import uuid

from sqlalchemy.orm import Session

from homepot.app.auth_utils import hash_password
from homepot.app.repositories.agent_repository import AgentRepository
from homepot.app.schemas.agent import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentTelemetryRequest,
)
from homepot.app.schemas.bootstrap import BootstrapProvisionRequest
from homepot.app.schemas.permissions import derive_capabilities, derive_push_channel
from homepot.app.schemas.provision import DeviceProvisionRequest
from homepot.app.services.lifecycle_service import LifecycleService
from homepot.canonical_ids import generate_device_id
from homepot.models import (
    ConnectivityState,
    DeviceCredential,
    EnrollmentMethod,
    HealthState,
    LifecycleEpoch,
    LifecycleState,
)


def _utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def _generate_unique_device_id(repository: AgentRepository) -> str:
    """Generate a canonical, collision-free device ID."""
    device_id = generate_device_id()
    while repository.get_device_by_device_id(device_id):
        device_id = generate_device_id()
    return device_id


class AgentService:
    """Service class that contains business logic for agent APIs."""

    def __init__(self, db: Session) -> None:
        """Initialize service with a database-backed repository."""
        self.db = db
        self.repository = AgentRepository(db)
        self.lifecycle = LifecycleService(db)

    def update_device(self, payload: AgentRegisterRequest) -> dict:
        """Update existing device DNA or create a new device."""
        try:
            device = self.repository.get_device_by_device_id(payload.device_id)

            if device:
                if device.lifecycle_state == LifecycleState.PENDING.value:
                    self.lifecycle.transition(
                        device,
                        LifecycleState.ACTIVE,
                        changed_by=f"device:{payload.device_id}",
                        reason="Device registration completed",
                    )

                updated = self.repository.update_device_registration(
                    device=device,
                    mac_address=payload.mac_address,
                    os_details=payload.os_details,
                    local_ip=payload.local_ip,
                    wan_ip=payload.wan_ip,
                    ip_address=payload.local_ip,
                    firmware_version=payload.firmware_version,
                    peripherals=payload.peripherals,
                )

                if payload.device_token is not None:
                    updated_obj = cast(Any, updated)
                    updated_obj.push_token = payload.device_token
                    updated_obj.push_channel = derive_push_channel(payload.os_details)
                    self.repository.save_device(updated)

                if payload.device_source:
                    updated_obj = cast(Any, updated)
                    existing_config: Dict[str, Any] = dict(
                        cast(Dict[str, Any], updated_obj.config or {})
                    )
                    existing_config["device_source"] = payload.device_source
                    updated_obj.config = existing_config
                    self.repository.save_device(updated)

                return {
                    "device_id": updated.device_id,
                    "site_id": updated.site.site_id if updated.site else None,
                    "lifecycle_state": updated.lifecycle_state,
                    "mac_address": updated.mac_address,
                    "os_details": updated.os_details,
                    "local_ip": updated.local_ip,
                    "wan_ip": updated.wan_ip,
                    "peripherals": updated.peripherals,
                    "created": False,
                }

            if not payload.site_id:
                raise ValueError("site_id is required to create a new device")

            site = self.repository.get_site_by_site_id(payload.site_id)
            if not site or not site.id:
                raise LookupError(f"Site '{payload.site_id}' not found")

            is_emulator_dna = payload.device_source == "emulator"
            created = self.repository.create_device(
                device_id=payload.device_id,
                name=payload.device_name or payload.device_id,
                device_type=payload.device_type,
                site_pk=int(site.id),
                mac_address=payload.mac_address,
                os_details=payload.os_details,
                local_ip=payload.local_ip,
                wan_ip=payload.wan_ip,
                ip_address=payload.local_ip,
                firmware_version=payload.firmware_version,
                lifecycle_state=LifecycleState.ACTIVE.value,
                enrollment_method=(
                    EnrollmentMethod.EMULATED.value if is_emulator_dna else None
                ),
                is_simulated=is_emulator_dna,
            )

            created_obj = cast(Any, created)
            created_obj.capabilities = derive_capabilities(payload.os_details)

            if is_emulator_dna:
                existing_config = dict(cast(Dict[str, Any], created_obj.config or {}))
                existing_config["device_source"] = "emulator"
                created_obj.config = existing_config

            if payload.device_token is not None:
                created_obj.push_token = payload.device_token
                created_obj.push_channel = derive_push_channel(payload.os_details)

            self.repository.save_device(created)

            return {
                "device_id": created.device_id,
                "site_id": site.site_id,
                "lifecycle_state": created.lifecycle_state,
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

            self.lifecycle.assert_active(device)

            updated = self.repository.update_last_heartbeat(device, payload.timestamp)
            return {
                "device_id": updated.device_id,
                "last_heartbeat_at": (
                    updated.last_heartbeat_at.isoformat()
                    if updated.last_heartbeat_at
                    else payload.timestamp.isoformat()
                ),
            }
        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(str(e))
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
                    uptime_seconds=payload.uptime_seconds,
                    network_latency_ms=payload.network_latency_ms,
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
                    "uptime_seconds": item.uptime_seconds,
                    "network_latency_ms": item.network_latency_ms,
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

    def provision_device(
        self, payload: DeviceProvisionRequest, provisioned_by: str
    ) -> dict:
        """Provision a new device and return one-time credentials.

        Uses the authenticated user's identity (``provisioned_by``) instead
        of the caller-provided ``payload.user_identity``.  Atomically creates
        the device, a lifecycle epoch, and device credentials.
        """
        try:
            site = self.repository.get_site_by_site_id(payload.site_id)
            if not site or not site.id:
                raise LookupError(f"Site '{payload.site_id}' not found")

            device_id = _generate_unique_device_id(self.repository)
            api_key = secrets.token_urlsafe(32)
            device_token = secrets.token_urlsafe(24)

            created = self.repository.create_device(
                device_id=device_id,
                name=payload.device_name or device_id,
                device_type=payload.device_type,
                site_pk=int(site.id),
                mac_address=None,
                os_details=payload.os_details,
                local_ip=None,
                wan_ip=None,
                lifecycle_state=LifecycleState.PENDING.value,
                enrollment_method=EnrollmentMethod.SELF_ENROLLED.value,
            )

            created_obj = cast(Any, created)
            created_obj.api_key_hash = hash_password(api_key)
            created_obj.capabilities = derive_capabilities(payload.os_details)

            existing_config: Dict[str, Any] = dict(
                cast(Dict[str, Any], created_obj.config or {})
            )
            existing_config.update(
                {
                    "provisioned_by": provisioned_by,
                    "provisioning_method": (
                        "sso" if payload.sso_token else "manual_identity"
                    ),
                    "os": payload.os_details,
                    "device_token": device_token,
                }
            )
            created_obj.config = existing_config
            created_obj.last_heartbeat_at = None

            self.repository.save_device(created)

            # Create lifecycle epoch for the self-enrolment
            epoch_id = str(uuid.uuid4())
            epoch = LifecycleEpoch(
                epoch_id=epoch_id,
                device_id=created.id,
                site_id=site.id,
                tenant_id=site.tenant_id,
                claimed_at=_utc_now(),
                enrolment_method=EnrollmentMethod.SELF_ENROLLED.value,
            )
            self.db.add(epoch)
            self.db.flush()

            created.lifecycle_epoch_id = epoch.id  # type: ignore[assignment]

            # Create tracked credential record
            credential_id = str(uuid.uuid4())
            credential = DeviceCredential(
                credential_id=credential_id,
                device_id=created.id,
                key_hash=hash_password(api_key),
                is_active=True,
            )
            self.db.add(credential)

            # Transition from PENDING to ACTIVE with audit trail
            self.lifecycle.transition(
                created,
                LifecycleState.ACTIVE,
                changed_by=f"user:{provisioned_by}",
                reason="Self-enrolment via provision endpoint",
            )

            return {
                "device_id": created.device_id,
                "api_key": api_key,
                "secret_key": api_key,
                "device_token": device_token,
                "site_id": site.site_id,
                "created_at": created.created_at,
                "epoch_id": epoch_id,
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid provision request: {str(e)}")
        except Exception:
            raise Exception("Failed to provision device")

    def bootstrap_provision_device(self, payload: BootstrapProvisionRequest) -> dict:
        """Provision a new device authenticated by site bootstrap key.

        Similar to ``provision_device`` but uses a bootstrap key for
        authentication instead of an SSO user identity.  The device
        is created directly in ACTIVE state with credentials.
        """
        try:
            site = self.repository.get_site_by_site_id(payload.site_id)
            if not site or not site.id:
                raise LookupError(f"Site '{payload.site_id}' not found")

            device_id = _generate_unique_device_id(self.repository)
            api_key = secrets.token_urlsafe(32)

            requested_name = (payload.device_name or "").strip() or device_id
            if self.repository.device_name_exists_in_site(int(site.id), requested_name):
                raise ValueError(
                    f"Device name '{requested_name}' is already in use in site "
                    f"'{payload.site_id}'. Choose a different device name."
                )

            is_emulator = payload.provisioning_source == "emulator"
            created = self.repository.create_device(
                device_id=device_id,
                name=requested_name,
                device_type=payload.device_type,
                site_pk=int(site.id),
                mac_address=None,
                os_details=payload.os_details,
                local_ip=None,
                wan_ip=None,
                lifecycle_state=LifecycleState.PENDING.value,
                enrollment_method=(
                    EnrollmentMethod.EMULATED.value
                    if is_emulator
                    else EnrollmentMethod.SELF_ENROLLED.value
                ),
                is_simulated=is_emulator,
            )

            created_obj = cast(Any, created)
            created_obj.api_key_hash = hash_password(api_key)
            created_obj.capabilities = derive_capabilities(payload.os_details)

            existing_config: Dict[str, Any] = dict(
                cast(Dict[str, Any], created_obj.config or {})
            )
            existing_config.update(
                {
                    "provisioning_method": "bootstrap_key",
                    "os": payload.os_details,
                }
            )
            if is_emulator:
                existing_config["device_source"] = "emulator"
            created_obj.config = existing_config
            created_obj.last_heartbeat_at = None

            self.repository.save_device(created)

            epoch_id = str(uuid.uuid4())
            epoch = LifecycleEpoch(
                epoch_id=epoch_id,
                device_id=created.id,
                site_id=site.id,
                tenant_id=site.tenant_id,
                claimed_at=_utc_now(),
                enrolment_method=EnrollmentMethod.SELF_ENROLLED.value,
            )
            self.db.add(epoch)
            self.db.flush()

            created.lifecycle_epoch_id = epoch.id

            credential_id = str(uuid.uuid4())
            credential = DeviceCredential(
                credential_id=credential_id,
                device_id=created.id,
                key_hash=hash_password(api_key),
                is_active=True,
            )
            self.db.add(credential)

            self.lifecycle.transition(
                created,
                LifecycleState.ACTIVE,
                changed_by="device:bootstrap",
                reason="Self-enrolment via bootstrap key",
            )

            return {
                "device_id": created.device_id,
                "api_key": api_key,
                "site_id": site.site_id,
                "created_at": created.created_at,
                "epoch_id": epoch_id,
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid bootstrap provision request: {str(e)}")
        except Exception:
            raise Exception("Failed to bootstrap provision device")

    def device_name_available(self, site_id: str, name: str) -> bool:
        """Return True if the name is not used by a live device in the site."""
        site = self.repository.get_site_by_site_id(site_id)
        if not site or not site.id:
            raise LookupError(f"Site '{site_id}' not found")
        return not self.repository.device_name_exists_in_site(
            int(site.id), name.strip()
        )

    def get_device_status(self, device_id: str) -> dict:
        """Return lifecycle, connectivity, and health state for a device."""
        try:
            device = self.repository.get_device_by_device_id(device_id)
            if not device:
                raise LookupError(f"Device '{device_id}' not found")

            heartbeat = device.last_heartbeat_at

            if not heartbeat:
                connectivity = ConnectivityState.UNKNOWN.value
            else:
                heartbeat_utc = heartbeat
                if heartbeat_utc.tzinfo is None:
                    heartbeat_utc = heartbeat_utc.replace(tzinfo=timezone.utc)
                current_time = _utc_now()
                is_online = (current_time - heartbeat_utc) <= timedelta(minutes=2)
                connectivity = (
                    ConnectivityState.ONLINE.value
                    if is_online
                    else ConnectivityState.OFFLINE.value
                )

            return {
                "device_id": device.device_id,
                "lifecycle_state": device.lifecycle_state
                or LifecycleState.PENDING.value,
                "connectivity_state": connectivity,
                "health_state": device.health_state or HealthState.UNKNOWN.value,
                "last_heartbeat_at": (heartbeat_utc.isoformat() if heartbeat else None),
            }

        except LookupError:
            raise
        except ValueError as e:
            raise ValueError(f"Invalid device status request: {str(e)}")
        except Exception:
            raise Exception("Failed to fetch device status")

    def get_latest_metrics(self, device_id: str) -> dict:
        """Return the most recent telemetry metrics for a device, or empty values."""
        try:
            device = self.repository.get_device_by_device_id(device_id)
            if not device or not device.id:
                raise LookupError(f"Device '{device_id}' not found")

            metric = self.repository.get_latest_metrics(device_pk=int(device.id))
            if metric is None:
                return {
                    "device_id": device.device_id,
                    "cpu_percent": None,
                    "memory_percent": None,
                    "disk_percent": None,
                    "network_latency_ms": None,
                    "uptime_seconds": None,
                    "timestamp": None,
                }

            extra_raw = metric.extra_metrics
            extra: Dict[str, Any] = (
                cast(Dict[str, Any], extra_raw) if isinstance(extra_raw, dict) else {}
            )
            return {
                "device_id": device.device_id,
                "cpu_percent": metric.cpu_percent,
                "memory_percent": metric.memory_percent,
                "disk_percent": metric.disk_percent,
                "network_latency_ms": metric.network_latency_ms,
                "uptime_seconds": extra.get("uptime_seconds"),
                "timestamp": metric.timestamp.isoformat(),
            }

        except LookupError:
            raise
        except Exception:
            raise Exception("Failed to fetch device metrics")
