# Get Devices by Site Endpoint

## Overview

The `/api/v1/devices/sites/{site_id}/devices` endpoint provides a way to retrieve all devices associated with a specific site. This is a fundamental operation for the Homepot system, enabling site-specific device management and monitoring.

## Purpose

This endpoint serves several key use cases:

1. **Site Dashboard**: Display all devices for a specific site in the management interface
2. **Device Monitoring**: Allow administrators to view device status, health, and configuration for a site
3. **Bulk Operations**: Enable operations on all devices within a site (updates, configuration changes)
4. **Reporting**: Generate site-specific reports about device inventory and status

## Implementation

### Endpoint Details

- **Path**: `/api/v1/devices/sites/{site_id}/devices`
- **Method**: `GET`
- **Path Parameter**: `site_id` (string) - The business ID of the site (not the internal database ID)

### Response Format

**Success (200 OK)**:
```json
[
  {
    "site_id": "demo-site-1",
    "device_id": "device-001",
    "name": "POS Terminal 1",
    "device_type": "POS",
    "status": "online",
    "ip_address": "192.168.1.100",
    "created_at": "2025-11-24T10:00:00Z",
    "updated_at": "2025-11-24T15:30:00Z"
  },
  {
    "site_id": "demo-site-1",
    "device_id": "device-002",
    "name": "POS Terminal 2",
    "device_type": "POS",
    "status": "offline",
    "ip_address": "192.168.1.101",
    "created_at": "2025-11-24T10:15:00Z",
    "updated_at": "2025-11-24T14:00:00Z"
  }
]
```

**Site Not Found (404 Not Found)**:
```json
{
  "detail": "Site with ID 'invalid-site' not found"
}
```

**Server Error (500 Internal Server Error)**:
```json
{
  "detail": "Internal server error"
}
```

## Database Schema

The endpoint relies on the relationship between Site and Device entities:

- **Site**: Identified by `site_id` (string, business key)
- **Device**: Contains `site_id` (string, foreign key to Site.site_id)
- **Ordering**: Results are ordered by `created_at` descending (newest first)

### Key Design Decision: String Business IDs

The system uses **string business IDs** (like `"demo-site-1"`, `"device-001"`) for API operations, separate from internal integer primary keys. This provides:

- **Stability**: External IDs don't change when data is migrated
- **Readability**: Human-friendly identifiers in logs and APIs
- **Flexibility**: Can incorporate meaningful information in the ID structure

## Usage Examples

### cURL
```bash
# Get all devices for a site
curl -X GET "http://localhost:8001/api/v1/devices/sites/demo-site-1/devices"
```

### Python
```python
import requests

response = requests.get(
    "http://localhost:8001/api/v1/devices/sites/demo-site-1/devices"
)

if response.status_code == 200:
    devices = response.json()
    print(f"Found {len(devices)} devices")
    for device in devices:
        print(f"  - {device['name']} ({device['device_id']}): {device['status']}")
elif response.status_code == 404:
    print("Site not found")
```

### JavaScript/TypeScript
```typescript
async function getDevicesBySite(siteId: string) {
  const response = await fetch(
    `http://localhost:8001/api/v1/devices/sites/${siteId}/devices`
  );
  
  if (response.status === 200) {
    const devices = await response.json();
    return devices;
  } else if (response.status === 404) {
    throw new Error(`Site ${siteId} not found`);
  }
  
  throw new Error('Failed to fetch devices');
}
```

## Testing

The endpoint is tested in `backend/tests/test_devices_by_site.py`:

1. **Endpoint Existence**: Verifies the endpoint is registered and accessible
2. **Response Format**: Validates the JSON structure and field types
3. **Error Handling**: Ensures proper 404 responses for non-existent sites

Tests are resilient to database availability, allowing them to pass in CI environments without PostgreSQL.

## Related Endpoints

- `GET /api/v1/devices/sites` - List all sites
- `GET /api/v1/devices/sites/{site_id}` - Get specific site details
- `GET /api/v1/devices/{device_id}` - Get specific device details
- `POST /api/v1/devices` - Register a new device

## Implementation History

- **PR#42**: Initial implementation of get devices by site endpoint
- **November 2024**: Addressed review feedback:
  - Fixed endpoint path to follow RESTful conventions
  - Added site validation with proper error messages
  - Uncommented timestamps in response
  - Added comprehensive tests
  - Improved database method naming and documentation

## Future Enhancements

Potential improvements for this endpoint:

1. **Pagination**: Add `limit` and `offset` parameters for large sites
2. **Filtering**: Support query parameters like `?status=online&device_type=POS`
3. **Sorting**: Allow custom sort fields beyond `created_at`
4. **Field Selection**: Support `?fields=device_id,name,status` to reduce payload
5. **Caching**: Implement response caching for frequently accessed sites

