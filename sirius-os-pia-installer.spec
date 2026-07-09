# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.0.0
Release:        3%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS
License:        GPLv3
URL:            https://github.com/jonathonp3/sirius-os-pia-installer/
BuildArch:      noarch

# Core dependencies for the factory and deployment
Requires:       distrobox 
Requires:       podman
Requires:       curl
Requires:       tar

# PIA Binary dependencies
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
# In COPR SCM, files are already in the current directory. 
# We just create the build structure.
%setup -c -T

%build
# No build needed

%install
# 1. Create target directories
mkdir -p %{buildroot}%{_libexecdir}
mkdir -p %{buildroot}%{_unitdir}

# 2. Install the scripts from the SCM checkout
# In 'simple' method, files are in %{_builddir}/.. (one level up)
install -p -m 755 %{_builddir}/../piavpn-extract.sh %{buildroot}%{_libexecdir}/
install -p -m 755 %{_builddir}/../piavpn-deploy.sh %{buildroot}%{_libexecdir}/

# 3. Install the systemd units
install -p -m 644 %{_builddir}/../piavpn-extract.service %{buildroot}%{_unitdir}/
install -p -m 644 %{_builddir}/../piavpn-deploy.service %{buildroot}%{_unitdir}/

%files
%{_libexecdir}/piavpn-extract.sh
%{_libexecdir}/piavpn-deploy.sh
%{_unitdir}/piavpn-extract.service
%{_unitdir}/piavpn-deploy.service

%changelog
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-3
- Fix: Use relative builddir paths for SCM compatibility
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-2
- Fix: Corrected file paths for COPR SCM build environment
* Thu Jul 09 2026 Jonathon <jonathon@sirius-os> - 1.0.0-1
- Initial release

