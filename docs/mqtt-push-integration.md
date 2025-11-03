# MQTT Push Notifications Integration Guide

## Overview

MQTT (Message Queuing Telemetry Transport) push notifications enable the HOMEPOT Client to send notifications to IoT sensors and industrial controllers. This extends the unified push notification system to support:

- **IoT Sensors** - Temperature, humidity, motion, door/window, etc.
- **Industrial Controllers** - PLCs, SCADA systems, industrial gateways
- **Edge Devices** - Raspberry Pi, Arduino, ESP32, custom embedded systems
- **OT Devices** - Operational Technology equipment

MQTT is perfect for industrial and IoT scenarios because it's:
- **Lightweight** - Minimal bandwidth and resource requirements
- **Reliable** - QoS levels (0, 1, 2) ensure delivery guarantees
- **Bi-directional** - Devices can both send and receive messages
- **Firewall-friendly** - Single TCP port for all communication
- **Battle-tested** - Industry standard for IoT messaging

## Supported Devices

MQTT push notifications work with any device that can:
- Connect to an MQTT broker over TCP/IP
- Subscribe to MQTT topics
- Parse JSON messages

### Compatible Platforms

- **Embedded Linux** - Raspberry Pi, BeagleBone, etc.
- **Microcontrollers** - ESP32, ESP8266, Arduino with Ethernet/WiFi
- **Industrial PLCs** - Siemens S7, Allen-Bradley, Modbus devices with MQTT gateways
- **SCADA Systems** - With MQTT client capabilities
- **Custom Hardware** - Any device with MQTT client library

## Architecture

MQTT uses a publish/subscribe pattern with a central broker:

```
HOMEPOT Backend (Publisher)
         ↓
    MQTT Broker (mosquitto, EMQX, HiveMQ)
         ↓
IoT Devices (Subscribers) → devices/sensor-001/notifications
```

### Components

1. **Backend Provider** (`mqtt_push.py`):
   - Implements `PushNotificationProvider` base class
   - Publishes to MQTT topics
   - Supports QoS levels (0, 1, 2)
   - TLS/SSL encryption support
   - Authentication and authorization

2. **MQTT Broker**:
   - Central message router
   - Manages topic subscriptions
   - Handles message delivery
   - Popular options: Mosquitto, EMQX, HiveMQ

3. **Device Topics**:
   - Topic pattern: `devices/{device_id}/notifications`
   - Examples:
     - `devices/sensor-001/notifications`
     - `factory/plc-01/alerts`
     - `home/living-room/temperature/alerts`

### Quality of Service (QoS) Levels

| QoS | Description | Use Case |
|-----|-------------|----------|
| **0** | At most once | Non-critical sensor readings |
| **1** | At least once | Important alerts (default) |
| **2** | Exactly once | Critical safety/control messages |

## Setup Guide

### Step 1: Install MQTT Broker

You need an MQTT broker to relay messages.

#### Option A: Mosquitto (Lightweight, Open Source)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

**macOS (Homebrew):**
```bash
brew install mosquitto
brew services start mosquitto
```

**Docker:**
```bash
docker run -d --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto
```

#### Option B: EMQX (Enterprise Features)

**Docker:**
```bash
docker run -d --name emqx \
  -p 1883:1883 \
  -p 8083:8083 \
  -p 8883:8883 \
  -p 18083:18083 \
  emqx/emqx:latest
```

Web dashboard: http://localhost:18083 (admin/public)

#### Option C: HiveMQ (Cloud/Enterprise)

