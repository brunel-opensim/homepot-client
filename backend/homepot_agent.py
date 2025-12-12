"""
HomePot Device Agent - Windows PC
This script runs on the device and sends heartbeat to backend
"""

import requests
import time
import socket
import platform
import psutil
import sys

# ===== CONFIGURATION =====
BACKEND_URL = "http://192.168.0.223:8000/api/v1"  # Your Ubuntu PC IP
DEVICE_ID = "pos-terminal-002"
HEARTBEAT_INTERVAL = 10 # seconds
# =========================

def get_local_ip():
    """Get local IP address of this PC."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"

def get_system_info():
    """Get detailed system information."""
    try:
        return {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }
    except:
        return {}

def get_hardware_usage():
    """Get current hardware usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        
        return {
            "cpu_usage": round(cpu_percent, 2),
            "memory_usage": round(memory.percent, 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "disk_usage": round(disk.percent, 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2)
        }
    except Exception as e:
        print(f"Error getting hardware usage: {e}")
        return {}

def send_heartbeat():
    """Send health check to backend server."""
    try:
        # Get hardware usage
        hw_usage = get_hardware_usage()
        
        # Prepare health check data (matching /health API format)
        data = {
            "is_healthy": True,
            "response_time_ms": 100,
            "status_code": 200,
            "endpoint": "/health",
            "response_data": {
                "status": "healthy",
                "version": "1.0.0"
            },
            "system": {
                "cpu_percent": hw_usage.get('cpu_usage', 0),
                "memory_percent": hw_usage.get('memory_usage', 0),
                "memory_used_mb": int(hw_usage.get('memory_used_gb', 0) * 1024),
                "memory_total_mb": int(hw_usage.get('memory_total_gb', 0) * 1024),
                "disk_percent": hw_usage.get('disk_usage', 0),
                "disk_used_gb": int(hw_usage.get('disk_used_gb', 0)),
                "disk_total_gb": int(hw_usage.get('disk_total_gb', 0)),
                "uptime_seconds": int(time.time())
            },
            "app_metrics": {
                "app_version": "1.0.0",
                "transactions_count": 0,
                "errors_count": 0,
                "warnings_count": 0,
                "avg_response_time_ms": 350
            },
            "network": {
                "latency_ms": 45,
                "rx_bytes": 0,
                "tx_bytes": 0
            }
        }
        
        # Send to backend using /health endpoint
        response = requests.post(
            f"{BACKEND_URL}/devices/{DEVICE_ID}/health",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✅ Health check sent successfully")
            print(f"   CPU: {hw_usage.get('cpu_usage', 0):.1f}% | "
                  f"RAM: {hw_usage.get('memory_usage', 0):.1f}% | "
                  f"Disk: {hw_usage.get('disk_usage', 0):.1f}%")
            return True
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend at {BACKEND_URL}")
        print(f"   Make sure backend is running and accessible")
        return False
    except Exception as e:
        print(f"❌ Error sending health check: {e}")
        return False

def check_backend_connection():
    """Test connection to backend."""
    try:
        response = requests.get(f"{BACKEND_URL.replace('/api/v1', '')}/", timeout=5)
        if response.status_code == 200:
            print("✅ Backend connection successful!")
            return True
        else:
            print(f"⚠️  Backend responded with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print(f"\nTroubleshooting:")
        print(f"  1. Is backend running on {BACKEND_URL}?")
        print(f"  2. Are both PCs on same WiFi?")
        print(f"  3. Is firewall blocking port 8000?")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("HomePot Device Agent - Windows PC")
    print("=" * 70)
    print(f"Device ID: {DEVICE_ID}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Local IP: {get_local_ip()}")
    print(f"Hostname: {platform.node()}")
    print("=" * 70)
    
    # Test backend connection first
    print("\nTesting backend connection...")
    if not check_backend_connection():
        print("\n❌ Cannot connect to backend. Please fix connection and try again.")
        sys.exit(1)
    
    print("\n✅ Connection successful! Starting agent...\n")
    print(f"Sending health check every {HEARTBEAT_INTERVAL} seconds")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n👋 Agent stopped by user")
        print("Goodbye!")