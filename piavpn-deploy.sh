#!/bin/bash
set -euo pipefail

# --- CONFIGURATION ---
STAGING_TAR="/tmp/pia-stage.tar.gz"
PIA_VAR_DIR="/var/opt/piavpn"
GID_PIAVPN=955

echo "🚀 Sirius-OS PIA VPN Deployment starting..."

# --- 1. DETECT ATOMIC/OSTREE ---
is_atomic=0
if [ -f /run/ostree-booted ] || grep -q ostree /proc/cmdline 2>/dev/null; then
    is_atomic=1
    echo "🏗️  Atomic environment detected."
else
    echo "💻 Workstation environment detected."
fi

# --- 2. THE ATOMIC BRIDGE (Must run every boot) ---
# This ensures the /opt/piavpn path is valid even on non-Atomic systems
if [ "$is_atomic" -eq 0 ]; then
    if [ ! -L "/opt/piavpn" ]; then
        echo "🔗 Workstation: Correcting /opt/piavpn bridge..."
        umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || true
        rm -rf /opt/piavpn
        ln -sf "$PIA_VAR_DIR" /opt/piavpn
        echo "✅ Bridge created: /opt/piavpn -> $PIA_VAR_DIR"
    fi
fi

# --- 3. CHECK FOR NEW UPDATE PACKAGE ---
# If no new package was made by the Producer, we stop here.
if [[ ! -f "$STAGING_TAR" ]]; then
    echo "✅ No new update package found. Paths are verified. Exiting."
    exit 0
fi

echo "🚚 New update found! Deploying to persistent store..."

# --- 4. PREPARE DIRECTORIES ---
mkdir -p "$PIA_VAR_DIR"
mkdir -p /usr/local/share/applications
mkdir -p /usr/local/share/pixmaps

# Wipe old binaries but PROTECT the 'etc' folder (credentials)
if [[ -d "$PIA_VAR_DIR/bin" ]]; then
    echo "🧹 Cleaning up old binaries..."
    find "$PIA_VAR_DIR" -mindepth 1 -maxdepth 1 ! -name etc -exec rm -rf {} +
fi

# --- 5. EXTRACTION ---

# A. Extract system configs directly to /etc
echo "📦 Extracting system configurations..."
tar -xpzf "$STAGING_TAR" -C / --no-same-owner --wildcards 'etc/*' || true

# B. Extract UI assets and REDIRECT to /usr/local (Atomic bypass)
# We use --strip-components=3 to land files directly in the target folders
echo "🎨 Integrating UI assets (Icon & Menu Entry)..."
tar -xpzf "$STAGING_TAR" --strip-components=3 -C /usr/local/share/applications usr/share/applications/piavpn.desktop || true
tar -xpzf "$STAGING_TAR" --strip-components=3 -C /usr/local/share/pixmaps usr/share/pixmaps/piavpn.png || true

# C. Extract binaries into /var/opt/piavpn but exclude the etc folder
echo "📦 Extracting binaries..."
tar -xpzf "$STAGING_TAR" -C "$PIA_VAR_DIR" --no-same-owner --strip-components=2 \
    --exclude='opt/piavpn/etc' \
    opt/piavpn || true

# Ensure etc exists for fresh installs
if [ ! -d "$PIA_VAR_DIR/etc" ]; then
    mkdir -p "$PIA_VAR_DIR/etc"
fi

# --- 6. INTEGRATION ---
echo "🔧 Configuring system integration..."

# Re-link binaries to /usr/local/bin
ln -sf /var/opt/piavpn/bin/piactl /usr/local/bin/piactl
ln -sf /var/opt/piavpn/bin/pia-daemon /usr/local/bin/pia-daemon
ln -sf /var/opt/piavpn/bin/pia-client /usr/local/bin/pia-client

# Fix paths in the service file (Systemd needs physical path)
if [[ -f /etc/systemd/system/piavpn.service ]]; then
    sed -i -e 's|/opt/piavpn|/var/opt/piavpn|g' /etc/systemd/system/piavpn.service
fi

# Refresh the menu database
update-desktop-database /usr/local/share/applications || true

# Set Ownership & Permissions (Locked GIDs)
chown -R root:root "$PIA_VAR_DIR"
groupadd -r piavpn || true
groupadd -r piahnsd || true
chgrp -R "$GID_PIAVPN" "$PIA_VAR_DIR/etc" 2>/dev/null || :
chmod 750 "$PIA_VAR_DIR/etc"
find "$PIA_VAR_DIR/etc" -name "*.json" -exec chmod 640 {} + 2>/dev/null || :
chmod 755 "$PIA_VAR_DIR/bin/"*

# Networking: Grant DNS capabilities to Unbound
setcap 'cap_net_bind_service=+ep' "$PIA_VAR_DIR/bin/pia-unbound" || true

# --- 7. CLEANUP & ACTIVATE ---
rm -f "$STAGING_TAR"
systemctl daemon-reload
systemctl restart piavpn.service --no-block || true

echo "✨ Update applied successfully."