Sign up at [hivemq.com](https://www.hivemq.com/) for cloud-hosted MQTT.

### Step 2: Configure Broker Security

**Enable authentication** (`/etc/mosquitto/passwd`):

```bash
# Create password file
sudo mosquitto_passwd -c /etc/mosquitto/passwd homepot

# Edit mosquitto.conf
sudo nano /etc/mosquitto/mosquitto.conf
```

**Add to mosquitto.conf:**
```conf
# Authentication
password_file /etc/mosquitto/passwd
allow_anonymous false

# Listeners
listener 1883 0.0.0.0

# TLS/SSL (recommended for production)
listener 8883
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
```

**Restart Mosquitto:**
```bash
sudo systemctl restart mosquitto
```

### Step 3: Generate TLS Certificates (Production)

For secure MQTT over TLS:

```bash
# Generate CA certificate
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt

# Generate server certificate
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 3650

# Move to mosquitto directory
sudo mkdir -p /etc/mosquitto/certs
sudo cp ca.crt server.crt server.key /etc/mosquitto/certs/
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
```

### Step 4: Configure Backend

Add MQTT configuration to your backend:

**`.env` file:**

```bash
# MQTT Broker Configuration
MQTT_BROKER_HOST=mqtt.example.com
MQTT_BROKER_PORT=1883

# Authentication (recommended)
MQTT_USERNAME=homepot
MQTT_PASSWORD=your_secure_password

# TLS/SSL (recommended for production)
MQTT_USE_TLS=true
MQTT_BROKER_PORT=8883

# Client Configuration
MQTT_CLIENT_ID=homepot-backend
MQTT_QOS=1
MQTT_RETAIN=false

# Optional
MQTT_KEEPALIVE=60
MQTT_TIMEOUT=30
```

**Python code:**

```python
from homepot.push_notifications import get_push_provider

# Configure MQTT provider
config = {
    "broker_host": os.getenv("MQTT_BROKER_HOST"),
    "broker_port": int(os.getenv("MQTT_BROKER_PORT", 1883)),
    "username": os.getenv("MQTT_USERNAME"),
    "password": os.getenv("MQTT_PASSWORD"),
    "use_tls": os.getenv("MQTT_USE_TLS", "false").lower() == "true",
    "client_id": os.getenv("MQTT_CLIENT_ID", "homepot-backend"),
    "qos": int(os.getenv("MQTT_QOS", 1)),
    "retain": os.getenv("MQTT_RETAIN", "false").lower() == "true",
}

# Get MQTT provider
mqtt_provider = await get_push_provider("mqtt_push", config)
```

### Step 5: Device Integration

Devices need to subscribe to their notification topics.

#### Python Example (Raspberry Pi)

```python
import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to device-specific topic
    client.subscribe("devices/sensor-001/notifications")

def on_message(client, userdata, msg):
    print(f"Received on {msg.topic}: {msg.payload}")
    notification = json.loads(msg.payload)
    
    title = notification.get("title")
    body = notification.get("body")
    data = notification.get("data", {})
    
    # Handle the notification
    print(f"Alert: {title} - {body}")
    print(f"Data: {data}")

client = mqtt.Client()
client.username_pw_set("device_user", "device_password")
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
client.connect("mqtt.example.com", 1883, 60)

# Start listening
client.loop_forever()
```

#### Arduino/ESP32 Example

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "YourWiFi";
const char* password = "YourPassword";
const char* mqtt_server = "mqtt.example.com";

WiFiClient espClient;
PubSubClient client(espClient);

void callback(char* topic, byte* payload, unsigned int length) {
  // Parse JSON notification
  StaticJsonDocument<512> doc;
  deserializeJson(doc, payload, length);
  
  const char* title = doc["title"];
  const char* body = doc["body"];
  
  Serial.print("Notification: ");
  Serial.println(title);
  Serial.println(body);
  
  // Handle notification (trigger LED, buzzer, display, etc.)
}

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  // Setup MQTT
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
  
  // Connect and subscribe
  while (!client.connected()) {
    if (client.connect("ESP32Client", "device_user", "device_password")) {
      client.subscribe("devices/sensor-001/notifications");
    }
  }
}

void loop() {
  client.loop();
}
```

#### Node-RED Flow

For industrial applications, use Node-RED:

1. Install MQTT input node
2. Configure broker connection
3. Subscribe to `devices/+/notifications`
4. Parse JSON payload
5. Route to displays, databases, or control systems

## Usage Examples

### Send Single Notification

```python
from homepot.push_notifications.base import (
    PushNotificationPayload,
    PushPriority
)

# Create notification
payload = PushNotificationPayload(
    title="Temperature Alert",
    body="Temperature exceeded threshold: 85°C",
    data={
        "sensor_id": "sensor-001",
        "value": 85,
        "threshold": 80,
        "location": "Server Room"
    },
    priority=PushPriority.HIGH
)

# Send to specific device
result = await mqtt_provider.send_notification(
    device_token="devices/sensor-001/notifications",
    payload=payload
)

if result.success:
    print("Notification sent successfully!")
else:
    print(f"Failed: {result.message}")
