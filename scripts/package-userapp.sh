#!/usr/bin/env bash
# Coordinate native User App packaging from the technician's Linux desktop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_APP_DIR="$REPO_ROOT/user_app"
PACKAGING_DIR="$REPO_ROOT/packaging"
DIST_DIR="$USER_APP_DIR/pyinstaller-dist"
RELEASE_DIR="$USER_APP_DIR/release"
WORK_DIR="${TMPDIR:-/tmp}/homepot-pyinstaller"
ARTIFACT_DIR="$REPO_ROOT/release-artifacts"
WORKFLOW_FILE="user-app-build.yml"

die() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }

usage() {
    cat <<'EOF'
Usage: ./scripts/package-userapp.sh <purpose> [options]

Purposes:
bootstrap       Install locked Node dependencies and PyInstaller build tools.
prepare         Freeze the agent and emulator binaries into pyinstaller-dist/.
test            Run User App linting and tests.
package         Build a Linux package locally for technician testing.
release         Build native macOS, Windows, and Linux packages in GitHub Actions.
download        Download artifacts from the latest or specified packaging run.
all             Run local prepare/test, then create and download a release build.
status          Show local and downloaded package artifacts.
clean           Remove local packaging artifacts.

Options:
--ref <branch>  Git ref to build with release (default: main).
--run-id <id>   GitHub Actions run ID to download.
--publish       Create/update the draft GitHub release after packaging.
--skip-tests   Skip linting and tests when using all.
-h, --help     Show this help.

Examples:
./scripts/package-userapp.sh all
./scripts/package-userapp.sh release --ref main
./scripts/package-userapp.sh download --run-id 123456789
EOF
}

host_platform() {
    case "$(uname -s)" in
        Darwin) echo mac ;;
        Linux) echo linux ;;
        MINGW*|MSYS*|CYGWIN*) echo win ;;
        *) die "Unsupported host operating system: $(uname -s)" ;;
    esac
}

PURPOSE="${1:-}"
[[ -n "$PURPOSE" ]] || { usage; exit 1; }
shift
REF="main"
RUN_ID=""
SKIP_TESTS=false
PUBLISH=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ref)
            [[ -n "${2:-}" ]] || die "--ref requires a value"
            REF="$2"
            shift 2
            ;;
        --run-id)
            [[ -n "${2:-}" ]] || die "--run-id requires a value"
            RUN_ID="$2"
            shift 2
            ;;
        --publish) PUBLISH=true; shift ;;
        --skip-tests) SKIP_TESTS=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done

HOST_PLATFORM="$(host_platform)"

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "'$1' is required"
}

bootstrap() {
    require_command npm
    require_command python3
    info "Installing User App dependencies from package-lock.json"
    (cd "$USER_APP_DIR" && npm ci)
    info "Installing PyInstaller packaging dependencies"
    python3 -m pip install pyinstaller fastapi uvicorn httpx==0.27.0 psutil platformdirs
}

prepare() {
    require_command python3
    python3 -m PyInstaller --version >/dev/null 2>&1 || die "PyInstaller is required; run '$0 bootstrap'."
    info "Freezing the HOMEPOT agent"
    PYTHONPATH="$REPO_ROOT/backend/src${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -m PyInstaller "$PACKAGING_DIR/agent.spec" \
        --distpath "$DIST_DIR" --workpath "$WORK_DIR/agent"
    info "Freezing the HOMEPOT emulator"
    python3 -m PyInstaller "$PACKAGING_DIR/emulator.spec" \
        --distpath "$DIST_DIR" --workpath "$WORK_DIR/emulator"
}

test_user_app() {
    require_command npm
    [[ -d "$USER_APP_DIR/node_modules" ]] || die "Dependencies are missing; run '$0 bootstrap'."
    (cd "$USER_APP_DIR" && npm run lint && npm test)
}

