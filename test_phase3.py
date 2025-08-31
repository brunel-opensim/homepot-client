#!/usr/bin/env python3
"""
Phase 3 Test Script: Agent Simulation & Health Checks

This script demonstrates the complete HOMEPOT POS scenario with realistic agent simulation:
1. Creates sites and POS terminals
2. Triggers configuration updates with agent simulation
3. Monitors agent states and health checks
4. Tests direct agent interactions
5. Demonstrates error scenarios and recovery
"""

import asyncio
import json
import random
import time
from typing import Dict, List

import aiohttp


async def test_phase3_agent_simulation():
    """Test the complete Phase 3 agent simulation functionality."""
    base_url = "http://localhost:8000"
    
    print("🏠 Testing HOMEPOT Client Phase 3: Agent Simulation & Health Checks")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        
        # Phase 1-2: Setup (Quick)
        print("\n🚀 Phase 1-2: Setting up test environment...")
        site_suffix = random.randint(1000, 9999)
        site_id = f"restaurant-{site_suffix}"
        
        # Create site
        site_data = {
            "site_id": site_id,
            "name": f"McDonald's Location {site_suffix}",
            "description": "Fast food restaurant with drive-thru and kiosks",
            "location": "Birmingham, UK"
        }
        
        async with session.post(f"{base_url}/sites", json=site_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Created site: {result['name']}")
            else:
                print(f"❌ Failed to create site: {resp.status}")
                return
        
        # Create 3 POS terminals with different types
        terminals = [
            {
                "device_id": f"drive-thru-{site_suffix}",
                "name": "Drive-Thru Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.10",
                "config": {"location": "drive_thru", "payment_gateway": "square", "priority": "high"}
            },
            {
                "device_id": f"counter-1-{site_suffix}",
                "name": "Main Counter Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.11",
                "config": {"location": "counter_1", "payment_gateway": "square", "priority": "high"}
            },
            {
                "device_id": f"kiosk-1-{site_suffix}",
                "name": "Self-Service Kiosk",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.12",
                "config": {"location": "kiosk_1", "payment_gateway": "square", "priority": "medium"}
            }
        ]
        
        device_ids = []
        for terminal in terminals:
            async with session.post(f"{base_url}/sites/{site_id}/devices", json=terminal) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    device_ids.append(terminal["device_id"])
                    print(f"✅ Created device: {terminal['name']}")
                else:
                    print(f"❌ Failed to create device {terminal['name']}: {resp.status}")
        
        # Wait for agents to initialize
        print("\n⏱️  Waiting for agents to initialize...")
        await asyncio.sleep(3)
        
        # Phase 3: Agent Testing
        print("\n🤖 Phase 3: Testing Agent Simulation...")
        
        # Step 1: Check agent status
        print("\n1️⃣ Checking agent status...")
        async with session.get(f"{base_url}/agents") as resp:
            if resp.status == 200:
                agents_data = await resp.json()
                agents = agents_data.get("agents", [])
                print(f"✅ Found {len(agents)} active agents:")
                for agent in agents:
                    print(f"   🤖 {agent['device_id']} - State: {agent['state']} - Config: v{agent['config_version']}")
            else:
                print(f"❌ Failed to get agents: {resp.status}")
                return
        
        # Step 2: Test individual health checks
        print("\n2️⃣ Testing individual device health checks...")
        for device_id in device_ids[:2]:  # Test first 2 devices
            async with session.post(f"{base_url}/devices/{device_id}/health") as resp:
                if resp.status == 200:
                    health_data = await resp.json()
                    health_status = health_data["health"]["status"]
                    config_version = health_data["health"]["config_version"]
                    print(f"✅ {device_id}: {health_status} (v{config_version})")
                    
                    # Show detailed metrics
                    metrics = health_data["health"]["metrics"]
                    print(f"   📊 CPU: {metrics['cpu_usage_percent']}% | Memory: {metrics['memory_usage_percent']}% | Transactions: {metrics['transactions_today']}")
                else:
                    error_data = await resp.json()
                    print(f"❌ Health check failed for {device_id}: {error_data.get('detail', 'Unknown error')}")
        
        # Step 3: Trigger POS configuration update (main scenario)
        print("\n3️⃣ Triggering POS payment configuration update...")
        job_data = {
            "action": "update_pos_payment_config",
            "description": "Update payment gateway to new Square API v2.0",
            "config_url": "https://config.mcdonalds.com/square-v2.0.json",
            "config_version": "2.0.1",
            "priority": "high"
        }
        
        async with session.post(f"{base_url}/sites/{site_id}/jobs", json=job_data) as resp:
            if resp.status == 200:
                job_result = await resp.json()
                job_id = job_result["job_id"]
                print(f"✅ Job created: {job_id}")
                
                # Monitor job progress and agent states
                print("\n4️⃣ Monitoring job progress and agent behavior...")
                for i in range(15):  # Monitor for up to 15 seconds
                    await asyncio.sleep(1)
                    
                    # Get job status
                    async with session.get(f"{base_url}/jobs/{job_id}") as job_resp:
                        if job_resp.status == 200:
                            job_status = await job_resp.json()
                            print(f"📈 Job {job_id}: {job_status['status']} (attempt {i+1}/15)")
                            
                            if job_status['status'] in ['acknowledged', 'completed', 'failed']:
                                print(f"✅ Job completed with status: {job_status['status']}")
                                if job_status.get('result'):
                                    result = job_status['result']
                                    print(f"   📊 Successful pushes: {result.get('successful_pushes', 0)}/{result.get('total_devices', 0)}")
                                break
                    
                    # Check agent states every few iterations
                    if i % 3 == 0:
                        async with session.get(f"{base_url}/agents") as agents_resp:
                            if agents_resp.status == 200:
                                agents_data = await agents_resp.json()
                                agents = agents_data.get("agents", [])
                                states = [f"{agent['device_id'].split('-')[0]}:{agent['state']}" for agent in agents[:3]]
                                print(f"   🤖 Agent states: {' | '.join(states)}")
            else:
                error_data = await resp.json()
                print(f"❌ Failed to create job: {error_data.get('detail', 'Unknown error')}")
                return
        
        # Step 5: Test direct agent interactions
        print("\n5️⃣ Testing direct agent interactions...")
        test_device = device_ids[0]
        
        # Test restart command
        print(f"\n   🔄 Testing restart command on {test_device}...")
        async with session.post(f"{base_url}/devices/{test_device}/restart") as resp:
            if resp.status == 200:
                restart_result = await resp.json()
                response = restart_result["response"]
                print(f"   ✅ Restart response: {response['status']} - {response['message']}")
            else:
                print(f"   ❌ Restart failed: {resp.status}")
        
        # Test custom push notification
        print(f"\n   📱 Testing custom push notification...")
        custom_notification = {
            "action": "health_check",
            "data": {"urgent": True}
        }
        async with session.post(f"{base_url}/agents/{test_device}/push", json=custom_notification) as resp:
            if resp.status == 200:
                push_result = await resp.json()
                response = push_result["response"]
                print(f"   ✅ Custom push response: {response['status']}")
                if response.get("health_check"):
                    health = response["health_check"]
                    print(f"   📊 Health result: {health['status']} (v{health['config_version']})")
            else:
                print(f"   ❌ Custom push failed: {resp.status}")
        
        # Step 6: Final site health check
        print("\n6️⃣ Final site health summary...")
        async with session.get(f"{base_url}/sites/{site_id}/health") as resp:
            if resp.status == 200:
                health_data = await resp.json()
                print(f"✅ Site health: {health_data['status_summary']}")
                print(f"📊 Health percentage: {health_data['health_percentage']:.1f}%")
                
                print("\n📱 Device Status Details:")
                for device in health_data["devices"]:
                    status_icon = "✅" if device["status"] == "online" else "❌" if device["status"] == "error" else "⏳"
                    print(f"  {status_icon} {device['name']} ({device['device_id']}): {device['status']}")
            else:
                print(f"❌ Health check failed: {resp.status}")
        
        # Step 7: Agent performance summary
        print("\n7️⃣ Agent simulation performance summary...")
        async with session.get(f"{base_url}/agents") as resp:
            if resp.status == 200:
                agents_data = await resp.json()
                agents = agents_data.get("agents", [])
                
                print(f"🤖 Total agents: {len(agents)}")
                states = {}
                config_versions = {}
                
                for agent in agents:
                    state = agent.get("state", "unknown")
                    states[state] = states.get(state, 0) + 1
                    
                    version = agent.get("config_version", "unknown")
                    config_versions[version] = config_versions.get(version, 0) + 1
                
                print(f"📊 Agent states: {dict(states)}")
                print(f"🔧 Config versions: {dict(config_versions)}")
            else:
                print(f"❌ Failed to get final agent status: {resp.status}")
        
    print("\n🎉 Phase 3 Agent Simulation test completed!")
    print("\n💡 What you can do next:")
    print("   • Open http://localhost:8000 for the enhanced dashboard")
    print("   • Check http://localhost:8000/docs for the complete API documentation")
    print("   • Monitor real-time agent states and health checks")
    print("   • Test error scenarios and recovery mechanisms")
    print("   • Integrate with your existing restaurant management systems")


if __name__ == "__main__":
    print("Starting Phase 3 Agent Simulation test...")
    print("Make sure the HOMEPOT Client server is running on http://localhost:8000")
    print("")
    
    try:
        asyncio.run(test_phase3_agent_simulation())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
