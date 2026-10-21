#!/usr/bin/env bash
#
# Mirror the published GitHub release into the dashboard's /downloads directory.
#
# Why this exists
# ---------------
# The Downloads page and the app's auto-updater must serve the SAME bytes for a
# given version. Previously the installers were copied to the server by hand
# from whatever build happened to be nearby, which allowed two different builds
# to both call themselves "v0.3.0" -- indistinguishable to a technician and
# hazardous to the updater, which keys on the version number.
#
# This script makes the GitHub release the single source of truth:
#
#   1. resolve a release (default: the latest published, non-draft release)
#   2. download its assets anonymously (the repo is public; no token needed)
#   3. verify each download against GitHub's own per-asset sha256 digest
#   4. verify the release's checksums.json against the bytes too
#   5. stage into a temporary directory and swap it in atomically
#
# Nothing is deleted from the live directory until the new set has fully
# downloaded and verified, so a failed or interrupted run leaves the current
# downloads serving exactly as before.
#
# The installers are large (~1 GB total), so a partial mirror is the normal
# failure mode. Staging plus verification is what makes that harmless.
#
# Usage:
#   ./scripts/mirror-downloads.sh                  # latest release
#   ./scripts/mirror-downloads.sh v0.3.0           # a specific tag
#   DRY_RUN=1 ./scripts/mirror-downloads.sh        # verify, do not install
#   TARGET_DIR=/path ./scripts/mirror-downloads.sh # override destination
#
set -euo pipefail

REPO="brunel-opensim/homepot-client"
TAG="${1:-}"
DRY_RUN="${DRY_RUN:-0}"
TARGET_DIR="${TARGET_DIR:-/var/www/homepot.cabera.com/frontend/dist/downloads}"

API="https://api.github.com/repos/${REPO}"

log()  { printf '%s\n' "$*" >&2; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

command -v curl    >/dev/null || fail "curl is required"
command -v python3 >/dev/null || fail "python3 is required"

# Check the destination before downloading a gigabyte into it.
[ -d "$TARGET_DIR" ] || fail "target directory does not exist: $TARGET_DIR"
[ -w "$TARGET_DIR" ] || fail "target directory is not writable: $TARGET_DIR"

# --- 1. Resolve the release -------------------------------------------------
if [ -z "$TAG" ]; then
  log "Resolving the latest published release of ${REPO}..."
  RELEASE_JSON=$(curl -fsSL --max-time 60 "${API}/releases/latest") \
    || fail "could not read the latest release (is it published, not a draft?)"
else
  log "Resolving release ${TAG}..."
  RELEASE_JSON=$(curl -fsSL --max-time 60 "${API}/releases/tags/${TAG}") \
    || fail "no such release: ${TAG}"
fi

# Refuse to mirror a draft: drafts can still change, so their bytes are not a
# stable promise. This is the whole point of treating the release as truth.
RESOLVED=$(printf '%s' "$RELEASE_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(json.dumps({
    "tag": d["tag_name"],
    "draft": d["draft"],
    "assets": [
        {"name": a["name"], "size": a["size"],
         "digest": (a.get("digest") or ""),
         "url": a["browser_download_url"]}
        for a in d["assets"]
    ],
}))
')
printf '%s' "$RESOLVED" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if d["draft"]:
    sys.exit("ERROR: %s is a DRAFT release; refusing to mirror mutable bytes" % d["tag"])
if not d["assets"]:
    sys.exit("ERROR: %s has no assets" % d["tag"])
print("  tag:    %s" % d["tag"], file=sys.stderr)
print("  assets: %d" % len(d["assets"]), file=sys.stderr)
for a in d["assets"]:
    if not a["digest"].startswith("sha256:"):
        sys.exit("ERROR: asset %s has no sha256 digest; cannot verify" % a["name"])
' || fail "release validation failed"

# --- 2/3/4. Download and verify into a staging directory --------------------
# Stage on the same filesystem as the target so the final swap is a rename
# (atomic) rather than a copy across devices.
STAGE_ROOT="$(cd "$(dirname "$TARGET_DIR")" && pwd)"
STAGE="${STAGE_ROOT}/.downloads-staging.$$"
# Handed to python3 through the environment: see the note at the download loop.
STAGE_DIR="$STAGE"
export STAGE_DIR
rm -rf "$STAGE"
mkdir -p "$STAGE"

cleanup() {
  if [ -d "$STAGE" ]; then rm -rf "$STAGE"; fi
}
trap cleanup EXIT

log ""
log "Downloading and verifying into staging: $STAGE"

printf '%s' "$RESOLVED" | python3 -c '
import hashlib, json, os, subprocess, sys

d = json.load(sys.stdin)
# The staging path arrives via the environment, not as an argv argument. A
# stray apostrophe in the code text below would otherwise close the shell quote
# early and silently shift the argument, which is how a relative path once got
# used here. An environment variable cannot be displaced that way.
stage = os.path.abspath(os.environ["STAGE_DIR"])
if not os.path.isdir(stage):
    sys.exit("ERROR: staging directory does not exist: %s" % stage)
ok = True

