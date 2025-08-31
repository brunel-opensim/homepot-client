#!/usr/bin/env python3
"""
Test script for HOMEPOT Client API endpoints.
Tests the complete POS scenario workflow.
"""

import asyncio
import aiohttp
import json
import time


async def test_pos_scenario():
    """Test the complete POS scenario workflow."""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🏠 Testing HOMEPOT Client POS Scenario API")
        print("=" * 50)
        
        # Step 1: Create a site
        print("\n1️⃣ Creating site...")
        import random
        site_suffix = random.randint(100, 999)
        site_id = f"site-{site_suffix}"
        
        site_data = {
            "site_id": site_id,
            "name": f"Restaurant Chain Location {site_suffix}",
            "description": "Main restaurant location with 5 POS terminals",
            "location": "London, UK"
        }
        
        async with session.post(f"{base_url}/sites", json=site_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Site created: {result}")
            else:
                print(f"❌ Site creation failed: {resp.status}")
                print(await resp.text())
                return
        
        # Step 2: Create POS terminals (devices)
        print("\n2️⃣ Creating POS terminals...")
        terminals = [
            {
                "device_id": f"pos-terminal-{site_suffix}-1",
                "name": "POS Terminal 1",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.101",
                "config": {"payment_gateway": "stripe", "location": "counter_1"}
            },
            {
                "device_id": f"pos-terminal-{site_suffix}-2", 
                "name": "POS Terminal 2",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.102",
                "config": {"payment_gateway": "stripe", "location": "counter_2"}
            },
            {
                "device_id": f"pos-terminal-{site_suffix}-3",
                "name": "POS Terminal 3", 
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.103",
                "config": {"payment_gateway": "stripe", "location": "drive_thru"}
            },
            {
                "device_id": f"pos-terminal-{site_suffix}-4",
                "name": "POS Terminal 4",
                "device_type": "pos_terminal", 
                "ip_address": "192.168.1.104",
                "config": {"payment_gateway": "stripe", "location": "counter_3"}
            },
            {
                "device_id": f"pos-terminal-{site_suffix}-5",
                "name": "POS Terminal 5",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.105",
                "config": {"payment_gateway": "stripe", "location": "kiosk"}
            }
        ]
        
        for terminal in terminals:
            async with session.post(f"{base_url}/sites/{site_id}/devices", json=terminal) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✅ Created {terminal['device_id']}: {result['message']}")
                else:
                    print(f"❌ Failed to create {terminal['device_id']}: {resp.status}")
                    print(await resp.text())
        
        # Step 3: Trigger POS config update job (main scenario)
        print("\n3️⃣ Triggering POS payment config update...")
        job_data = {
            "action": "update_pos_payment_config",
            "description": "Update payment gateway configuration for Stripe v2.1",
            "config_url": "https://config.homepot.com/stripe/v2.1/config.json",
            "config_version": "2.1.0",
            "priority": "high"
        }
        
        async with session.post(f"{base_url}/sites/{site_id}/jobs", json=job_data) as resp:
            if resp.status == 200:
                job_result = await resp.json()
                job_id = job_result["job_id"]
                print(f"✅ Job created: {job_result}")
                
                # Step 4: Monitor job status
                print(f"\n4️⃣ Monitoring job {job_id} status...")
                for i in range(10):  # Check for up to 10 seconds
                    await asyncio.sleep(1)
                    
                    async with session.get(f"{base_url}/jobs/{job_id}") as resp:
                        if resp.status == 200:
                            status = await resp.json()
                            description = status.get('description', 'No description')
                            print(f"📊 Job status: {status['status']} - {description}")
                            
                            if status['status'] in ['completed', 'acknowledged', 'failed']:
                                break
                        else:
                            print(f"❌ Failed to get job status: {resp.status}")
                            break
                
            else:
                print(f"❌ Job creation failed: {resp.status}")
                print(await resp.text())
                return
        
        # Step 5: Check site health (final status)
        print("\n5️⃣ Checking site health...")
        async with session.get(f"{base_url}/sites/{site_id}/health") as resp:
            if resp.status == 200:
                health = await resp.json()
                print(f"✅ Site health: {health['status_summary']}")
                print(f"📊 Health percentage: {health['health_percentage']:.1f}%")
                print(f"📈 Devices: {health['healthy_devices']}/{health['total_devices']} healthy")
                
                # Show device details
                print("\n📱 Device Status Details:")
                for device in health['devices']:
                    status_icon = "✅" if device['status'] == 'online' else "❌"
                    print(f"  {status_icon} {device['name']} ({device['device_id']}): {device['status']}")
                
            else:
                print(f"❌ Health check failed: {resp.status}")
                print(await resp.text())
        
        # Step 6: List all sites
        print("\n6️⃣ Listing all sites...")
        async with session.get(f"{base_url}/sites") as resp:
            if resp.status == 200:
                sites = await resp.json()
                print(f"✅ Found {len(sites['sites'])} sites:")
                for site in sites['sites']:
                    print(f"  🏢 {site['name']} ({site['site_id']})")
            else:
                print(f"❌ Failed to list sites: {resp.status}")
        
        print("\n🎉 POS scenario test completed!")
        print("\n💡 You can now:")
        print("   • Open http://localhost:8000 for the dashboard")
        print("   • View real-time WebSocket updates")
        print("   • Check the interactive API docs at http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(test_pos_scenario())
