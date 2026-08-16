# UK Demonstrator KPI Evidence

This directory holds versioned KPI export bundles produced by the UK
demonstrator calculation (`backend/src/homepot/kpi/`). The contents are
**generated** and the directory is listed in `.gitignore` (only this
`README.md` is tracked), mirroring the `logs/` convention.

## Generating an export

From the repository root:

```bash
./scripts/kpi-export.sh \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-31T23:59:59Z
```

The wrapper resolves the venv and the database URL so it works from the repo
root without activating a virtualenv. When the venv is active you can call the
CLI directly: `homepot-client kpi-export ...`.

Each run writes a self-contained directory named by its **run ID** (a UTC
timestamp, e.g. `20260816T220500Z`, or an explicit `--run-id`):

```
kpi-evidence/
└── <run-id>/
    ├── kpi-export.json   # manifest + kpis + raw evidence
    └── kpi-summary.csv   # machine-readable KPI summary (--format csv)
```

Pass `--out-dir` to write elsewhere.

## Reproducibility

Every export records its `calculation_version`, `git_commit`, reporting
timezone (`UTC`), filters, and the raw evidence rows backing each value, so a
reviewer can pin any number to an exact code revision and data snapshot.

See [docs/kpi-export.md](../docs/kpi-export.md) for the full register of KPIs,
their formulas, units, and the manifest contract.
