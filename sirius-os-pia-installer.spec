# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.2.0
Release:        1%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# --- SOURCES ---
Source1:        piavpn-extract.sh
Source2:        piavpn-deploy.sh
Source3:        pia_service_removal.sh
Source4:        piavpn-extract.service
Source5:        piavpn-deploy.service
Source6:        sirius-os-pia.sysusers
Source7:        wolf-os-vpn.preset

# --- DEPENDENCIES ---
Requires:       distrobox, podman, curl, tar
Requires:       libnsl, libXaw, libutempter, libxcrypt-compat, libxkbcommon-x11, nss-tools, xterm, wget2

%description
Advanced background pipeline to build and deploy PIA VPN for Atomic desktops.
Includes an automated isolated factory and self-destructing cleanup logic.

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
install -p -m 755 %{SOURCE3} %{buildroot}/usr/libexec/pia_service_removal.sh

install -p -m 644 %{SOURCE4} %{buildroot}/usr/lib/systemd/system/piavpn-extract.service
install -p -m 644 %{SOURCE5} %{buildroot}/usr/lib/systemd/system/piavpn-deploy.service

install -p -m 644 %{SOURCE6} %{buildroot}/usr/lib/sysusers.d/sirius-os-pia.conf
install -p -m 644 %{SOURCE7} %{buildroot}/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%post
# Run the provisioner to set up the janitor in /etc
/usr/libexec/pia_service_removal.sh

%preun
if [ $1 -eq 0 ]; then
    echo "🚨 Sirius-OS: Uninstalling. Cleanup scheduled for next boot."
    mkdir -p /etc/piavpn-cleanup
    echo "true" > /etc/piavpn-cleanup/cleanup-needed
fi

%files
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/libexec/pia_service_removal.sh
/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service
/usr/lib/sysusers.d/sirius-os-pia.conf
/usr/lib/systemd/system-preset/50-wolf-os-vpn.preset

%changelog
* Sat Jul 11 2026 Jonathon <jonathon@sirius-os> - 1.2.0-1
- feat: Implemented 3-script architecture with pia_service_removal.sh
- feat: Added self-destructing cleaner for complete uninstall

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

