# Peripheral Discovery Architecture

## Overview
As the HOMEPOT platform expands into hardware integrations beyond the primary compute endpoint, dealing with "dumb" peripherals (devices without an independent Operating System, such as receipt printers, barcode scanners, and RFID card readers) presents a challenge.

These devices cannot run the HomePot Agent, authenticate using SSO/JWT, or connect directly to the internet to report telemetry. 

To bridge this gap, HOMEPOT utilizes a **Gateway Pattern via Peripheral Discovery**.

## The Gateway Pattern
Instead of attempting direct cloud-to-peripheral communication, the system leverages the primary compute node (the Point-of-Sale terminal, Kiosk, or back-office PC) as a proxy.

1. **Host Registration**: The physical compute node running the GetFudo User App / HomePot Agent registers with the backend normally.
2. **Peripheral Polling**: Periodically, the Agent scans the host Operating System for attached hardware (USB, COM ports, localized networked devices like CUPS printers).
3. **Payload Piggybacking**: The detected hardware profiles are packaged into the `peripherals` dictionary and transmitted alongside the Agent's standard Device DNA and telemetry heartbeats.
4. **Dashboard Representation**: The HOMEPOT backend detects the nested peripheral items and correctly associates them as child components to the parent Host Device within a given Site.

## `real_device_discovery.py`
The orchestration of this polling logic resides in `backend/src/homepot/agent/utils/real_device_discovery.py`. 

This module adheres to the Open-Closed Principle, serving as a unified entry point to execute OS-specific scripts:
- **Windows**: Executes `Get-Printer` via PowerShell.
- **Linux/macOS**: Executes `lpstat -p` via CUPS.

It currently exports a unified dictionary schema:
```json
{
  "printers": [
    {
      "name": "EPSON TM-T88VI",
      "type": "printer",
      "status": "online",
      "connection_type": "CUPS",
      "...": "..."
    }
  ],
  "scanners": [],
  "card_readers": []
}
```

## The Hardware Emulator
During development, UI creation, or fleet load simulation, acquiring hundreds of physical USB printers is impractical. 

The discovery utility implements a seamless override flag: `USE_HARDWARE_EMULATOR=true`. 

When this environment variable is detected:
1. All host OS polling (e.g., PowerShell / CUPS) is bypassed.
2. The agent immediately returns a pre-configured dictionary of "fake" attached hardware (e.g., an "EPSON TM-T88VI (EMULATED)" printer, and a "Zebra DS2200 (EMULATED)" scanner).
3. The fake payloads flow identically through the network architecture, allowing backend engineers and frontend Dealdio React developers to design their logic securely without needing physical hardware.

## Future Roadmap (Phases)
Based on R&D integration specifications, peripheral support is rolling out in distinct phases:
- **Phase 1 - Discovery MVP (Current):** Extend Device DNA to collect and transmit connected peripherals to the backend.
- **Phase 2 - Dashboard Visibility:** Render the extracted JSON arrays securely under the parent device view on the React dashboard.
- **Phase 3 - Test Print / Command Execution:** Implement reverse-proxy command handling (e.g., Dashboard -> Agent -> Printer).
- **Phase 4 - Advanced Health Monitoring:** Monitor specialized edge conditions like "Out of Paper" using customized pycups or pywin32 integration.