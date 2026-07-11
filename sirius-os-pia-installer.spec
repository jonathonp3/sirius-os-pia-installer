# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.1.1
Release:        1%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# --- SOURCES ---
Source1:        piavpn-extract.sh
Source2:        piavpn-deploy.sh
Source3:        piavpn-extract.service
Source4:        piavpn-deploy.service
Source5:        sirius-os-pia.sysusers
Source6:        wolf-os-vpn.preset

# --- DEPENDENCIES ---
Requires:       distrobox, podman, curl, tar
Requires:       libnsl, libXaw, libutempter, libxcrypt-compat, libxkbcommon-x11
Requires:       mkfontscale, nss-tools, xterm, xorg-x11-fonts-misc, wget2

%description
Background pipeline to build and deploy PIA VPN for Atomic desktops.
Includes sysusers.d for group management, systemd presets for 
automatic enablement, and full cleanup logic upon uninstallation.

%prep
%setup -c -T

%build
# No build needed

%install
# 1. Create target directories
mkdir -p %{buildroot}/usr/libexec
mkdir -p %{buildroot}/usr/lib/systemd/system
mkdir -p %{buildroot}/usr/lib/sysusers.d
mkdir -p %{buildroot}/usr/lib/systemd/system-preset

# 2. Install scripts
install -p -m 755 %{SOURCE1} %{buildroot}/usr/libexec/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}/usr/libexec/piavpn-deploy.sh

# 3. Install systemd units
install -p -m 644 %{SOURCE3} %{buildroot}/usr/lib/systemd/system/piavpn-extract.service
install -p -m 644 %{SOURCE4} %{buildroot}/usr/lib/systemd/system/piavpn-deploy.service

# 4. Install sysusers configuration
install -p -m 644 %{SOURCE5} %{buildroot}/usr/lib/sysusers.d/sirius-os-pia.conf

# 5. Install systemd preset
install -p -m 644 %{SOURCE6} %{buildroot}/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%preun
# $1 == 0 means uninstallation. We perform a surgical wipe of the VPN.
if [ $1 -eq 0 ]; then
    echo "🗑️ Sirius-OS: Completely removing PIA VPN binaries and configs..."

    # Stop and disable the VPN service
    systemctl disable --now piavpn.service 2>/dev/null || :
    
    # Unmount locked cgroup interfaces (Atomic Bridge safety)
    umount -l /opt/piavpn/etc/cgroup/net_cls 2>/dev/null || :
    
    # Remove system configurations
    rm -f /etc/systemd/system/piavpn.service
    rm -f /etc/NetworkManager/conf.d/wgpia.conf
    
    # Remove UI assets and refresh menu
    rm -f /usr/local/share/applications/piavpn.desktop
    rm -f /usr/local/share/pixmaps/piavpn.png
    if [ -x /usr/bin/update-desktop-database ]; then
        update-desktop-database /usr/local/share/applications 2>/dev/null || :
    fi
    
    # Remove host binary links
    rm -f /usr/local/bin/piactl
    rm -f /usr/local/bin/pia-daemon
    rm -f /usr/local/bin/pia-client
    rm -f /usr/local/bin/pia-unbound
    
    # Remove the legacy bridge link
    rm -f /opt/piavpn
    
    # Remove the persistent storage (Binaries and Credentials)
    rm -rf /var/opt/piavpn
    
    systemctl daemon-reload
    echo "✨ PIA VPN has been completely wiped from the system."
fi

%files
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service
/usr/lib/sysusers.d/sirius-os-pia.conf
/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%changelog
* Sat Jul 11 2026 Jonathon <jonathon@sirius-os> - 1.1.1-1
- feat: Added %%preun cleanup logic for total VPN removal
- feat: Added systemd preset for automatic enablement
- bump version to 1.1.1
* Fri Jul 10 2026 Jonathon <jonathon@sirius-os> - 1.1.0-1
- feat: implemented sysusers.d for native group creation during layering
- bump version to 1.1.0
* Fri Jul 10 2026 Jonathon <jonathon@sirius-os> - 1.0.0-10
- Fix: Added pia-ubound resolver to path, added group piahnsd
* Fri Jul 10 2026 Jonathon <jonathon@sirius-os> - 1.0.0-10
- Fix: Added pia-ubound resolver to path, added group piahnsd
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-9
- Fix: Removed leading slashes from tar extraction paths to match archive structure
- Fixed UI asset deployment for icons and desktop entries
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-8
- Fix: Use --strip-components=3 for accurate UI asset extraction
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-7
- Fix: Switched to explicit paths in %files to resolve macro expansion failure
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-6
- Fix: Add explicit leading slash to %{_unitdir}
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-5
- Fix: Explicitly define files as Sources to ensure bundling in SRPM
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-3
- Fix: Use relative builddir paths for SCM compatibility
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-2
- Fix: Corrected file paths for COPR SCM build environment
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-1
- Initial release

