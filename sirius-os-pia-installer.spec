# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.0.0
Release:        10%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# --- SOURCES ---
Source1:        piavpn-extract.sh
Source2:        piavpn-deploy.sh
Source3:        piavpn-extract.service
Source4:        piavpn-deploy.service

# --- DEPENDENCIES ---
Requires:       distrobox, podman, curl, tar
Requires:       libnsl, libXaw, libutempter, libxcrypt-compat, libxkbcommon-x11
Requires:       mkfontscale, nss-tools, xterm, xorg-x11-fonts-misc, wget2

%description
Background pipeline to build and deploy PIA VPN for Atomic desktops.

%prep
%setup -c -T

%build
# No build needed

%install
# 1. Create target directories using explicit paths
mkdir -p %{buildroot}/usr/libexec
mkdir -p %{buildroot}/usr/lib/systemd/system

# 2. Install the scripts
install -p -m 755 %{SOURCE1} %{buildroot}/usr/libexec/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}/usr/libexec/piavpn-deploy.sh

# 3. Install the systemd units
install -p -m 644 %{SOURCE3} %{buildroot}/usr/lib/systemd/system/piavpn-extract.service
install -p -m 644 %{SOURCE4} %{buildroot}/usr/lib/systemd/system/piavpn-deploy.service

%files
# Use explicit paths to avoid macro expansion issues
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service

%changelog

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
