# Mobivisor Integration Roadmap & Architecture

**Status**: Draft  
**Target Audience**: Consortium Members (Dealdio, Brunel OpenSim), Developers  
**Goal**: Achieve seamless, vendor-agnostic integration between HOMEPOT and Mobivisor.

---

## 1. Executive Summary

HOMEPOT Client is built on a **Modular Framework** designed to support multiple device management APIs. While it provides a robust "Generic API" out of the box, its architecture allows for plug-and-play integration with external providers like Mobivisor.

The goal of this roadmap is to evolve the current Mobivisor integration from a simple "Proxy" model to a full "Platform Integration." This will allow HOMEPOT users to leverage core features (Analytics, Jobs, AI Agents) on Mobivisor-managed devices while ensuring the HOMEPOT Generic API remains independent and robust.

**Key Principles:**
1.  **Modular Architecture**: The system uses an Adapter pattern to support any external provider (Mobivisor, Azure IoT, etc.) without changing core code.
2.  **Vendor Isolation**: The core system must not depend on Mobivisor availability.
3.  **Seamless Experience**: Users should see a unified list of devices, regardless of source.
4.  **Graceful Degradation**: If the external service is removed, local data remains accessible.

---

## 2. Architecture Strategy

### 2.1 The "Shadow Device" Concept
To enable HOMEPOT features on external devices, we will "sync" them into the local database as **Shadow Records**.

*   **Local Devices**: Managed fully by HOMEPOT.
*   **Shadow Devices**: Managed by Mobivisor, but mirrored in HOMEPOT for analytics and reporting.

### 2.2 Database Schema (Vendor-Agnostic)
We will avoid adding vendor-specific columns (e.g., `mobivisor_id`) to the core `devices` table. Instead, we use a generic approach.

**Proposed Schema Changes:**

```python
class Device(Base):
    # ... existing fields ...
    
    # Source of the device record
    source = Column(String(20), default="LOCAL")  # Enum: 'LOCAL', 'EXTERNAL'
    
    # Generic container for external provider details
    # Example: {"provider": "mobivisor", "external_id": "12345", "sync_status": "active"}
    integration_metadata = Column(JSON, nullable=True) 
```

### 2.3 The Adapter Pattern
The backend will use an Interface/Adapter pattern to communicate with external providers. This ensures the core logic (Orchestrator) never imports Mobivisor-specific code directly.

**Interface Definition:**
```python
class ExternalDeviceProvider(ABC):
    @abstractmethod
    async def sync_devices(self) -> List[DeviceData]:
        """Fetch all devices from external source."""
        pass

    @abstractmethod
    async def execute_command(self, device_id: str, command: str, params: Dict) -> bool:
        """Execute a command (e.g., reboot, lock) on the external device."""
        pass
```

---

## 3. Implementation Roadmap

### Phase 1: Foundation (Database & Models)
*   **Task 1.1**: Create migration to add `source` and `integration_metadata` columns to `devices` table.
*   **Task 1.2**: Update Pydantic models to include these new fields.
*   **Task 1.3**: Implement `ExternalDeviceProvider` abstract base class.

### Phase 2: The Mobivisor Adapter
*   **Task 2.1**: Implement `MobivisorAdapter` class that wraps the existing `MobivisorDeviceEndpoints` logic.
*   **Task 2.2**: Implement `sync_devices()` method to fetch from Mobivisor API and map to `DeviceData`.
*   **Task 2.3**: Implement `execute_command()` to translate HOMEPOT jobs into Mobivisor actions.

### Phase 3: Synchronization Engine
*   **Task 3.1**: Create a background task (Celery or asyncio) that runs periodically (e.g., every 15 mins).
*   **Task 3.2**: Implement "Upsert" logic:
    *   If device exists (match by `external_id` in metadata), update status/details.
    *   If new, create with `source='EXTERNAL'`.
    *   If deleted in Mobivisor, mark as `status='ARCHIVED'` locally.

### Phase 4: Frontend Unification
*   **Task 4.1**: Update `SitesList.jsx` to display a "Source" badge (Local vs. Mobivisor).
*   **Task 4.2**: Update `DeviceDetail.jsx` to conditionally render tabs:
    *   **Local**: Show standard config, direct shell access.
    *   **Mobivisor**: Show "Policies", "System Apps", "Kiosk Mode" (fetched via Proxy API).

---

## 4. Configuration & Safety

### Feature Flags
The integration must be toggleable via environment variables to ensure the Generic API can run standalone.

```bash
# .env
ENABLE_EXTERNAL_INTEGRATION=true
EXTERNAL_PROVIDER=mobivisor
MOBIVISOR_API_URL=https://api.mobivisor.com
MOBIVISOR_API_TOKEN=xyz...
```

### Error Handling
*   If the Sync Task fails (e.g., API down), log the error but **do not** crash the application.
*   UI should show a "Sync Warning" if data is stale (> 1 hour).

---

## 5. Developer Guidelines

1.  **Do not import Mobivisor modules** in `orchestrator.py` or `agents.py`. Use the Adapter interface.
2.  **Keep the `devices` table clean**. Put all vendor-specific data in `integration_metadata`.
3.  **Test with the Flag OFF**. Ensure the system passes all tests when `ENABLE_EXTERNAL_INTEGRATION=false`.
