# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.1.1
Release:        2%{?dist}
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
if [ $1 -eq 0 ]; then
    echo "📝 Sirius-OS: Scheduling persistent data cleanup..."
    mkdir -p /etc/tmpfiles.d/
    cat <<EOF > /etc/tmpfiles.d/piavpn-cleanup.conf
# Sirius-OS VPN Cleanup
# This file will delete itself after running once.

# 1. Recursive removal of the binaries and credentials
R! /var/opt/piavpn                                -    -    -    -    -

# 2. Individual file removals
r! /etc/systemd/system/piavpn.service             -    -    -    -    -
r! /etc/NetworkManager/conf.d/wgpia.conf          -    -    -    -    -
r! /usr/local/share/applications/piavpn.desktop   -    -    -    -    -
r! /usr/local/share/pixmaps/piavpn.png            -    -    -    -    -
r! /usr/local/bin/piactl                          -    -    -    -    -
r! /usr/local/bin/pia-daemon                      -    -    -    -    -
r! /usr/local/bin/pia-client                      -    -    -    -    -
r! /usr/local/bin/pia-unbound                     -    -    -    -    -
r! /opt/piavpn                                    -    -    -    -    -

# 3. SELF-DESTRUCT: Remove this very file at the end of the process
r /etc/tmpfiles.d/piavpn-cleanup.conf             -    -    -    -    -
EOF
fi

%files
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service
/usr/lib/sysusers.d/sirius-os-pia.conf
/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%changelog
* Sat Jul 11 2026 Jonathon <jonathon@sirius-os> - 1.1.1-2
- feat: implemented self-destructing tmpfiles.d cleanup in %%preun
- Solves "ghost binaries" issue where persistent data remained after Atomic uninstall
- Adds one-time boot logic to wipe /var/opt/piavpn and system-wide symlinks
- Ensures complete system removal of pia after uninstall
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

