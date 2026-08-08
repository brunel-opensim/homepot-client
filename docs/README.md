# HOMEPOT Client Documentation

This directory contains the full user, operator, and developer documentation,
published to **Read the Docs** (mkdocs). Use its **short links** whenever you
need to reference a topic:

```bash
https://homepot-client.readthedocs.io/en/latest/
```

## Entry points

- **[Getting Started](getting-started.md)** - First-time setup and running locally
- **[Device Emulators](device-emulators.md)** - Simulators/emulators reference
- **[Data Collection](data-collection-guide.md)** - Collecting real telemetry for AI training

## Structure

- `index.md` — the mkdocs home page (Read the Docs landing)
- `<topic>.md` — one markdown file per documentation topic
- `mkdocs.yml` — site configuration (site name, nav, theme, plugins)

## Building locally

```bash
mkdocs serve    # live preview at http://localhost:8000
```

> The docs are listed under **`docs/`** in the monorepo Project Structure tree;
> see the top-level [`README.md`](../README.md) for the overall layout.