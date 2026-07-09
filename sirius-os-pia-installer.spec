# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.0.0
Release:        5%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# --- SOURCES ---
# We define each file so they are bundled into the SRPM
Source1:        piavpn-extract.sh
Source2:        piavpn-deploy.sh
Source3:        piavpn-extract.service
Source4:        piavpn-deploy.service

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
Background pipeline to build and deploy PIA VPN for Atomic desktops.

%prep
# Create the build directory
%setup -c -T

%build
# No build needed

%install
# 1. Create target directories
mkdir -p %{buildroot}%{_libexecdir}
mkdir -p %{buildroot}%{_unitdir}

# 2. Install the files using the Source macros
# This ensures we pull the files from the bundled 'SOURCES' directory
install -p -m 755 %{SOURCE1} %{buildroot}%{_libexecdir}/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}%{_libexecdir}/piavpn-deploy.sh
install -p -m 644 %{SOURCE3} %{buildroot}%{_unitdir}/piavpn-extract.service
install -p -m 644 %{SOURCE4} %{buildroot}%{_unitdir}/piavpn-deploy.service

%files
%{_libexecdir}/piavpn-extract.sh
%{_libexecdir}/piavpn-deploy.sh
%{_unitdir}/piavpn-extract.service
%{_unitdir}/piavpn-deploy.service

%changelog
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-5
- Fix: Explicitly define files as Sources to ensure bundling in SRPM
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-4
- Fix: Use %{_sourcedir} for reliable file pathing in COPR SCM
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-3
- Fix: Use relative builddir paths for SCM compatibility
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-2
- Fix: Corrected file paths for COPR SCM build environment
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-1
- Initial release
