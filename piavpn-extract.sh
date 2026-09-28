#!/usr/bin/bash
set -euo pipefail

# --- CONFIGURATION ---
REMOTE_URL="https://www.privateinternetaccess.com/download/linux-vpn"
PIA_VAR_DIR="/var/opt/piavpn"
VERSION_FILE="$PIA_VAR_DIR/share/version.txt"
CONTAINER_NAME="pia-factory"

# DYNAMIC PATHING: Uses the user's runtime cache directory (RAM-based)
# This avoids "Sticky Bit" permission issues found in /tmp
USER_ID=$(id -u)
STAGING_DIR="/run/user/$USER_ID/cache/pia-vpn"
STAGING_TAR="$STAGING_DIR/pia-stage.tar.gz"

# RegEx to match 2 or 3 version segments (e.g., 3.7 or 3.7.2) plus build number
VERSION_REGEX='[0-9]+\.[0-9]+(\.[0-9]+)?[-+][0-9]+'

# Ensure the landing pad exists
mkdir -p "$STAGING_DIR"

# --- CONCURRENCY GUARD ---
# Prevent the timer and a manual `systemctl --user start` from racing,
# and make the service safe to re-run after an interrupted first boot
# (e.g. BlueBuild/Bazzite first-boot reboot tearing down the session).
LOCK="$STAGING_DIR/.extract.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "⏳ Extraction already running in another process; exiting."
    exit 0
fi

# --- RECENT-CHECK CACHE ---
# The timer fires on every boot (OnBootSec=1min 30sec) and monthly
# (OnCalendar=monthly). PIA releases every 3-5 months, so checking
# more than once a day is wasted traffic. Skip the network round trip
# if we checked recently.
#
# 1min 30sec is chosen to clear Bazzite's first-boot session teardown
# (~52s measured). Silverblue has no equivalent teardown, and
# post-first-install boots exit immediately via the version check, so
# this delay is only ever paid once per machine.
#
# The stamp lives in the user's XDG state directory, not in
# /var/opt/piavpn (which is root-owned and not writable from the
# user session that runs this script).
STAMP_FILE="$HOME/.local/state/sirius-os/pia/.last-check"
STAMP_DIR="$(dirname "$STAMP_FILE")"
CHECK_INTERVAL=$((7 * 24 * 3600))  # 7 days in seconds

