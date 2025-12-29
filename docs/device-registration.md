# Device Registration Guide

This guide explains how to register new devices in the HOMEPOT Client system. Device registration is a fundamental step in managing your OT (Operational Technology) and IoT assets.

## Conceptual Model

In HOMEPOT, every device must belong to a **Site**. This hierarchy ensures that devices are organized by their physical or logical location, enabling features like:

*   **Geospatial Visualization**: Viewing sites and their status on a world map.
*   **Group Management**: Applying policies or commands to all devices at a specific site.
*   **Access Control**: Restricting user access to specific sites.

```mermaid
graph LR
    Site[Site (Location)] --> Device1[Device 1 (POS)]
    Site --> Device2[Device 2 (Sensor)]
    Site --> Device3[Device 3 (Gateway)]
```

## Prerequisites

Before registering a device, you must have at least one **Site** created in the system.

## Step 1: Create a Site

If you haven't created a site yet, follow these steps:

1.  Navigate to the **Sites** section in the dashboard.
2.  Click **Create New Site**.
3.  Fill in the required information:
    *   **Site Name**: A descriptive name (e.g., "London HQ").
    *   **Site ID**: A unique identifier (e.g., "site-lon-001").
    *   **Location**: A human-readable address (e.g., "London, UK").
    *   **Latitude & Longitude**: The GPS coordinates of the site. This is **crucial** for the world map visualization.
        *   *Example*: Latitude `51.5074`, Longitude `-0.1278` for London.
4.  Click **Create Site**.

## Step 2: Register a Device

Once you have a site, you can register devices to it.

1.  Navigate to the **Devices** section.
2.  Click **Register New Device** (or navigate to `/device/new`).
3.  **Assign to Site**: Select the site where this device is located from the dropdown menu.
4.  **Device Details**:
    *   **Device Name**: A friendly name (e.g., "Front Desk POS").
    *   **Device ID**: A unique identifier (e.g., Serial Number or Asset Tag).
    *   **Device Type**: Select the category (POS Terminal, IoT Sensor, etc.).
5.  **Network & Info** (Optional but recommended):
    *   **IP Address**: The local IP address of the device.
    *   **MAC Address**: The physical address of the network interface.
    *   **Firmware Version**: The current software version running on the device.
6.  Click **Register Device**.

## API Reference

For developers integrating directly with the API:

### Create Site
`POST /api/v1/sites`

```json
{
  "site_id": "site-001",
  "name": "New York Office",
  "location": "New York, USA",
  "latitude": 40.7128,
  "longitude": -74.0060
}
```

### Register Device
`POST /api/v1/devices/sites/{site_id}/devices`

```json
{
  "device_id": "dev-001",
  "name": "Lobby Sensor",
  "device_type": "iot_sensor",
  "site_id": "site-001",
  "ip_address": "192.168.1.50"
}
```
