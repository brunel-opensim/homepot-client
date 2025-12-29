#!/usr/bin/env python3
"""
HOMEPOT AI Capability Demo.

This script demonstrates the full AI pipeline:
1. Data Ingestion (EventStore)
2. Predictive Analysis (FailurePredictor)
3. Context-Aware Intelligence (LLM + RAG)

Scenario: A server ('server-01') is experiencing a rapid CPU spike.
"""

import asyncio
import logging
import os
import sys

# Add project root to path (to import 'ai' package)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
# Add backend/src to path for homepot imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from ai.analysis_modes import ModeManager
from ai.analytics_service import AIAnalyticsService
from ai.event_store import EventStore
from ai.failure_predictor import FailurePredictor
from ai.llm import LLMService
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DEMO")


def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


async def run_demo():
    """Run the AI capability demo."""
    print_header("HOMEPOT AI CAPABILITY DEMO")
    print("Initializing AI Services...")

    # 1. Initialize Services
    event_store = EventStore()

    # Check actual DB connectivity
    db_status = "OFFLINE (Using In-Memory Cache)"
    if event_store.engine:
        try:
            with event_store.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "ACTIVE (Database Connected)"
        except Exception as e:
            db_status = f"OFFLINE (Connection Failed: {str(e).split(':')[0]})"
            # Disable engine to prevent error spam during demo
            event_store.engine = None

    predictor = FailurePredictor(event_store)
    mode_manager = ModeManager()
    llm_service = LLMService()

    print(f"INFO: Database Connection: {db_status}")
    print(
        f"INFO: LLM Service: {'ACTIVE' if llm_service.check_health() else 'OFFLINE (Will use Simulation)'}"
    )

    # =========================================================================
    # SCENARIO 1: Shift Start - System Overview
    # =========================================================================
    print_header("SCENARIO 1: Technician Shift Start")
    print("Technician: 'How are things going?'")
    print("AI: Gathering system-wide telemetry...")

    analytics_service = AIAnalyticsService()
    system_summary = await analytics_service.get_system_health_summary(
        window_minutes=15
    )

    if system_summary["status"] == "ok":
        print(f"\n[System Telemetry Summary]")
        print(f"  Active Devices (15m): {system_summary['active_devices_count']}")
        print(f"  Critical Devices:     {system_summary['critical_devices_count']}")
        print(f"  Recent Errors:        {system_summary['recent_error_count']}")
        if system_summary["critical_device_ids"]:
            print(
                f"  Alerts on:            {', '.join(system_summary['critical_device_ids'])}"
            )

        # Ask LLM
        if llm_service.check_health():
            print("\nGenerating AI Daily Briefing...")

            shift_context = f"""
[SYSTEM HEALTH REPORT]
Timestamp: {system_summary['timestamp']}
Active Devices: {system_summary['active_devices_count']}
Critical Devices: {system_summary['critical_devices_count']}
List of Critical Devices: {system_summary['critical_device_ids']}
Recent Error Count: {system_summary['recent_error_count']}
"""
            shift_prompt = "You are the HOMEPOT AI Assistant. A technician just started their shift and asked 'How are things going?'. Provide a concise, professional summary of the system status based on the report. If there are critical devices, highlight them immediately."

            response = llm_service.generate_response(
                "How are things going?",
                context=shift_context,
                system_prompt=shift_prompt,
            )
            print("\nAI Response:")
            print("-" * 40)
            print(response)
            print("-" * 40)

            # Pause for effect
            print(
                "\n(Technician acknowledges. Proceeding to deep dive on specific device...)"
            )
            await asyncio.sleep(2)
    else:
        print(f"Error fetching system summary: {system_summary.get('message')}")

    # =========================================================================
    # SCENARIO 2: Deep Dive Analysis
    # =========================================================================
    print_header("SCENARIO 2: Deep Dive Analysis")

    device_id = None
    if event_store.engine:
        try:
            with event_store.engine.connect() as conn:
                # Find the device with the most recent data
                result = conn.execute(
                    text(
                        "SELECT device_id FROM device_metrics ORDER BY timestamp DESC LIMIT 1"
                    )
                ).fetchone()
                if result:
                    device_id = result[0]
        except Exception as e:
            print(f"Warning: Could not auto-detect device: {e}")

    if not device_id:
        device_id = "server-01"  # Fallback
        print(
            f"Warning: No devices found in DB. Defaulting to '{device_id}' (which may fail)."
        )

    print(f"Target Device: {device_id}")

    # Check if we already have recent data in the DB
    existing_events = event_store.get_recent_events(device_id, limit=5)

    if existing_events and len(existing_events) > 0:
        print(f"INFO: Found {len(existing_events)} recent events in database.")
        print("Using existing data from DB for analysis.")
        for e in existing_events:
            ts = e.get("timestamp", "N/A")
            val = e.get("value", {})
            cpu = val.get("cpu_percent", "N/A")
            print(f"  [DB READ] [{ts}] CPU: {cpu}%")
    else:
        print("ERROR: No sufficient data found in database.")
        print(
            f"The demo requires existing data in the 'device_metrics' table for '{device_id}'."
        )
        # sys.exit(1) # Don't exit, try to proceed with prediction even if it fails (it handles errors)

    # 3. Run Predictive Analysis
    print_header("STEP 2: Predictive Maintenance Analysis")
    print("Running FailurePredictor...")

    prediction = await predictor.predict_device_failure(device_id)

    print(f"\nRisk Assessment for {device_id}:")
    print(f"  Risk Level: {prediction.get('risk_level', 'UNKNOWN')}")
    print(f"  Failure Probability: {prediction.get('failure_probability', 0.0)}/1.0")

    risk_factors = [
        f.get("name", "Unknown") for f in prediction.get("risk_factors", [])
    ]
    print(f"  Risk Factors: {risk_factors}")

    if prediction.get("failure_probability", 0) > 0.7:
        print("\n[!] CRITICAL RISK DETECTED")

    # 4. Simulate Context Injection (The "Bridge")
    print_header("STEP 3: Context-Aware AI Query")
    user_query = f"What is the status of {device_id}?"
    print(f'User Query: "{user_query}"')

    # Construct the context (mimicking api.py logic)
    recent_events = event_store.get_recent_events(device_id, limit=5)
    live_context = (
        f"[CURRENT SYSTEM STATUS]\n"
        f"Device ID: {device_id}\n"
        f"Risk Level: {prediction.get('risk_level', 'UNKNOWN')}\n"
        f"Failure Probability: {prediction.get('failure_probability', 0.0)}\n"
        f"Risk Factors: {', '.join(risk_factors)}\n"
        f"Recent Events: {recent_events}\n"
    )

    print("\nGenerated Context Block:")
    print("-" * 40)
    print(live_context.strip())
    print("-" * 40)

    # 5. Generate LLM Response
    print_header("STEP 4: LLM Response Generation")
    print("Mode: MAINTENANCE (Technical Focus)")

    # Check if LLM is available
    if llm_service.check_health():
        print("LLM is online. Generating response...\n")

        # Print what the LLM sees
        system_prompt = mode_manager.get_system_prompt()
        print("DEBUG: LLM Input:")
        print("-" * 40)
        print(f"System Prompt:\n{system_prompt}\n")
        print(f"User Query:\n{user_query}\n")
        print(f"Context:\n{live_context}")
        print("-" * 40)
        print("\n")

        response = llm_service.generate_response(
            user_query,
            context=live_context,
            system_prompt=system_prompt,
        )
        print("AI Response:")
        print("-" * 40)
        print(response)
        print("-" * 40)
    else:
        print("[!] ERROR: LLM Service not reachable (Ollama might be down).")
        print("The demo requires a running LLM service to generate the response.")
        print("Please ensure Ollama is running (e.g., 'ollama serve').")
        # sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_demo())
