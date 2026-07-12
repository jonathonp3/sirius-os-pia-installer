#!/bin/bash
# Sirius-OS: PIA Removal
set -euo pipefail

CLEANUP_DIR="/etc/piavpn-uninstall"
UNINSTALL_DIR="$CLEANUP_DIR"
SERVICE_FILE="/etc/systemd/system/piavpn-uninstall.service"
TASK_FILE="$UNINSTALL_DIR/pia-uninstaller.sh"
NEEDED_MARKER="$CLEANUP_DIR/uninstall-needed"

echo "⚙️  Provisioning dormant cleanup infrastructure..."

mkdir -p "$UNINSTALL_DIR"

# Create the actual uninstallation task
cat <<'EOF' > "$TASK_FILE"
#!/bin/bash
set -euo pipefail

echo "🧹 Removing VPN data..."

# 1. Kill surviving processes
pkill -9 pia-daemon || :
pkill -9 pia-client || :
pkill -9 pia-unbound || :

# 2. Force unmount kernel locks
umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :

# 3. Nuke binaries, storage, and configs
echo "🗑️  Removing persistent files..."
rm -rf /var/opt/piavpn
rm -f /etc/systemd/system/piavpn.service
rm -f /etc/NetworkManager/conf.d/wgpia.conf
rm -f /usr/local/share/applications/piavpn.desktop
rm -f /usr/local/share/pixmaps/piavpn.png
rm -f /usr/local/bin/piactl /usr/local/bin/pia-daemon /usr/local/bin/pia-client /usr/local/bin/pia-unbound
rm -rf /opt/piavpn

# 4. Remove the trigger marker
rm -f /etc/piavpn-uninstall/uninstall-needed

# 5. SELF-DESTRUCT: Remove systemd artifacts
echo "📂 Removing uninstall.service..."
rm -f /etc/systemd/system/multi-user.target.wants/piavpn-uninstall.service
# rm -f /etc/systemd/system/piavpn-uninstall.service
# rm -f /etc/piavpn-uninstall/pia-uninstaller.sh
rmdir /etc/piavpn-uninstall 2>/dev/null || :

systemctl daemon-reload
echo "✨ VPN has been removed."
EOF

chmod +x "$TASK_FILE"

# Create the systemd service (dormant; runs only if marker exists)
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sirius-OS PIA VPN Uninstall
ConditionPathExists=$NEEDED_MARKER
DefaultDependencies=no
After=local-fs.target
Before=multi-user.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/bin/bash $TASK_FILE

[Install]
WantedBy=multi-user.target
EOF

# Pre-enable the service
mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sf "$SERVICE_FILE" /etc/systemd/system/multi-user.target.wants/piavpn-uninstall.service

echo "✅ Uninstall task installed; waiting for trigger marker."
echo "To trigger uninstall, create: $NEEDED_MARKER"