```

### Send Bulk Notifications

```python
# Send to multiple devices at once
notifications = [
    ("devices/sensor-001/notifications", payload1),
    ("devices/sensor-002/notifications", payload2),
    ("factory/plc-01/alerts", payload3),
]

results = await mqtt_provider.send_bulk_notifications(notifications)

for result in results:
    print(f"{result.device_token}: {result.success}")
```

### Topic-Based Broadcasting

```python
# Send to all devices in a location
payload = PushNotificationPayload(
    title="System Maintenance",
    body="Scheduled maintenance in 30 minutes",
    priority=PushPriority.NORMAL
)

# All devices subscribing to this topic will receive it
result = await mqtt_provider.send_topic_notification(
    topic="factory/floor-3/alerts",
    payload=payload
)
```

### Emergency Alerts

```python
# Critical alert with QoS 2 (exactly once delivery)
emergency_config = config.copy()
emergency_config["qos"] = 2  # Exactly once

emergency_provider = await get_push_provider("mqtt_push", emergency_config)

payload = PushNotificationPayload(
    title="🚨 EMERGENCY SHUTDOWN",
    body="Gas leak detected in Building A",
    data={
        "emergency_level": "CRITICAL",
        "action": "EVACUATE",
        "location": "Building A"
    },
    priority=PushPriority.URGENT
)

# Broadcast to all emergency systems
await emergency_provider.send_topic_notification(
    topic="emergency/building-a/all",
    payload=payload
)
```

## Topic Naming Conventions

Use hierarchical topic structure for organization:

```
devices/{device_type}/{device_id}/notifications
├── devices/sensor/temp-001/notifications
├── devices/sensor/motion-002/notifications
├── devices/plc/line-01/notifications
└── devices/gateway/edge-gateway-01/notifications

factory/{building}/{floor}/{area}/alerts
├── factory/building-a/floor-1/production/alerts
├── factory/building-a/floor-2/assembly/alerts
└── factory/building-b/warehouse/alerts

home/{room}/{device_type}/alerts
├── home/living-room/temperature/alerts
├── home/kitchen/smoke-detector/alerts
└── home/garage/door/alerts
```

## Testing

### Test with Mosquitto Client

**Subscribe (simulate device):**
```bash
mosquitto_sub -h mqtt.example.com -t "devices/sensor-001/notifications" \
  -u device_user -P device_password -v
```

**Publish (simulate backend):**
```bash
mosquitto_pub -h mqtt.example.com -t "devices/sensor-001/notifications" \
  -u homepot -P your_password \
  -m '{"title":"Test","body":"Test notification","timestamp":"2025-01-24T10:30:00Z"}'
```

### Test with Python

```python
import asyncio
from homepot.push_notifications.mqtt_push import MQTTPushProvider
from homepot.push_notifications.base import PushNotificationPayload

async def test_mqtt():
    config = {
        "broker_host": "localhost",
        "broker_port": 1883,
        "username": "homepot",
        "password": "password",
    }
    
    provider = MQTTPushProvider(config)
    await provider.initialize()
    
    payload = PushNotificationPayload(
        title="Test Alert",
        body="This is a test notification"
    )
    
    result = await provider.send_notification(
        "devices/test/notifications",
        payload
    )
    
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    
    await provider.cleanup()

asyncio.run(test_mqtt())
```

## Monitoring

### Check Platform Status

```python
info = await mqtt_provider.get_platform_info()

print(f"Platform: {info['platform']}")
print(f"Broker: {info['broker_host']}:{info['broker_port']}")
print(f"Connected: {info['connected']}")
print(f"QoS: {info['qos']}")
print(f"Statistics: {info['statistics']}")
```

### View Statistics

```python
stats = info['statistics']
print(f"Total Sent: {stats['total_sent']}")
print(f"Successful: {stats['total_success']}")
print(f"Failed: {stats['total_failed']}")
print(f"Last Sent: {stats['last_sent']}")
print(f"Connections: {stats['connection_count']}")
```

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to broker
```python
# Check broker is running
mosquitto -h  # Should show version

# Check port is open
nc -zv mqtt.example.com 1883

# Check firewall
sudo ufw allow 1883/tcp
```

**Problem:** Authentication failed
```bash
# Verify credentials
mosquitto_sub -h localhost -t test -u homepot -P password

