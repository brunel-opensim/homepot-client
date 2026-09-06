#!/bin/sh
# homepot-ctl-install.sh — one-time OS elevation install for the Homepot User App.
#
# Run through an OS admin prompt (osascript "with administrator privileges" on
# macOS, pkexec on Linux) so it executes as root. It installs the scoped
# `homepot-ctl` helper and grants the app user a NOPASSWD rule for that single
# helper — never `ALL`, never a raw shell.
#
# Usage:
#   homepot-ctl-install.sh --ctl <source-homepot-ctl> [--uid <user>] [--root <target>]
#
# After a revoke the User App tears the drop-in down via `sudo -n homepot-ctl
# deprovision`. A future re-grant re-runs this installer (another admin prompt).
set -eu

CTL_SRC=""
TARGET_USER=""
if [ -n "${HOMEPOT_ELEVATION_ROOT:-}" ]; then
  BASE="$HOMEPOT_ELEVATION_ROOT"
else
  BASE=""
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ctl) CTL_SRC="$2"; shift 2 ;;
    --uid) TARGET_USER="$2"; shift 2 ;;
    --root) BASE="$2"; shift 2 ;;
    *) echo "homepot-ctl-install: unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$CTL_SRC" ] || [ ! -f "$CTL_SRC" ]; then
  echo "homepot-ctl-install: --ctl <source-homepot-ctl> is required" >&2
  exit 2
fi

if [ -n "$BASE" ]; then
  INSTALL_DIR="$BASE"
  SUDOERS_DIR="$BASE/sudoers.d"
else
  INSTALL_DIR="/usr/local/homepot"
  SUDOERS_DIR="/etc/sudoers.d"
fi

umask 022
mkdir -p "$INSTALL_DIR" "$SUDOERS_DIR"
install -m 0755 "$CTL_SRC" "$INSTALL_DIR/homepot-ctl"
chmod 0755 "$INSTALL_DIR/homepot-ctl"
# Best-effort ownership; on non-root installs (tests / staging with a writable
# --root) the surrounding `set -eu` must not abort on a failed chown.
chown root:wheel "$INSTALL_DIR/homepot-ctl" 2>/dev/null || chown root:root "$INSTALL_DIR/homepot-ctl" 2>/dev/null || true

if [ -n "$TARGET_USER" ]; then
  rule="$TARGET_USER ALL=(ALL) NOPASSWD: $INSTALL_DIR/homepot-ctl"
  umask 077
  printf '%s\n' "$rule" > "$SUDOERS_DIR/homepot"
  chmod 0440 "$SUDOERS_DIR/homepot"
fi