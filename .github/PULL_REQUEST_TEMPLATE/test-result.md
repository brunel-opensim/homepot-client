---
name: Device Test Result
about: Submit completed device testing results
title: 'test: [PLATFORM] [DEVICE] device testing results'
labels: 'test-result'
---

## Test Result Submission

- **Device**: (e.g., Brunel Device 001)
- **Device ID**: (e.g., DEVICE-XXXX-XXXX-XXXX)
- **Platform**: Windows 10 / Windows 11 / macOS / Linux / Android
- **Agent Version**: (check Device Details → Source)
- **Tester**: 
- **Date**: 
- **Test template file**: `docs/test-results/<platform>-<device>-<date>.md`

## Summary

| Section | Total | Pass | Fail | Blocked |
|---------|-------|------|------|---------|
| 1. Registration | 6 | | | |
| 2. Apply Configuration | 8 | | | |
| 3. Direct Connect | 5 | | | |
| 4. Compose Command | 17 | | | |
| 5. Push History | 5 | | | |
| 6. Live Logs & Audit | 5 | | | |
| 7. Device Health | 5 | | | |
| 8. Offline & Resilience | 5 | | | |
| 9. Auto-Update | 5 | | | |
| 10. Logs & Files | 5 | | | |
| **Total** | **66** | | | |

## Failed tests (if any)

List any failed tests with details:

- Test X.Y: description of failure and observed behavior

## Blocked tests (if any)

List any blocked tests and the reason:

- Test X.Y: reason (e.g., "requires physical access to device")

## Additional notes

Any other observations, screenshots, or context.