package() {
    [[ "$HOST_PLATFORM" == linux ]] || die "Local packaging is reserved for the Linux technician desktop."
    require_command npm
    [[ -d "$DIST_DIR/homepot-agent" && -d "$DIST_DIR/homepot-emulator" ]] || die "Frozen binaries are missing; run '$0 prepare'."
    [[ -d "$USER_APP_DIR/node_modules" ]] || die "Dependencies are missing; run '$0 bootstrap'."
    info "Packaging User App for Linux"
    (cd "$USER_APP_DIR" && npx electron-builder --linux --publish never)
}

require_github_auth() {
    require_command gh
    gh auth status >/dev/null 2>&1 || die "GitHub CLI authentication is required; run 'gh auth login'."
}

latest_run_id() {
    local created_after="${1:-0}"
    gh run list --workflow "$WORKFLOW_FILE" --branch "$REF" --event workflow_dispatch \
        --limit 20 --json databaseId,createdAt \
        --jq ".[] | select(.createdAt | fromdateiso8601 >= $created_after) | .databaseId" \
        | head -1
}

release() {
    require_github_auth
    info "Dispatching native macOS, Windows, and Linux packaging for ref '$REF'"
    local publish=false
    local dispatch_started_at
    dispatch_started_at="$(date -u +%s)"
    if $PUBLISH; then publish=true; fi
    gh workflow run "$WORKFLOW_FILE" --ref "$REF" -f "publish=$publish"
    info "Waiting for the packaging workflow to be registered"
    local attempts=0
    while [[ -z "$RUN_ID" && $attempts -lt 10 ]]; do
        RUN_ID="$(latest_run_id "$dispatch_started_at")"
        [[ -n "$RUN_ID" ]] || sleep 2
        ((attempts++)) || true
    done
    [[ -n "$RUN_ID" ]] || die "Could not determine the GitHub Actions run ID; use '$0 download --run-id <id>'."
    info "Watching GitHub Actions run $RUN_ID"
    gh run watch "$RUN_ID" --exit-status
    download
}

download() {
    require_github_auth
    if [[ -z "$RUN_ID" ]]; then
        RUN_ID="$(latest_run_id)"
    fi
    [[ -n "$RUN_ID" ]] || die "No packaging workflow run found for ref '$REF'."
    mkdir -p "$ARTIFACT_DIR/$RUN_ID"
    info "Downloading artifacts from GitHub Actions run $RUN_ID"
    gh run download "$RUN_ID" --dir "$ARTIFACT_DIR/$RUN_ID"
    info "Artifacts are available in $ARTIFACT_DIR/$RUN_ID"
}

show_status() {
    echo "Host platform: $HOST_PLATFORM"
    echo "Frozen binaries:"
    find "$DIST_DIR" -maxdepth 2 -type f -perm -111 -print 2>/dev/null || true
    echo "Packaged artifacts:"
    find "$RELEASE_DIR" -maxdepth 3 \( -name '*.app' -o -name '*.dmg' -o -name '*.zip' -o -name '*.AppImage' -o -name '*.deb' -o -name '*.rpm' -o -name '*.exe' -o -name '*.msi' \) -print 2>/dev/null || true
    echo "Downloaded release artifacts:"
    find "$ARTIFACT_DIR" -type f \( -name '*.dmg' -o -name '*.zip' -o -name '*.AppImage' -o -name '*.deb' -o -name '*.rpm' -o -name '*.exe' -o -name '*.msi' \) -print 2>/dev/null || true
}

clean() {
    info "Removing local frozen binaries, package output, and PyInstaller work files"
    rm -rf "$DIST_DIR" "$RELEASE_DIR" "$ARTIFACT_DIR" "$WORK_DIR"
}

case "$PURPOSE" in
    bootstrap) bootstrap ;;
    prepare) prepare ;;
    test) test_user_app ;;
    package) package ;;
    release) release ;;
    download) download ;;
    all)
        [[ "$HOST_PLATFORM" == linux ]] || die "The distribution workflow must be run from the Linux technician desktop."
        prepare
        if ! $SKIP_TESTS; then test_user_app; fi
        release
        ;;
    status) show_status ;;
    clean) clean ;;
    -h|--help|help) usage ;;
    *) die "Unknown purpose: $PURPOSE" ;;
esac