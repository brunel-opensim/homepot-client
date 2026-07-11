# Fleet Simulation Load Testing

## Overview
As the HOMEPOT platform migrates to a highly scalable architecture using PostgreSQL and TimescaleDB, it is critical to ensure that the backend infrastructure can handle high-volume, concurrent telemetry from managed endpoints. 

The **Fleet Simulation framework** allows developers to safely load-test the API endpoints and database connections before moving code into production or Dockerized environments. By generating concurrent, randomized metric payloads (including future support for nested structures like Printer DNA), engineers can identify connection limits, memory leaks, and processing bottlenecks.

## Purpose
- **Verify Scalability:** Test how the backend performs when hundreds or thousands of devices sync metrics simultaneously.
- **Database Connection Pooling validation:** Ensure the SQLAlchemy/PostgreSQL configuration is tuned to handle concurrent async requests without resource exhaustion.
- **New Feature Stress-Testing:** Provide a foundation to test nested payloads, such as the upcoming Printer array, mimicking real-world edge devices safely.

## Simulator Design
The standalone runner script `backend/utils/run_fleet_simulation.py` acts as a driver to orchestrate multiple simulated edge devices using Python's `asyncio` and `httpx`.

### Key Characteristics
1. **Accurate Seed Mapping:** The simulation maps exactly to the realistic subset of expected mock devices defined in `backend/utils/seed_data.py` (e.g., `site1-linux-01`, `site2-macos-03`).
2. **Concurrency Control:** Utilizes `asyncio.Semaphore` and `httpx.Limits` to strictly throttle the maximum active TCP connections. This simulates scale without causing native OS socket port exhaustion locally (ephemeral port exhaustion).
3. **Scatter & Gather Timing:** Employs randomized `asyncio.sleep()` delays between requests to create realistic traffic distributions ("jitter"), perfectly mimicking thousands of endpoints syncing asynchronously over WAN.
4. **Behavioral Variance:** Automatically rotates through varied telemetry scenarios (`healthy`, `low_memory`, `high_errors`) natively supported by the `/api/v1/testing/simulate/device` fast API endpoint.

## Running the Simulation

### Prerequisites
Ensure your backend environment supports `httpx`:
```bash
source .venv/bin/activate
pip install httpx
```

Ensure the HOMEPOT backend is fully running:
```bash
./scripts/start-dashboard.sh
```

### Execution
Run the fleet simulator from the project root:
```bash
python3 backend/utils/run_fleet_simulation.py
```

### Interpreting Output
The simulation runs for a predetermined amount of time (configurable within the script via `SIMULATION_DURATION_SECONDS`). Upon completion, the console provides output logging the total requests successfully ingested by PostgreSQL:
```
--- Simulation Complete ---
Active Devices: 10
Total Successful Metrics Pushed: 178
Device Loop Errors: 0
Average req/sec: 2.97
```

## Configuring the Simulation
Developers can easily alter the load parameters within `backend/utils/run_fleet_simulation.py`:
- `NUM_DEVICES`: *Currently configured to track the array of predefined seed records, but easily modifiable to scale into the hundreds.*
- `SIMULATION_DURATION_SECONDS`: How long the load test runs. By default `60` seconds.
- `CONCURRENT_REQUESTS_LIMIT`: Max simultaneous connections sent to the API. Increase alongside database pool optimizations.
- `SAMPLE_PRINTERS`: Placeholder for upcoming R&D hardware expansion testing.
