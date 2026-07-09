Name:           sirius-os-pia-installer
Version:        1.0.0
Release:        1%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# Core dependencies for the factory and deployment
Requires:       distrobox 
Requires:       podman
Requires:       curl
Requires:       tar

# PIA Binary dependencies (Ensures they are present on the host)
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
Automates provisioning from user-level containers to root-level persistent storage.

%prep
# No prep needed for plain script packaging

%build
# No build needed for scripts

%install
# 1. Create target directories in the build root
mkdir -p %{buildroot}%{_libexecdir}
mkdir -p %{buildroot}%{_unitdir}

# 2. Install the scripts
# We use '.' (current directory) because SCM builds put files in the build root
install -p -m 755 piavpn-extract.sh %{buildroot}%{_libexecdir}/
install -p -m 755 piavpn-deploy.sh %{buildroot}%{_libexecdir}/

# 3. Install the systemd units
install -p -m 644 piavpn-extract.service %{buildroot}%{_unitdir}/
install -p -m 644 piavpn-deploy.service %{buildroot}%{_unitdir}/

%files
# The binaries/scripts
%{_libexecdir}/piavpn-extract.sh
%{_libexecdir}/piavpn-deploy.sh
# The services
%{_unitdir}/piavpn-extract.service
%{_unitdir}/piavpn-deploy.service

%changelog
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-1
- Initial release of the Sirius-OS PIA VPN Provisioning pipeline
- Implemented decoupled Producer-Consumer architecture
- Added support for persistent /var/opt storage and UI integration

