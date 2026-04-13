"""Utility functions for generating and collecting device DNA information."""

import platform
import socket
from typing import Any, Dict, Optional
import uuid

import httpx
import psutil

# Public IP lookup is best-effort metadata collection and depends on external services.
PUBLIC_IP_SERVICES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
)


def _fetch_public_ip(client: httpx.Client, service_url: str) -> Optional[str]:
    """Fetch the public IP from a single service, returning None on failure."""
    try:
        response = client.get(service_url)
        response.raise_for_status()
        wan_ip = response.text.strip()
    except Exception:
        return None

    return wan_ip or None


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


def get_wan_ip() -> Optional[str]:
    """Retrieve the public (WAN) IP address using external fallback services."""
    try:
        with httpx.Client(timeout=5.0) as client:
            for service_url in PUBLIC_IP_SERVICES:
                wan_ip = _fetch_public_ip(client, service_url)
                if wan_ip:
                    return wan_ip
    except Exception:
        return None
    return None


def get_mac_address() -> Optional[str]:
    """Retrieve the MAC address of the current machine."""
    try:
        mac = uuid.getnode()
        return ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(40, -1, -8))
    except Exception:
        return None


def collect_device_dna() -> Dict[str, Optional[str]]:
    """Collect device identification data and return it as a dictionary."""
    return {
        "local_ip": get_local_ip(),
        "wan_ip": get_wan_ip(),
        "mac_address": get_mac_address(),
        "os_name": platform.system(),
        "os_version": platform.release(),
    }
