"""Utility functions for generating and collecting device DNA information."""

import platform
import socket
from typing import Any, Dict, Optional
import uuid

import httpx
import psutil


def get_local_ip() -> Optional[str]:
    """Retrieve the first non-loopback local IPv4 address."""
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith(
                    "127."
                ):
                    return addr.address
    except Exception:
        pass
    return None


def get_wan_ip(payload: Any) -> Optional[str]:
    """Retrieve the public (WAN) IP address using an external service."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("https://api.ipify.org")
            response.raise_for_status()
            return response.text.strip()
    except Exception:
        return None


def get_mac_address() -> Optional[str]:
    """Retrieve the MAC address of the current machine."""
    try:
        mac = uuid.getnode()
        return ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(40, -1, -8))
    except Exception:
        return None


def collect_device_dna(payload: Any) -> Dict[str, Optional[str]]:
    """Collect device identification data and return it as a dictionary."""
    return {
        "local_ip": get_local_ip(),
        "wan_ip": get_wan_ip(payload),
        "mac_address": get_mac_address(),
        "os_name": platform.system(),
        "os_version": platform.release(),
    }
