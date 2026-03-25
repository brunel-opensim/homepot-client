# Real Device Agent

The `homepot.agent` module is the backend-facing scaffold for a future real-device
agent integration. It currently provides:

- `POST /api/v1/agent/register` for pre-authorized device registration checks.
- `homepot.agent.utils.device_dna` helpers that gather basic host identity data.
- `homepot.agent.real_device_agent` as a starter config-loading entrypoint for the
  GetFudo implementation team.

## Authentication strategy

Device registration is intentionally limited to pre-seeded devices. The
`/register` endpoint validates:

- `device_id` against an existing `Device` record.
- `api_key` against the stored `Device.api_key_hash`.
- `site_id` against the site already associated with that device.

This keeps registration aligned with the existing device authentication model
used by other device-facing APIs in the backend.

## External WAN IP dependency

`device_dna.py` currently uses public IP discovery services to determine WAN IP
information. The current implementation tries these providers in order and
returns the first successful response:

- `https://api.ipify.org`
- `https://ifconfig.me/ip`
- `https://icanhazip.com`

This is still an external dependency and should be treated as best-effort
metadata collection rather than a hard requirement for agent registration.

## Current scope

The agent runtime in `real_device_agent.py` is a placeholder by design. It is
meant to provide a small, documented starting point while the full production
agent lifecycle, command polling, telemetry, and deployment workflow are built
in a separate implementation phase.
