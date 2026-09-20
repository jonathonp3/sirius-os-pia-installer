#!/bin/bash
set -euo pipefail

TARGET_USER=$(id -nu 1000 || echo "jonathon")
USER_ID=$(id -u "$TARGET_USER" || echo "1000")

echo "🔧 Sirius-OS: Provisioning PIA VPN infrastructure..."

# --- STEP 1: COPY ALL FILES IMMEDIATELY ---

# Atomic handoff: write to .tmp, then rename. cp truncates the
# destination before writing, and systemd can scan the directory
# during the write, seeing a partial file and failing enable with
# "Unit does not exist." The race was observed on Workstation but
# not on silverblue

echo "📦 Deploying unit blueprints to /etc..."
mkdir -p /etc/systemd/system/
mkdir -p /etc/systemd/user/

cp /usr/share/sirius-os/pia/piavpn-deploy.service /etc/systemd/system/.piavpn-deploy.service.tmp
mv -f /etc/systemd/system/.piavpn-deploy.service.tmp /etc/systemd/system/piavpn-deploy.service

cp /usr/share/sirius-os/pia/piavpn-deploy.path /etc/systemd/system/.piavpn-deploy.path.tmp
mv -f /etc/systemd/system/.piavpn-deploy.path.tmp /etc/systemd/system/piavpn-deploy.path

cp /usr/share/sirius-os/pia/piavpn-extract.service /etc/systemd/user/.piavpn-extract.service.tmp
mv -f /etc/systemd/user/.piavpn-extract.service.tmp /etc/systemd/user/piavpn-extract.service

cp /usr/share/sirius-os/pia/piavpn-extract.timer /etc/systemd/user/.piavpn-extract.timer.tmp
mv -f /etc/systemd/user/.piavpn-extract.timer.tmp /etc/systemd/user/piavpn-extract.timer

# --- STEP 2: ENABLE LINGER ---
mkdir -p /var/lib/systemd/linger
touch "/var/lib/systemd/linger/$TARGET_USER"

# --- STEP 3: WAIT FOR USER MANAGER ---
echo "⏳ Waiting for $TARGET_USER's user manager..."
for i in {1..15}; do
    if [ -S "/run/user/$USER_ID/systemd/private" ]; then
        echo "✅ User manager is ready."
        break
    fi
    [[ $i -eq 15 ]] && echo "❌ Timeout waiting for user manager." && exit 1
    sleep 1
done

# --- STEP 4: ARM THE SYSTEM ---
systemctl daemon-reload
systemctl enable --now piavpn-deploy.path
systemctl enable piavpn-deploy.service

systemctl --user -M "${TARGET_USER}@" daemon-reload
systemctl --user -M "${TARGET_USER}@" enable --now piavpn-extract.timer

# --- STEP 5: FINALIZE ---
mkdir -p /etc/sirius-os
touch /etc/sirius-os/pia-provisioned
echo "✅ Sirius-OS: PIA VPN provisioning complete!"

# --- STEP 6: KICKSTART ---
# This manual call is now safe because all units are already on disk
/usr/libexec/piavpn-deploy.sh