# Reset password
sudo mosquitto_passwd -b /etc/mosquitto/passwd homepot newpassword
sudo systemctl restart mosquitto
```

### Message Not Received

**Problem:** Device not receiving notifications

1. **Check topic subscription:**
   ```python
   # Ensure exact topic match
   device_token = "devices/sensor-001/notifications"  # Must match subscription
   ```

2. **Verify QoS settings:**
   ```python
   # Use QoS 1 or 2 for reliability
   config["qos"] = 1
   ```

3. **Check device connection:**
   ```bash
   # Monitor broker logs
   sudo tail -f /var/log/mosquitto/mosquitto.log
   ```

### Performance Issues

**Problem:** High latency or message delays

1. **Reduce payload size:**
   ```python
   # Keep messages under 256KB
   # Use data field efficiently
   ```

2. **Optimize QoS:**
   ```python
   # Use QoS 0 for non-critical messages
   config["qos"] = 0
   ```

3. **Scale broker:**
   ```bash
   # Use clustered EMQX or HiveMQ for high volume
   ```

## Security Best Practices

1. **Always use TLS in production:**
   ```python
   config["use_tls"] = True
   config["broker_port"] = 8883
   ```

2. **Strong authentication:**
   - Use complex passwords
   - Separate credentials per device
   - Rotate credentials regularly

3. **Topic ACLs (Access Control Lists):**
   ```conf
   # /etc/mosquitto/acl
   user homepot
   topic write devices/+/notifications
   
   user sensor-001
   topic read devices/sensor-001/notifications
   ```

4. **Network security:**
   - Firewall MQTT ports
   - Use VPN for remote devices
   - Consider certificate-based auth

5. **Message encryption:**
   - TLS encrypts transport
   - Consider payload encryption for sensitive data

## Integration with Database

Register MQTT devices in HOMEPOT database:

```python
from homepot.models import DeviceType

# Register IoT sensor
device = {
    "device_type": DeviceType.IOT_SENSOR,
    "device_token": "devices/sensor-001/notifications",
    "platform": "mqtt_push",
    "metadata": {
        "sensor_type": "temperature",
        "location": "Server Room",
        "manufacturer": "DHT22"
    }
}

# Register industrial controller
plc_device = {
    "device_type": DeviceType.INDUSTRIAL_CONTROLLER,
    "device_token": "factory/plc-01/alerts",
    "platform": "mqtt_push",
    "metadata": {
        "controller_type": "Siemens S7-1200",
        "protocol": "Modbus TCP",
        "location": "Production Line 1"
    }
}
```

## Advanced Features

### Retained Messages

Keep last message for new subscribers:

```python
config["retain"] = True  # Last message persists on broker
```

### Last Will and Testament (LWT)

Detect device disconnections:

```python
# Device sets LWT on connection
client.will_set(
    "devices/sensor-001/status",
    payload="offline",
    qos=1,
    retain=True
)
```

### Persistent Sessions

Resume after reconnection:

```python
# Device uses clean_session=False
client = mqtt.Client(client_id="sensor-001", clean_session=False)
```

## Performance Considerations

| Metric | Recommendation |
|--------|---------------|
| **Payload Size** | < 10KB for sensors, < 100KB for controllers |
| **QoS Level** | Use 0 for telemetry, 1 for alerts, 2 for critical |
| **Connection Pool** | Reuse MQTT client connections |
| **Topic Structure** | Hierarchical, max 7 levels deep |
| **Broker Selection** | Mosquitto < 1K devices, EMQX > 1K devices |

## Next Steps

1. **Set up MQTT broker** with TLS and authentication
2. **Configure backend** with broker credentials
3. **Register IoT devices** in database with MQTT topics
4. **Deploy device firmware** with MQTT subscription code
5. **Test end-to-end** notification delivery
6. **Monitor performance** and optimize as needed
7. **Integrate with alerting system** for critical notifications

## Additional Resources

- [MQTT Specification](https://mqtt.org/mqtt-specification/)
- [Mosquitto Documentation](https://mosquitto.org/documentation/)
- [Paho MQTT Client](https://www.eclipse.org/paho/)
- [EMQX Documentation](https://docs.emqx.com/)
- [HiveMQ MQTT Essentials](https://www.hivemq.com/mqtt-essentials/)