for a in d["assets"]:
    name, want = a["name"], a["digest"].split(":", 1)[1].lower()
    dest = os.path.join(stage, name)
    # These transfers are large (~1 GB total) and a transient network or write
    # hiccup is the expected failure, not an exception. Retries are explicit
    # rather than delegated to curl alone so we can remove a partial file
    # between attempts: a leftover partial is what makes curl fail with
    # "Failure writing output to destination" on the retry.
    for attempt in range(1, 5):
        if os.path.exists(dest):
            os.remove(dest)
        r = subprocess.run(
            ["curl", "-fsSL",
             "--retry", "5", "--retry-delay", "5", "--retry-all-errors",
             "--max-time", "1800", "--speed-time", "60", "--speed-limit", "1024",
             "-o", dest, a["url"]],
            capture_output=True,
        )
        if r.returncode == 0 and os.path.exists(dest):
            break
        detail = r.stderr[:120].decode(errors="replace").strip() or f"rc={r.returncode}"
        print("  retry %d/4 for %s (%s)" % (attempt, name, detail), file=sys.stderr)
    else:
        print("ERROR: could not download %s" % name, file=sys.stderr)
        ok = False
        continue

    size = os.path.getsize(dest)
    if size != a["size"]:
        print("ERROR: %s size %d != release %d" % (name, size, a["size"]), file=sys.stderr)
        ok = False
        continue

    h = hashlib.sha256()
    with open(dest, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != want:
        print("ERROR: %s sha256 %s != release %s" % (name, got, want), file=sys.stderr)
        ok = False
        continue
    print("  ok: %-45s %14d  sha256 verified" % (name, size), file=sys.stderr)

# The release checksums.json (present from #540 onward) must agree with the
# bytes we just verified. It is the same manifest the Downloads page displays,
# so a mismatch here means the page would show a digest the file does not have.
#
# Its absence is a hard failure, not a warning: mirroring a release without it
# would silently strip the digests from the Downloads page, which is worse than
# not mirroring. Releases published before #540 predate the manifest.
manifest = os.path.join(stage, "checksums.json")
if not os.path.exists(manifest):
    print("ERROR: the release has no checksums.json, so the Downloads page would\n"
          "       show no digests. Re-publish the release with the manifest\n"
          "       (the packaging job produces it) before mirroring.",
          file=sys.stderr)
    sys.exit(1)

with open(manifest) as fh:
    files = json.load(fh).get("files", {})
if not files:
    print("ERROR: checksums.json is empty", file=sys.stderr)
    sys.exit(1)

# Every artifact we mirrored must be described, and every described file must
# be present -- otherwise the page would advertise a file that is not served.
for name in sorted(files):
    if not os.path.exists(os.path.join(stage, name)):
        print("ERROR: checksums.json lists %s but it was not downloaded" % name, file=sys.stderr)
        ok = False

# Compare the digests in the manifest against the verified bytes. The GitHub
# digest already matched, so a disagreement here means the manifest describes a
# different build -- exactly the drift this script exists to prevent.
for name, entry in sorted(files.items()):
    path = os.path.join(stage, name)
    if not os.path.exists(path):
        continue
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != str(entry.get("sha256", "")).lower():
        print("ERROR: checksums.json sha256 for %s does not match the release asset" % name,
              file=sys.stderr)
        ok = False
    if entry.get("size") is not None and entry["size"] != os.path.getsize(path):
        print("ERROR: checksums.json size for %s does not match the release asset" % name,
              file=sys.stderr)
        ok = False

print("  ok: checksums.json (%d entries, all verified against the assets)" % len(files),
      file=sys.stderr)

sys.exit(0 if ok else 1)
' || fail "verification failed; the live downloads were not changed"

# --- 5. Swap in -------------------------------------------------------------
log ""
if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN=1: verified $(ls -1 "$STAGE" | wc -l) files; not installing."
  exit 0
fi

# Warn about blockmap *targets* the live set has and the staged set lacks. Not
# fatal: the app still updates, just without a differential download. But it is
# a silent regression in update size, so say it out loud rather than let the
# swap hide it.
#
# Compared by the extension the blockmap belongs to (".exe", ".zip", ".dmg"),
# not by filename: a version bump renames every file, so a plain name diff
# would report every blockmap as lost on every release. What matters is
# whether the new set still carries a blockmap for each target kind, since the
# feed's blockMapSize is per target, not per version.
if command -v diff >/dev/null; then
  kinds() { ls -1 "$1"/*.blockmap 2>/dev/null | sed -E 's/\.blockmap$//; s/.*(\.[a-zA-Z0-9]+)$/\1/' | sort -u; }
  LOST=$(comm -23 <(kinds "$TARGET_DIR") <(kinds "$STAGE"))
  if [ -n "$LOST" ]; then
    log "Warning: the live set has blockmaps for targets the release does not:"
    printf '  *%s\n' $LOST >&2
    log "Updates of those targets will fall back to a full download."
  fi
fi

# Move the old set aside, move the new one in, then remove the old one. At no
# point is the live directory empty: the gap between the two renames is a
# single filesystem operation on the same directory. Existence was checked
# before the download, so a bad path fails without transferring a gigabyte.
BACKUP="${TARGET_DIR}.old.$(date -u +%Y%m%dT%H%M%SZ)"
mv "$TARGET_DIR" "$BACKUP"
mv "$STAGE" "$TARGET_DIR"
log "Installed $(ls -1 "$TARGET_DIR" | wc -l) files into $TARGET_DIR"
log "Previous set kept for rollback at $BACKUP"
