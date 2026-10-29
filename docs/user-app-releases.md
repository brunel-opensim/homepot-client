# User App Releases & Versioning

How a User App build becomes an installer a technician can download, and the
one rule that keeps it honest: **a version number identifies one set of bytes.**

## 1. The rule

```
one version number  ==  one set of bytes
```

The version number is the identity of a build. Three separate things key on it:

| Consumer | How it uses the version |
|---|---|
| The auto-updater in a packaged app | Polls GitHub, compares against its own version, downloads anything newer |
| The dashboard Downloads page | Renders the version and the SHA-256 of each installer |
| A technician reading the page | Compares the displayed digest against the file they downloaded |

If one version number could mean two different builds, all three disagree — and
the failure is silent. A technician cannot tell which installer is which, and an
updater may believe it already has a version whose bytes it has never seen.

This happened once: `v0.3.0` existed as two byte-sets, because installers were
copied to the server by hand from whichever build happened to be nearby. The
mirror and the guard below exist to make that impossible.

## 2. Where the version lives

`user_app/package.json`, in one place:

```json
{
  "name": "homepot-agent",
  "version": "0.3.2"
}
```

**Nothing increments it automatically.** CI reads it; nobody writes it. A new
version is a deliberate commit:

```bash
npm --prefix user_app version 0.3.2 --no-git-tag-version
```

That updates `package.json` and `package-lock.json`. Commit both.

Because the version is manual, an ordinary merge does **not** produce a release.
Frontend, docs and script changes get built and tested, but no release is
created, because the number did not move.

## 3. What triggers a build

`.github/workflows/user-app-build.yml` runs on:

- a push to `main` touching `user_app/**`, `packaging/**`, `backend/**`, or the workflow itself;
- a pull request touching the same paths (build and test, no publish);
- a manual dispatch with **`publish=true`**.

A push only ever *builds*. Publishing is always a manual dispatch:

```bash
gh workflow run user-app-build.yml --ref main \
  -f publish=true \
  -f api_base_url='https://homepot.cabera.com/api/v1'
```

`api_base_url` is baked into the packaged app. Get it wrong and every installer
points at the wrong backend — the renderer has no `.env` in CI, so without this
the bundle falls back to `http://localhost:8000` and points at the technician's
own machine.

## 4. What a publish run produces

The `publish` job assembles a release with **14 assets**:

| Kind | Files | Notes |
|---|---|---|
| Installers | 7 | `.exe`, `.msi`, `.dmg`, `.zip`, `.AppImage`, `.deb`, `.rpm` |
| Blockmaps | 3 | `.exe`, `.zip`, `.dmg` only — see below |
| Update feeds | 3 | `latest.yml`, `latest-mac.yml`, `latest-linux.yml` |
| Manifest | 1 | `checksums.json` — SHA-256 and SHA-512 per installer |

`checksums.json` is built per platform during packaging, merged by the publish
job, and gated: the build fails if a file a feed references has no checksum
entry, or if the feed's `sha512` disagrees with the file. The Downloads page
shows its `sha256` values; the updater uses the feeds' `sha512`.

**Blockmaps.** electron-updater uses these for differential (delta) updates, so
without them every update downloads the full ~130–165 MB. electron-builder emits
them only for the Windows NSIS installer and the macOS zip/dmg, so exactly three
exist. Note that `latest-linux.yml` advertises a `blockMapSize` for the AppImage
even though no AppImage blockmap is ever written — that is upstream
electron-builder behaviour, it is harmless (the updater falls back to a full
download), and it must **not** be gated on, or every build fails forever.

## 5. The guard: no republishing different bytes

The publish job creates a **draft** release and uploads with `--clobber`. Without
a check, this sequence would silently corrupt a release:

1. merge a change that alters what goes inside the installers;
2. run a build — `package.json` still says `0.3.2`;
3. it reuses the existing `v0.3.2` release and **overwrites** the assets.

The tag would then describe two builds. A rebuild of an *unchanged* tree is
byte-identical, so re-runs look harmless right up until the day they are not.

Before uploading, the job hashes the freshly built assets and compares them
against the release's own per-asset digests:

| Situation | Result |
|---|---|
| Re-run of the same tree (digests match) | passes |
| Rebuild after a change, version not bumped | **fails**, naming the differing files |
| First publish (no release, or no assets yet) | passes |

The failure tells you what to do:

```
ERROR: 1 file(s) differ from the bytes already published under this version.
       The version number is the identity of the bytes: ...
       Bump the version in user_app/package.json and rebuild.
```

Two implementation details worth knowing if you edit this step:

- The release is looked up from the release **list**, not `releases/tags/<tag>`.
  The tag endpoint returns **404 for drafts**, and a draft is the normal case.
- `gh release view --json assets` cannot be used: it does not surface `digest`.

