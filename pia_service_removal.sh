#!/bin/bash
# Sirius-OS: Provisioning the Dormant Janitor
set -euo pipefail

CLEANUP_DIR="/etc/piavpn-cleanup"
SERVICE_FILE="/etc/systemd/system/piavpn-uninstall-cleanup.service"

echo "⚙️  Provisioning dormant cleanup infrastructure..."

mkdir -p "$CLEANUP_DIR"

# 1. Create the ACTUAL cleanup task inside /etc
# This script will exist even after the RPM is deleted from /usr/
cat <<'EOF' > "$CLEANUP_DIR/cleanup-task.sh"
#!/bin/bash
echo "🧹 Janitor: Deep cleaning orphaned VPN data..."

# Stop service and unmount kernel locks
systemctl disable --now piavpn.service 2>/dev/null || :
umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :

# Remove binaries, configs, and symlinks
rm -rf /var/opt/piavpn
rm -f /etc/systemd/system/piavpn.service
rm -f /etc/NetworkManager/conf.d/wgpia.conf
rm -f /usr/local/share/applications/piavpn.desktop
rm -f /usr/local/share/pixmaps/piavpn.png
rm -f /usr/local/bin/piactl /usr/local/bin/pia-daemon /usr/local/bin/pia-client /usr/local/bin/pia-unbound
rm -f /opt/piavpn

# SELF-DESTRUCT: Remove the janitor's own footprints
rm -f /etc/systemd/system/piavpn-uninstall-cleanup.service
rm -rf /etc/piavpn-cleanup
systemctl daemon-reload

echo "✨ Janitor: System is now pristine."
EOF

chmod +x "$CLEANUP_DIR/cleanup-task.sh"

# 2. Create the Systemd service that watches for the marker
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sirius-OS PIA VPN Uninstall Cleanup
ConditionPathExists=$CLEANUP_DIR/cleanup-needed
DefaultDependencies=no
After=local-fs.target
Before=shutdown.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash $CLEANUP_DIR/cleanup-task.sh

[Install]
WantedBy=multi-user.target
EOF

# 3. Pre-enable the service so it is ready to trigger on the next boot
mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sf "$SERVICE_FILE" /etc/systemd/system/multi-user.target.wants/

