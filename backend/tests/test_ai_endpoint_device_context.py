from datetime import datetime, timedelta, timezone

from homepot.app.api.API_v1.Endpoints.AIEndpoint import _device_is_online, _device_mode
from homepot.models import Device


def test_device_is_online_uses_heartbeat_recency():
    device = Device(
        device_id="device-online",
        name="Online Device",
        device_type="terminal",
        site_id=1,
        last_heartbeat_at=datetime.now() - timedelta(seconds=60),
    )

    assert _device_is_online(device) is True

    device.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=180)

    assert _device_is_online(device) is False


def test_device_mode_classifies_real_simulated_and_emulated_devices():
    simulated_device = Device(
        device_id="device-simulated",
        name="Simulated Device",
        device_type="terminal",
        site_id=1,
        is_simulated=True,
    )
    emulated_device = Device(
        device_id="device-emulated",
        name="Emulated Device",
        device_type="terminal",
        site_id=1,
        config={"device_source": "emulator"},
    )
    real_device = Device(
        device_id="device-real",
        name="Real Device",
        device_type="terminal",
        site_id=1,
    )

    assert _device_mode(simulated_device) == "simulated"
    assert _device_mode(emulated_device) == "emulated"
    assert _device_mode(real_device) == "real"
