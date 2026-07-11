#!/bin/bash
# Sirius-OS: Janitor Provisioning Logic
set -euo pipefail

CLEANUP_DIR="/etc/piavpn-cleanup"
SERVICE_FILE="/etc/systemd/system/piavpn-uninstall-cleanup.service"

mkdir -p "$CLEANUP_DIR"

# Create the ACTUAL aggressive cleanup task
cat <<'EOF' > "$CLEANUP_DIR/cleanup-task.sh"
#!/bin/bash
echo "🧹 Janitor: Commencing deep clean of PIA VPN..."

# 1. Kill any surviving processes
/usr/bin/pkill -9 pia-daemon || :
/usr/bin/pkill -9 pia-client || :

# 2. Force unmount kernel locks
/usr/bin/umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :

# 3. Clean everything
/usr/bin/rm -rf /var/opt/piavpn
/usr/bin/rm -f /etc/systemd/system/piavpn.service
/usr/bin/rm -f /etc/NetworkManager/conf.d/wgpia.conf
/usr/bin/rm -f /usr/local/share/applications/piavpn.desktop
/usr/bin/rm -f /usr/local/share/pixmaps/piavpn.png
/usr/bin/rm -f /usr/local/bin/piactl /usr/local/bin/pia-daemon /usr/local/bin/pia-client /usr/local/bin/pia-unbound
/usr/bin/rm -f /opt/piavpn

# 4. SELF-DESTRUCT
/usr/bin/rm -f /etc/systemd/system/multi-user.target.wants/piavpn-uninstall-cleanup.service
/usr/bin/rm -f /etc/systemd/system/piavpn-uninstall-cleanup.service
/usr/bin/rm -rf /etc/piavpn-cleanup

/usr/bin/systemctl daemon-reload
echo "✨ Janitor: System is clean. Task complete."
EOF

chmod +x "$CLEANUP_DIR/cleanup-task.sh"

# Create the Systemd service that watches for the marker
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sirius-OS PIA VPN Uninstall Cleanup
ConditionPathExists=$CLEANUP_DIR/cleanup-needed
DefaultDependencies=no
After=local-fs.target
Before=multi-user.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/bin/bash $CLEANUP_DIR/cleanup-task.sh

[Install]
WantedBy=multi-user.target
EOF

# Pre-enable the service
mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sf "$SERVICE_FILE" /etc/systemd/system/multi-user.target.wants/