if [[ -f "$STAMP_FILE" ]]; then
    LAST_CHECK=$(stat -c %Y "$STAMP_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$(( NOW - LAST_CHECK ))

    if (( AGE < CHECK_INTERVAL )); then
        echo "⏩ Last check was $(( AGE / 86400 ))d ago; skipping (interval: 7 days)."
        exit 0
    fi
fi


# --- AUTO-CLEANUP ON EXIT ---
cleanup() {
    if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo "🧹 Auto-cleanup: Removing container '$CONTAINER_NAME'..."
        distrobox rm -f "$CONTAINER_NAME" --yes >/dev/null 2>&1 || :
    fi
}
trap cleanup EXIT

echo "🔍 Sirius-OS: Checking for PIA VPN updates..."

# --- 1. DISCOVERY ---
# curl -f fails on HTTP errors (4xx/5xx). --max-time bounds the hang
# when offline so we don't wait 30+ seconds for a TCP timeout.
# `|| true` on BOTH pipelines prevents set -e/pipefail from killing
# the script when the network is unreachable (curl returns nothing,
# then grep fails on empty input). The offline branch below handles
# the empty LATEST_URL case.
RAW=$(curl -sfL --max-time 30 -A "Mozilla/5.0" "$REMOTE_URL" 2>/dev/null || true)
LATEST_URL=$(echo "$RAW" | \
             grep -oE "https://installers\.privateinternetaccess\.com/download/pia-linux-$VERSION_REGEX\.run" | \
             head -n 1 || true)

if [ -z "$LATEST_URL" ]; then
    if [[ -f "$VERSION_FILE" ]]; then
        echo "⚠️  Network unavailable; PIA already installed, skipping check."
        echo "    The next boot or monthly timer will retry."
        # Do NOT touch the stamp — we want to retry on the next boot.
        exit 0
    fi
    echo "❌ Error: Could not find download URL, and no local install exists."
    exit 1
fi

# Extract and normalize (convert + to -) for a consistent comparison string
LATEST_VER=$(echo "$LATEST_URL" | grep -oE "$VERSION_REGEX" | tr '+' '-' || true)

# --- 2. IDEMPOTENCY ---
if [[ -f "$VERSION_FILE" ]]; then
    # Extract version from file and normalize + to -
    CURRENT_VER=$(grep -oE "$VERSION_REGEX" "$VERSION_FILE" | head -n 1 | tr '+' '-' || echo "none")

    if [[ "$CURRENT_VER" == "$LATEST_VER" ]]; then
        echo "✅ Already up to date ($CURRENT_VER). Nothing to do."
        # Clean up any leftover temp files
        rm -f "$STAGING_TAR" "${STAGING_TAR}.tmp" || true
        # Record the successful check
        mkdir -p "$STAMP_DIR"
        touch "$STAMP_FILE"
        exit 0
    fi
    echo "🏗️ Update found: $CURRENT_VER -> $LATEST_VER"
fi

# --- 3. PRE-FLIGHT CLEANUP ---
echo "🏗️ Preparing build environment..."
rm -f "$STAGING_TAR" "${STAGING_TAR}.tmp" || true

if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "🧹 Detected existing/broken container '$CONTAINER_NAME'. Purging..."
    distrobox rm -f "$CONTAINER_NAME" --yes >/dev/null 2>&1 || :
fi

# --- 4. BUILD IN DISTROBOX ---
echo "📦 Creating fresh build environment (Fedora)..."
distrobox create --name "$CONTAINER_NAME" --image fedora:latest --yes >/dev/null

echo "🛠️ Entering container to prepare binaries..."
# Use -n for non-interactive mode to prevent hangups in background services
distrobox enter -n "$CONTAINER_NAME" -- bash -c "
   set -euo pipefail

   echo '   -> Phase 1/4: Installing build dependencies (dnf)...'
   sudo dnf install -y --nodocs --setopt=install_weak_deps=False \
        wget tar systemd NetworkManager procps-ng libnsl kmod >/dev/null 2>&1

   echo '   -> Phase 2/4: Downloading and verifying PIA v$LATEST_VER...'
   wget -q -O /tmp/pia.run '$LATEST_URL'
   chmod +x /tmp/pia.run
   /tmp/pia.run --check >/dev/null 2>&1 || { echo '❌ Installer integrity check failed!'; exit 1; }

   echo '   -> Phase 3/4: Running installer...'
   # CRITICAL: We do NOT use sudo here. The installer escalates internally.
   /tmp/pia.run --quiet || true

   echo '   -> Phase 4/4: Creating staging archive from container files...'
   sudo tar -czf /tmp/pia-stage.tar.gz -C / \
    opt/piavpn \
    etc/systemd/system/piavpn.service \
    etc/NetworkManager/conf.d/wgpia.conf \
    usr/share/applications/piavpn.desktop \
    usr/share/pixmaps/piavpn.png >/dev/null 2>&1 || true
"

# --- 5. HOST DEPLOYMENT (Atomic Handoff) ---
echo "🚚 Extracting archive to user staging area..."
# 1. Copy from container to hidden temp file first
podman cp "$CONTAINER_NAME":/tmp/pia-stage.tar.gz "${STAGING_TAR}.tmp"
sync "${STAGING_TAR}.tmp"

# 2. Atomic move with -f (Force)
# This replaces any existing file without asking, and triggers the .path watcher
mv -f "${STAGING_TAR}.tmp" "$STAGING_TAR"

# --- 6. RECORD SUCCESSFUL CHECK ---
# Only reached if the full pipeline succeeded. A failed curl, a
# failed container build, or a failed tar staging all exit earlier
# without touching the stamp, so the next boot will retry.
mkdir -p "$STAMP_DIR"
touch "$STAMP_FILE"

echo "🚀 SUCCESS: Archive ready for deployment."
