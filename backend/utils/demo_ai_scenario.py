#!/usr/bin/env python3
"""
HOMEPOT AI Capability Demo.

This script demonstrates the full AI pipeline:
1. Data Ingestion (EventStore)
2. Predictive Analysis (FailurePredictor)
3. Context-Aware Intelligence (LLM + RAG)

Scenario: A server ('server-01') is experiencing a rapid CPU spike.
"""

import logging
import os
import sys

# Add ai directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ai")))

from analysis_modes import ModeManager
from event_store import EventStore
from failure_predictor import FailurePredictor
from llm import LLMService
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DEMO")


def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def run_demo():
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

    # 2. Auto-Detect Device
    print_header("STEP 1: Data Acquisition")

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
        sys.exit(1)

    # 3. Run Predictive Analysis
    print_header("STEP 2: Predictive Maintenance Analysis")
    print("Running FailurePredictor...")

    prediction = predictor.predict_failure_risk(device_id)

    print(f"\nRisk Assessment for {device_id}:")
    print(f"  Risk Level: {prediction['risk_level']}")
    print(f"  Risk Score: {prediction['score']}/1.0")
    print(f"  Reasons:    {prediction['reasons']}")

    if prediction["score"] > 0.7:
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
        f"Risk Score: {prediction.get('score', 0.0)}\n"
        f"Risk Factors: {', '.join(prediction.get('reasons', []))}\n"
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
        response = llm_service.generate_response(
            user_query,
            context=live_context,
            system_prompt=mode_manager.get_system_prompt(),
        )
        print("AI Response:")
        print("-" * 40)
        print(response)
        print("-" * 40)
    else:
        print("[!] ERROR: LLM Service not reachable (Ollama might be down).")
        print("The demo requires a running LLM service to generate the response.")
        print("Please ensure Ollama is running (e.g., 'ollama serve').")
        sys.exit(1)


if __name__ == "__main__":
    run_demo()
