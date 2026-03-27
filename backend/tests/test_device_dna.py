"""Tests for device DNA utilities."""

import socket

from homepot.agent.utils import device_dna


def test_get_local_ip_returns_first_non_loopback(monkeypatch):
    """Local IP lookup should skip loopback addresses."""

    class Addr:
        def __init__(self, family, address):
            self.family = family
            self.address = address

    monkeypatch.setattr(
        device_dna.psutil,
        "net_if_addrs",
        lambda: {
            "lo": [Addr(socket.AF_INET, "127.0.0.1")],
            "eth0": [Addr(socket.AF_INET, "192.168.10.20")],
        },
    )

    assert device_dna.get_local_ip() == "192.168.10.20"


def test_get_wan_ip_uses_fallback_service(monkeypatch):
    """WAN IP lookup should fall back when the first service fails."""

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class ClientStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            if url == device_dna.PUBLIC_IP_SERVICES[0]:
                raise RuntimeError("primary unavailable")
            return Response("198.51.100.7\n")

    monkeypatch.setattr(device_dna.httpx, "Client", lambda timeout=5.0: ClientStub())

    assert device_dna.get_wan_ip() == "198.51.100.7"


def test_get_wan_ip_returns_none_when_all_services_fail(monkeypatch):
    """WAN IP lookup should fail closed when all providers are unavailable."""

    class ClientStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            raise RuntimeError(f"{url} unavailable")

    monkeypatch.setattr(device_dna.httpx, "Client", lambda timeout=5.0: ClientStub())

    assert device_dna.get_wan_ip() is None


def test_get_mac_address_formats_uuid_node(monkeypatch):
    """MAC address formatting should convert uuid.getnode() output."""
    monkeypatch.setattr(device_dna.uuid, "getnode", lambda: 0x001122334455)

    assert device_dna.get_mac_address() == "00:11:22:33:44:55"


def test_collect_device_dna_aggregates_sources(monkeypatch):
    """Device DNA should combine all helper outputs into one payload."""
    monkeypatch.setattr(device_dna, "get_local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(device_dna, "get_wan_ip", lambda payload=None: "203.0.113.8")
    monkeypatch.setattr(device_dna, "get_mac_address", lambda: "aa:bb:cc:dd:ee:ff")
    monkeypatch.setattr(device_dna.platform, "system", lambda: "TestOS")
    monkeypatch.setattr(device_dna.platform, "release", lambda: "2026.1")

    assert device_dna.collect_device_dna({"device_id": "x"}) == {
        "local_ip": "10.0.0.5",
        "wan_ip": "203.0.113.8",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "os_name": "TestOS",
        "os_version": "2026.1",
    }
