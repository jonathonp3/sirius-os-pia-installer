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
fi

# --- 2. THE ATOMIC BRIDGE (Moved to the TOP) ---
# This MUST run every time, even if there is no update, to ensure the app works.
if [ "$is_atomic" -eq 0 ]; then
    if [ ! -L "/opt/piavpn" ]; then
        echo "🔗 Workstation detected: Correcting /opt/piavpn bridge..."
        
        # Unmount virtual filesystem if it exists
        umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || true
        
        # Delete the real folder so we can replace it with a link
        rm -rf /opt/piavpn
        
        # Create the symlink
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

# --- 4. DEPLOYMENT LOGIC (Same as before) ---
mkdir -p "$PIA_VAR_DIR"
find "$PIA_VAR_DIR" -mindepth 1 -maxdepth 1 ! -name etc -exec rm -rf {} +

tar -xpzf "$STAGING_TAR" -C / --no-same-owner --wildcards 'etc/*' || true
tar -xpzf "$STAGING_TAR" -C "$PIA_VAR_DIR" --no-same-owner --strip-components=2 --exclude='opt/piavpn/etc' opt/piavpn || true

if [ ! -d "$PIA_VAR_DIR/etc" ]; then
    mkdir -p "$PIA_VAR_DIR/etc"
fi

# --- 5. INTEGRATION ---
ln -sf /var/opt/piavpn/bin/piactl /usr/local/bin/piactl
ln -sf /var/opt/piavpn/bin/pia-daemon /usr/local/bin/pia-daemon
ln -sf /var/opt/piavpn/bin/pia-client /usr/local/bin/pia-client

if [[ -f /etc/systemd/system/piavpn.service ]]; then
    sed -i -e 's|/opt/piavpn|/var/opt/piavpn|g' /etc/systemd/system/piavpn.service
fi

chown -R root:root "$PIA_VAR_DIR"
groupadd -r piavpn || true
chgrp -R "$GID_PIAVPN" "$PIA_VAR_DIR/etc" 2>/dev/null || :
chmod 750 "$PIA_VAR_DIR/etc"
chmod 755 "$PIA_VAR_DIR/bin/"*
setcap 'cap_net_bind_service=+ep' "$PIA_VAR_DIR/bin/pia-unbound" || true

# Cleanup and notify systemd
rm -f "$STAGING_TAR"
systemctl daemon-reload
systemctl restart piavpn.service --no-block || true

echo "✨ Update applied successfully."

