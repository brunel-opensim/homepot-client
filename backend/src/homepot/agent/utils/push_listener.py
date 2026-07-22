"""Push-wake-up listener that triggers command polling on incoming notifications."""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

from homepot.agent.utils.wns_push import WNSPushChannelManager

logger = logging.getLogger(__name__)


class PushWakeupListener:
    """Listens for push notifications and signals the command poller to wake up.

    Supports MQTT subscription and WNS push channel registration.  When a
    notification arrives on the device's MQTT topic the internal
    ``asyncio.Event`` is set, allowing the polling loop to check for pending
    commands immediately.

    On Windows the listener also starts a :class:`WNSPushChannelManager` to
    create / refresh a WNS push channel URI so the backend can push
    notifications without MQTT.

    If no MQTT broker is configured and WNS is unavailable the listener
    operates in *simulated* mode: it never sets the event, and the polling
    loop relies on its own interval.
    """

    def __init__(
        self,
        device_id: str,
        *,
        mqtt_broker_host: Optional[str] = None,
        mqtt_broker_port: int = 1883,
        mqtt_username: Optional[str] = None,
        mqtt_password: Optional[str] = None,
        topic_prefix: str = "devices",
        wns_channel_mgr: Optional[WNSPushChannelManager] = None,
    ) -> None:
        """Initialise the listener with device identity and optional MQTT config."""
        self._device_id = device_id
        self._mqtt_host = mqtt_broker_host
        self._mqtt_port = mqtt_broker_port
        self._mqtt_username = mqtt_username
        self._mqtt_password = mqtt_password
        self._topic = f"{topic_prefix}/{device_id}/commands"
        self._event = asyncio.Event()
        self._client: Any = None
        self._wns_mgr = wns_channel_mgr

    @property
    def wake_event(self) -> asyncio.Event:
        """Return the ``asyncio.Event`` set when a push notification arrives."""
        return self._event

    @property
    def wns_channel_mgr(self) -> Optional[WNSPushChannelManager]:
        """Return the optional WNS channel manager."""
        return self._wns_mgr

    async def start(self) -> None:
        """Connect to the MQTT broker and start WNS channel registration."""
        if self._wns_mgr is not None:
            self._wns_mgr.get_or_create_channel()
            self._wns_mgr.start_background_refresh()

        if not self._mqtt_host:
            logger.info(
                "PushWakeupListener: no MQTT broker configured; "
                "running in simulated mode (no wake-ups)"
            )
            return

        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(
                client_id=f"agent-{self._device_id}-push",
                protocol=mqtt.MQTTv5,
            )
            if self._mqtt_username and self._mqtt_password:
                self._client.username_pw_set(self._mqtt_username, self._mqtt_password)

            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message

            logger.info(
                "Connecting to MQTT broker %s:%s", self._mqtt_host, self._mqtt_port
            )
            self._client.connect_async(self._mqtt_host, self._mqtt_port)
            self._client.loop_start()
            logger.info("PushWakeupListener subscribed to %s", self._topic)
        except ImportError:
            logger.warning(
                "paho-mqtt not installed; push wake-up disabled. "
                "Install with: pip install paho-mqtt"
            )
        except Exception as exc:
            logger.warning("Failed to start MQTT push listener: %s", exc, exc_info=True)

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: int, properties: Any
    ) -> None:
        """Handle MQTT connection established event and subscribe to device topic."""
        if reason_code == 0:
            logger.info("MQTT connected, subscribing to %s", self._topic)
            client.subscribe(self._topic, qos=1)
        else:
            logger.warning("MQTT connection failed reason_code=%s", reason_code)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Decode incoming MQTT message and signal the poller to wake up."""
        try:
            payload_str = msg.payload.decode("utf-8") if msg.payload else "{}"
            payload = json.loads(payload_str)
            logger.info("Push notification received on %s: %s", msg.topic, payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Failed to decode push message payload: %s", exc)
        self._event.set()

    async def stop(self) -> None:
        """Stop WNS refresh and disconnect from MQTT broker."""
        if self._wns_mgr is not None:
            await self._wns_mgr.stop_background_refresh()
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            logger.info("PushWakeupListener stopped")


def create_push_listener(
    config: Dict[str, Any],
    cred: Optional[Any] = None,
) -> PushWakeupListener:
    """Build a ``PushWakeupListener`` from agent configuration.

    Reads the following configuration keys (all optional):

    * ``mqtt_broker_host``
    * ``mqtt_broker_port`` (default ``1883``)
    * ``mqtt_username``
    * ``mqtt_password``

    If *cred* is supplied and the platform is Windows, a
    :class:`WNSPushChannelManager` is attached for WNS push registration.
    """
    wns_mgr: Optional[WNSPushChannelManager] = None
    if sys.platform == "win32" and cred is not None:
        wns_mgr = WNSPushChannelManager(cred)

    return PushWakeupListener(
        device_id=config.get("device_id", ""),
        mqtt_broker_host=config.get("mqtt_broker_host"),
        mqtt_broker_port=int(config.get("mqtt_broker_port", 1883)),
        mqtt_username=config.get("mqtt_username"),
        mqtt_password=config.get("mqtt_password"),
        wns_channel_mgr=wns_mgr,
    )