## 6. A publish run leaves a draft

The workflow **never publishes the release**. It creates a draft, so nothing is
visible to devices until someone deliberately promotes it:

```bash
gh release edit v0.3.2 --draft=false --latest
```

This matters because the updater is configured with `releaseType: release`,
which resolves `/releases/latest` — and that excludes both drafts and
prereleases. Promoting is therefore the step that makes devices see a new
version, and it is worth a deliberate look first:

```bash
gh release view v0.3.2 --json tagName,isDraft --jq '"tag=\(.tagName) draft=\(.isDraft)"'
gh release view v0.3.2 --json assets --jq '.assets[] | "\(.size)\t\(.name)"' | sort -k2
```

## 7. Two destinations, one source

A release feeds two things, and they must serve the same bytes:

```
GitHub release  ──>  packaged devices (auto-updater polls /releases/latest)
     │
     └──────────>  dashboard /downloads  (served to technicians)
```

The **GitHub release is the single source of truth.** The server's
`downloads/` directory is a verified *mirror* of it, never a separate copy.
Mirroring, verification and rollback are covered in
[Server Deployment](server-deployment.md#mirroring-the-release-preferred).

Practical consequence: never hand-copy an installer into the server's
`downloads/` directory. Change the release, then re-mirror. Hand-copying is how
`v0.3.0` came to exist as two byte-sets.

## 8. Release checklist

1. Bump the version and commit it:
   ```bash
   npm --prefix user_app version 0.3.X --no-git-tag-version
   ```
2. Merge the bump to `main`.
3. Confirm the build for that commit succeeded.
4. Dispatch the publish run with `publish=true`.
5. Verify the draft before promoting it:
   - **14 assets**, including `checksums.json` and the three blockmaps;
   - every manifest entry matches the release's own digests and sizes;
   - each feed's `sha512` matches the manifest, and its `version:` matches.
6. Promote it: `gh release edit v0.3.X --draft=false --latest`.
7. Dry-run the mirror on the server, then install it:
   ```bash
   DRY_RUN=1 ~/bin/mirror-downloads.sh v0.3.X
   ~/bin/mirror-downloads.sh v0.3.X
   ```
8. Confirm the Downloads page shows the new version with digests, and that
   missing paths now 404 rather than returning the SPA page.

Note that the *dashboard* serving that page has its own independent version:
its commit comes from a frontend build, not from the app version above, and is
visible at `/build-info.json`
([Server Deployment §8](server-deployment.md#is-the-deployed-dashboard-current)).

## 9. Current releases

| Version | Notes |
|---|---|
| `v0.3.2` | Latest. First release carrying blockmaps and `checksums.json`. |
| `v0.3.1` | Has `checksums.json`, no blockmaps. Never mirrored. |
| `v0.3.0` | Predates `checksums.json`; existed as two byte-sets. Superseded. |

---

## 10. Auto-update behavior (end-user experience)

The packaged User App checks for updates automatically. This section documents
the behavior so technicians know what to expect.

### Check schedule
- **First check**: 30 seconds after app launch (lets the app settle)
- **Periodic check**: every 4 hours thereafter
- **Manual check**: technician can trigger via Settings → "Check for Updates"

### Update flow
1. **Checking**: App queries GitHub releases for a newer version
2. **Update available**: OS notification shown ("HOMEPOT Agent update available — Version X is ready to download"). Tray tooltip changes to "HOMEPOT Agent — Update v{version} available"
3. **Download**: User clicks "Download" in Settings; progress shown as percentage
4. **Downloaded**: OS notification shown ("HOMEPOT Agent update ready — Version X has been downloaded. Restart to finish installing.")
5. **Install**: User clicks "Restart to Install" → app quits, installer runs, app relaunches

### Update modes
| Mode | Channel | Notes |
|------|---------|-------|
| Packaged app | GitHub releases (electron-updater) | Reads `latest.yml` / `latest-mac.yml` / `latest-linux.yml` |
| Source checkout (dev) | Git (`git fetch` + `git rev-parse`) | Shows commits behind `origin/main` |
| Neither | Disabled | Reports "Automatic updates are not enabled for this build" |

### What the Dashboard technician sees
- **Settings page**: "Last checked" timestamp + current version
- **Tray icon tooltip**: Changes to show update availability
- **OS notifications**: Native toast when update available and when downloaded

### Important notes
- Updates are **manual install** — the app downloads but does not install automatically. The user must click "Restart to Install".
- The auto-updater only sees **published** releases (not drafts). Drafts are held back until a technician promotes them.
- The agent binary inside the app is updated as part of the app update — no separate agent update needed.
- On Windows, the NSIS installer runs silently and replaces the app in `%LOCALAPPDATA%\Programs\homepot-agent\`.
