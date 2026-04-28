# User App Implementation Guide

## Overview
The HOMEPOT User App is a lightweight native client agent (acting as a "Digital Security Badge") designed to run continuously on employee devices (Android, Windows, macOS, Linux). It operates completely independently of the centralized web-based Admin Dashboard.

This implementation utilizes a **Hybrid Monolith** architecture: compiling a single shared React UI into native Desktop shells (via Electron) and Mobile shells (via Capacitor).

## Directory Setup
The frontend source code is isolated within the top-level `/user_app` directory to prevent any cross-contamination with the core Admin Dashboard (`/frontend`).

## Prerequisites
To develop the User App, ensure you have the following installed locally:
*   **Node.js**: v18+ (Node v20 LTS recommended)
*   **npm**: Standard package manager
*   *(Future)* Desktop build tools for Electron (e.g., MSVC on Windows, Xcode on macOS)
*   *(Future)* Android Studio / SDKs for building the mobile APK via Capacitor.

## Tech Stack
The foundational UI stack mirrors the Admin Dashboard to allow for seamless code reuse:
*   **Core**: React 19 + TypeScript
*   **Bundler**: Vite (SWC)
*   **Styling**: Tailwind CSS v3.4.x + Radix UI

## Getting Started Locally

Currently, the scaffolding can be run as a standard development web server:

```bash
# 1. Navigate to the application directory
cd user_app

# 2. Install required dependencies
npm install

# 3. Start the local development server (typically opens on port 5173)
npm run dev
```

## Implementation Phases
1. **Phase 1 (Current):** Web-based UI layout and scaffolding using Tailwind CSS and raw React components.
2. **Phase 2:** Wrapping the Vite build in **Electron** (for Desktop OS logic) and **Capacitor** (for Android logic).
3. **Phase 3:** Connecting the React context state to the local IPC network layer broadcasted by the underlying Python device agent (developed by Dealdio).
