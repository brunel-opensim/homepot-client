# Device Test Results

This directory contains device testing templates and completed test reports.

## For test engineers

### 1. Get the template

Copy the template file to a new file with the correct naming convention:

```bash
cp docs/test-results/windows-device-template.md \
   docs/test-results/<platform>-<org>-<date>.md
```

**Naming convention:** `<platform>-<org>-<YYYY-MM-DD>.md`

- **Platform**: `windows10`, `windows11`, `macos`, `linux`, `android`
- **Org**: lowercase organisation slug (e.g., `brunel`, `getfudo`, `dealdio`)
- **Date**: `YYYY-MM-DD` (ISO format)

Examples:
- `docs/test-results/windows11-brunel-2026-11-23.md`
- `docs/test-results/windows10-getfudo-2026-11-02.md`
- `docs/test-results/macos-brunel-2026-11-05.md`

### 2. Fill in the template

Open your copy and fill in every field in the **Test environment** table and all
test sections. Do not leave placeholder values (`DEVICE-XXXX-XXXX-XXXX`).

### 3. Submit for review

1. Create a branch: `git checkout -b test/<platform>-<org>-<date>`
2. Add your file: `git add docs/test-results/<your-file>.md`
3. Commit: `git commit -m "test(device): add <platform> test results for <org>"`
4. Push and open a PR for review.

Only the template (`windows-device-template.md`) and completed test reports
should be in this directory. Do not add fix lists, notes, or other files.
EOF