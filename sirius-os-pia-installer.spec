# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.2.0
Release:        2%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# --- SOURCES ---
Source1:        piavpn-extract.sh
Source2:        piavpn-deploy.sh
Source3:        pia-uninstall-provision.sh
Source4:        piavpn-extract.service
Source5:        piavpn-deploy.service
Source6:        sirius-os-pia.sysusers
Source7:        wolf-os-vpn.preset

# --- DEPENDENCIES ---
Requires:       distrobox
Requires:       podman
Requires:       curl
Requires:       tar
Requires:       libnsl
Requires:       libXaw
Requires:       libutempter
Requires:       libxcrypt-compat
Requires:       libxkbcommon-x11
Requires:       mkfontscale
Requires:       nss-tools
Requires:       xterm
Requires:       xorg-x11-fonts-misc
Requires:       wget2

%description
Advanced background pipeline to build and deploy PIA VPN for Atomic desktops.
Includes an automated isolated factory and one-time uninstall cleanup logic.

%prep
%setup -c -T

%build
# No build needed

%install
mkdir -p %{buildroot}/usr/libexec
mkdir -p %{buildroot}/usr/lib/systemd/system
mkdir -p %{buildroot}/usr/lib/sysusers.d
mkdir -p %{buildroot}/usr/lib/systemd/system-preset

install -p -m 755 %{SOURCE1} %{buildroot}/usr/libexec/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}/usr/libexec/piavpn-deploy.sh
install -p -m 755 %{SOURCE3} %{buildroot}/usr/libexec/pia-uninstall-provision.sh

install -p -m 644 %{SOURCE4} %{buildroot}/usr/lib/systemd/system/piavpn-extract.service
install -p -m 644 %{SOURCE5} %{buildroot}/usr/lib/systemd/system/piavpn-deploy.service

install -p -m 644 %{SOURCE6} %{buildroot}/usr/lib/sysusers.d/sirius-os-pia.conf
install -p -m 644 %{SOURCE7} %{buildroot}/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%post
/usr/libexec/pia-uninstall-provision.sh >/dev/null 2>&1 || :

%postun
if [ $1 -eq 0 ]; then
    echo "🚨 Sirius-OS: Uninstalling. Scheduling uninstall marker for next boot."
    mkdir -p /etc/piavpn-uninstall
    echo "true" > /etc/piavpn-uninstall/uninstall-needed
    systemctl daemon-reload >/dev/null 2>&1 || :
fi

%files
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/libexec/pia-uninstall-provision.sh

/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service

/usr/lib/sysusers.d/sirius-os-pia.conf
/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%changelog
* Sun Jul 12 2026 jonathon <jonathon@sitius- 1.2.0-2
- Fix added back missing despondencies 

* Sun Jul 12 2026 jonathon <jonathon@sitius- 1.2.0-1
- Fix uninstall flow on rpm-ostree by provisioning a dormant systemd service gated by /etc/piavpn-uninstall/uninstall-needed marker created in %postun.

