import socket
import uuid
import platform
import psutil
import httpx


def get_local_ip():
    """Get primary local IP address"""
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    return addr.address
    except Exception:
        pass
    return None


def get_wan_ip(payload):
    """Get public WAN IP"""
    try:
        with httpx.Client(timeout=5.0) as client:
            # response = client.get("https://api.ipify.org")
            response = client.get(payload.backend_url)
            response.raise_for_status()
            return response.text.strip()
    except Exception:
        return None


def get_mac_address():
    """Get primary MAC address"""
    try:
        mac = uuid.getnode()
        return ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(40, -1, -8))
    except Exception:
        return None


def collect_device_dna(payload):
    """Collect static Device DNA"""
    return {
        "local_ip": get_local_ip(),
        "wan_ip": get_wan_ip(payload),
        "mac_address": get_mac_address(),
        "os_name": platform.system(),
        "os_version": platform.release(),
    }