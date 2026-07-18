#!/bin/bash
# Sirius-OS: PIA Removal Provisioning
set -euo pipefail

SERVICE_FILE="/etc/systemd/system/piavpn-uninstall.service"
TASK_FILE="/etc/piavpn-uninstall/pia-uninstaller.sh"

if [ -e "$SERVICE_FILE" ] || [ -e "$TASK_FILE" ]; then
  echo "ℹ️  Uninstall provision already exists; skipping."
  exit 0
fi

CLEANUP_DIR="/etc/piavpn-uninstall"
UNINSTALL_DIR="$CLEANUP_DIR"

echo "⚙️  Provisioning dormant cleanup infrastructure..."

mkdir -p "$UNINSTALL_DIR"

cat <<'EOF' > "$TASK_FILE"
#!/bin/bash
set -euo pipefail

echo "🧹 Removing VPN data..."

pkill -9 pia-daemon || :
pkill -9 pia-client || :
pkill -9 pia-unbound || :

umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :

echo "🗑️  Removing persistent files..."
rm -rf /var/opt/piavpn
rm -f /etc/systemd/system/piavpn.service
rm -f /etc/NetworkManager/conf.d/wgpia.conf
rm -f /usr/local/share/applications/piavpn.desktop
rm -f /usr/local/share/pixmaps/piavpn.png
rm -f /usr/local/bin/piactl /usr/local/bin/pia-daemon /usr/local/bin/pia-client /usr/local/bin/pia-unbound
rm -rf /opt/piavpn

echo "📂 Removing uninstall.service..."
rm -f /etc/systemd/system/multi-user.target.wants/piavpn-uninstall.service
rm -f /etc/systemd/system/piavpn-uninstall.service
rm -f /etc/piavpn-uninstall/pia-uninstaller.sh
rmdir /etc/piavpn-uninstall 2>/dev/null || :

systemctl daemon-reload
echo "✨ VPN has been removed."
EOF

chmod +x "$TASK_FILE"

# Service triggers only when the marker exists
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sirius-OS PIA VPN Uninstall
# Only start this unit if the given path exists
ConditionPathExists=!/usr/libexec/piavpn-deploy.sh
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

mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sf "$SERVICE_FILE" /etc/systemd/system/multi-user.target.wants/piavpn-uninstall.service

echo "✅ Uninstall task installed"

