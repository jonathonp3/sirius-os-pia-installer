#!/bin/bash
set -euo pipefail

# --- CONFIGURATION ---
REMOTE_URL="https://www.privateinternetaccess.com/download/linux-vpn"
PIA_VAR_DIR="/var/opt/piavpn"
VERSION_FILE="$PIA_VAR_DIR/share/version.txt"
CONTAINER_NAME="pia-factory"
STAGING_TAR="/tmp/pia-stage.tar.gz"

echo "🔍 Sirius-OS: Checking for PIA VPN updates..."

# --- 1. DISCOVERY ---
LATEST_URL=$(curl -sL -A "Mozilla/5.0" $REMOTE_URL | \
             grep -oE 'https://installers\.privateinternetaccess\.com/download/pia-linux-[0-9.]+-[0-9]+\.run' | \
             head -n 1)

if [ -z "$LATEST_URL" ]; then
    echo "❌ Error: Could not find download URL."
    exit 1
fi

LATEST_VER=$(echo "$LATEST_URL" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+')

# --- 2. IDEMPOTENCY (Skip if same) ---
if [[ -f "$VERSION_FILE" ]]; then
    CURRENT_VER=$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+' "$VERSION_FILE" | head -n 1 || echo "none")
    if [[ "$CURRENT_VER" == "$LATEST_VER" ]]; then
        echo "✅ Already up to date ($CURRENT_VER). Nothing to do."
        # Delete any old staging files to be safe
        rm -f "$STAGING_TAR"
        exit 0
    fi
fi

# --- 3. BUILD IN DISTROBOX ---
echo "🏗️ Update found! Building v$LATEST_VER in Distrobox..."

# Clean up any old files
rm -f "$STAGING_TAR"
distrobox rm -f "$CONTAINER_NAME" --yes >/dev/null 2>&1 || :

# Create and enter factory
distrobox create --name "$CONTAINER_NAME" --image fedora:latest --yes >/dev/null
distrobox enter "$CONTAINER_NAME" -- bash -c "
   set -euo pipefail
   sudo dnf install -y wget tar systemd NetworkManager procps-ng libnsl >/dev/null
   wget -q -O /tmp/pia.run '$LATEST_URL'
   chmod +x /tmp/pia.run
   /tmp/pia.run --quiet || true
   
   # Create the archive inside the container
   sudo tar -czf /tmp/pia-stage.tar.gz \
     /opt/piavpn \
     /etc/systemd/system/piavpn.service \
     /etc/NetworkManager/conf.d/wgpia.conf \
     /usr/share/applications/piavpn.desktop \
     /usr/share/pixmaps/piavpn.png || true
"

# 4. Pull the archive to the host /tmp folder
echo "📦 Capturing binaries..."
podman cp "$CONTAINER_NAME":/tmp/pia-stage.tar.gz "$STAGING_TAR"

# 5. Cleanup the container
distrobox rm -f "$CONTAINER_NAME" --yes >/dev/null
echo "🚀 Extraction complete. Archive is ready for root deployment."

