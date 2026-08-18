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

TARGET_USER=$(id -nu 1000 || echo "jonathon")

echo "🧹 Removing VPN data..."
# 1. Stop and Disable units (User and System)
systemctl disable --now piavpn.service || :
systemctl disable --now piavpn-deploy.path || :
systemctl --user -M "${TARGET_USER}@" disable --now piavpn-extract.timer || :

# 2. Kill processes
pkill -9 pia-daemon || :
pkill -9 pia-client || :
pkill -9 pia-unbound || :

# 3. Manual Firewall Flush
echo "🔥 Clearing VPN Kill-Switch rules..."
nft flush ruleset || :
systemctl restart firewalld || :

umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :

echo "🗑️  Removing persistent files and binaries..."
rm -rf /var/opt/piavpn
rm -rf /opt/piavpn
rm -f /etc/NetworkManager/conf.d/wgpia.conf
rm -f /usr/local/share/applications/piavpn.desktop
rm -f /usr/local/share/pixmaps/piavpn.png
rm -f /usr/local/bin/piactl /usr/local/bin/pia-daemon /usr/local/bin/pia-client /usr/local/bin/pia-unbound

echo "📂 Cleaning /etc from Provisioned Units..."
# Remove System Units
rm -f /etc/systemd/system/piavpn-deploy.service
rm -f /etc/systemd/system/piavpn-deploy.path
rm -f /etc/systemd/system/piavpn-provision.service

# Remove User Units
rm -f /etc/systemd/user/piavpn-extract.service
rm -f /etc/systemd/user/piavpn-extract.timer

# Remove Provisioning Marker
rm -f /etc/wolf-os/pia-provisioned
rmdir /etc/wolf-os 2>/dev/null || :

echo "📂 Removing uninstaller infrastructure..."
rm -f /etc/systemd/system/multi-user.target.wants/piavpn-uninstall.service
rm -f /etc/systemd/system/piavpn-uninstall.service
rm -f /etc/piavpn-uninstall/pia-uninstaller.sh
rmdir /etc/piavpn-uninstall 2>/dev/null || :

systemctl daemon-reload
echo "✨ VPN has been completely removed from Wolf-OS."
EOF

chmod +x "$TASK_FILE"

# Service triggers only when the master deploy script is gone (RPM uninstalled)
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sirius-OS PIA VPN Uninstall
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

