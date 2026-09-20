#!/bin/bash
set -euo pipefail

# --- CONFIGURATION ---
STAGING_TAR="/run/user/1000/cache/pia-vpn/pia-stage.tar.gz"
PIA_VAR_DIR="/var/opt/piavpn"
GID_PIAVPN=955

# Detect the primary user (UID 1000)
TARGET_USER=$(id -nu 1000)
if [ -z "$TARGET_USER" ]; then
    echo "❌ Error: Could not detect primary user (UID 1000)."
    exit 1
fi

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
if [ "$is_atomic" -eq 0 ]; then
    if [ ! -L "/opt/piavpn" ]; then
        echo "🔗 Workstation: Correcting /opt/piavpn bridge..."
        umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || true
        rm -rf /opt/piavpn
        ln -sf "$PIA_VAR_DIR" /opt/piavpn
        echo "✅ Bridge created: /opt/piavpn -> $PIA_VAR_DIR"
    fi
fi

# --- 3. CHECK FOR NEW UPDATE OR FIRST INSTALL ---
if [[ ! -f "$STAGING_TAR" ]]; then
    if [[ ! -d "$PIA_VAR_DIR/bin" ]]; then
        echo "🆕 First Boot detected (PIA missing). Triggering user-level extraction for $TARGET_USER..."
        
        # --- THE FIX: Wait for the user manager socket ---
        USER_ID=$(id -u "$TARGET_USER")
        for i in {1..15}; do
            if [ -S "/run/user/$USER_ID/systemd/private" ]; then
                break
            fi
            sleep 1
        done
        # -------------------------------------------------

        systemctl --user -M "${TARGET_USER}@" enable --now piavpn-extract.timer 2>/dev/null || :
        systemctl --user -M "${TARGET_USER}@" start piavpn-extract.service --no-block || :
        
        echo "⏳ Initial extraction started. VPN will appear shortly."
    else
        echo "✅ No new update package found. Paths are verified. Exiting."
    fi
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
echo "📦 Extracting system configurations..."
tar -xpzf "$STAGING_TAR" -C / --no-same-owner --wildcards 'etc/*' || true

echo "🎨 Integrating UI assets (Icon & Menu Entry)..."
tar -xpzf "$STAGING_TAR" --strip-components=3 -C /usr/local/share/applications usr/share/applications/piavpn.desktop || true
tar -xpzf "$STAGING_TAR" --strip-components=3 -C /usr/local/share/pixmaps usr/share/pixmaps/piavpn.png || true

echo "📦 Extracting binaries..."
tar -xpzf "$STAGING_TAR" -C "$PIA_VAR_DIR" --no-same-owner --strip-components=2 \
    --exclude='opt/piavpn/etc' \
    opt/piavpn || true

if [ ! -d "$PIA_VAR_DIR/etc" ]; then
    mkdir -p "$PIA_VAR_DIR/etc"
fi

# --- 6. INTEGRATION ---
echo "🔧 Configuring system integration..."

# Re-link binaries
ln -sf /var/opt/piavpn/bin/piactl /usr/local/bin/piactl
ln -sf /var/opt/piavpn/bin/pia-daemon /usr/local/bin/pia-daemon
ln -sf /var/opt/piavpn/bin/pia-client /usr/local/bin/pia-client
ln -sf /var/opt/piavpn/bin/pia-unbound /usr/local/bin/pia-unbound

# Patch paths for Atomic compatibility
# BUG FIX: Look for '=/opt' or ' /opt' to prevent /var/var/var/ path doubling.
if [[ -f /etc/systemd/system/piavpn.service ]]; then
    sed -i -e 's|=\/opt/piavpn|=/var/opt/piavpn|g' /etc/systemd/system/piavpn.service
fi

if [[ -f /usr/local/share/applications/piavpn.desktop ]]; then
    sed -i -e 's|=\/opt/piavpn|=/var/opt/piavpn|g' /usr/local/share/applications/piavpn.desktop
    sed -i -e 's| \/opt/piavpn| /var/opt/piavpn|g' /usr/local/share/applications/piavpn.desktop
fi

# Refresh the menu database
update-desktop-database /usr/local/share/applications || true

# --- SET OWNERSHIP & PERMISSIONS (MATCH WORKSTATION) ---
echo "🔐 Setting permissions to match workstation..."

# Set ownership
chown -R root:root "$PIA_VAR_DIR"
chgrp -R "$GID_PIAVPN" "$PIA_VAR_DIR/etc" 2>/dev/null || :

# Set directory permissions (755 for all directories)
chmod 755 "$PIA_VAR_DIR"
chmod 755 "$PIA_VAR_DIR/bin"
chmod 755 "$PIA_VAR_DIR/lib"
chmod 755 "$PIA_VAR_DIR/plugins"
chmod 755 "$PIA_VAR_DIR/qml"
chmod 755 "$PIA_VAR_DIR/share"
chmod 755 "$PIA_VAR_DIR/var"
chmod 755 "$PIA_VAR_DIR/etc"
chmod 755 "$PIA_VAR_DIR/etc/cgroup" 2>/dev/null || true

# Set binary permissions (755 for all binaries)
chmod 755 "$PIA_VAR_DIR/bin/"*

# Special SUID bit for support-tool-launcher (matches workstation)
# Allows support-tool to run with elevated privileges when needed
chmod 4750 "$PIA_VAR_DIR/bin/support-tool-launcher" 2>/dev/null || true

# Set JSON file permissions (match workstation exactly)
# account.json: 600 (rw-------) - private credentials
chmod 600 "$PIA_VAR_DIR/etc/account.json" 2>/dev/null || true
# data.json: 644 (rw-r--r--) - readable by all
chmod 644 "$PIA_VAR_DIR/etc/data.json" 2>/dev/null || true
# settings.json: 644 (rw-r--r--) - readable by all
chmod 644 "$PIA_VAR_DIR/etc/settings.json" 2>/dev/null || true

# --- NETWORKING PERMISSIONS (SECURITY BEST PRACTICE) ---
# Allow binding to privileged ports (ports below 1024)
# Required for pia-unbound DNS resolver to bind to port 53
setcap 'cap_net_bind_service=+ep' "$PIA_VAR_DIR/bin/pia-unbound" || true

# Give specific privileges without running as root
# - cap_net_admin: Configure network interfaces and routing
# - cap_net_raw: Create raw sockets (WireGuard protocol)
# - cap_sys_admin: Mount cgroups, configure network namespaces
# Follows the principle of least privilege
setcap 'cap_net_admin,cap_net_raw,cap_sys_admin+ep' "$PIA_VAR_DIR/bin/pia-daemon" || true

# --- 7. CLEANUP & ACTIVATE ---
echo "🧹 Cleaning up staging area..."
rm -f "$STAGING_TAR"
# Also remove the .tmp file if it was left behind by a crash
rm -f "${STAGING_TAR}.tmp"

systemctl daemon-reload
systemctl restart piavpn.service --no-block || true



# Nudge GNOME to show the new icon immediately
touch /usr/local/share/applications



echo "✨ Update applied successfully."

