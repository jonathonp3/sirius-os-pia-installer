# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        1.2.0
Release:        12%{?dist}
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
Source6:        pia-uninstall-provision.service
Source7:        sirius-os-pia.sysusers

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
Requires:       systemd
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
mkdir -p %{buildroot}/usr/lib/systemd/system/multi-user.target.wants

# Install Scripts
install -p -m 755 %{SOURCE1} %{buildroot}/usr/libexec/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}/usr/libexec/piavpn-deploy.sh
install -p -m 755 %{SOURCE3} %{buildroot}/usr/libexec/pia-uninstall-provision.sh

# Install Services
install -p -m 644 %{SOURCE4} %{buildroot}/usr/lib/systemd/system/piavpn-extract.service
install -p -m 644 %{SOURCE5} %{buildroot}/usr/lib/systemd/system/piavpn-deploy.service
install -p -m 644 %{SOURCE6} %{buildroot}/usr/lib/systemd/system/pia-uninstall-provision.service

# Install Sysusers
install -p -m 644 %{SOURCE7} %{buildroot}/usr/lib/sysusers.d/sirius-os-pia.conf

# Enable Services via Symlinks (Atomic-friendly enablement)
ln -sf ../piavpn-deploy.service %{buildroot}/usr/lib/systemd/system/multi-user.target.wants/piavpn-deploy.service
ln -sf ../pia-uninstall-provision.service %{buildroot}/usr/lib/systemd/system/multi-user.target.wants/pia-uninstall-provision.service

%post
# No-op: Provisioning handled by systemd service on boot

%postun


%files
/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/libexec/pia-uninstall-provision.sh

/usr/lib/systemd/system/piavpn-extract.service
/usr/lib/systemd/system/piavpn-deploy.service
/usr/lib/systemd/system/pia-uninstall-provision.service

/usr/lib/systemd/system/multi-user.target.wants/piavpn-deploy.service
/usr/lib/systemd/system/multi-user.target.wants/pia-uninstall-provision.service

/usr/lib/sysusers.d/sirius-os-pia.conf

%changelog
* Sat Jul 18 2026 jonathon <jonathon@sirius-os> - 1.2.0-12
- Comment clean up pia-uninstall-provision

* Mon Jul 13 2026 jonathon <jonathon@sirius-os> - 1.2.0-11
- Fix: Trigger uninstall cleanup via systemd ConditionPathExists gate
- Fix: Ensure uninstall provision artifacts are created at runtime under /etc (deployment-persistent)
- Improvement: Use oneshot uninstall unit to remove PIA files and stop related services

* Mon Jul 13 2026 jonathon <jonathon@sirius-os> - 1.2.0-10
- Fix: Moved uninstall provisioning to a systemd service to bypass rpm-ostree sandbox
- Fix: Ensure uninstaller artifacts in /etc are created at runtime for persistence
- Improvement: Hard-enable provisioning service via /usr symlink

* Sun Jul 12 2026 jonathon <jonathon@sirius-os> - 1.2.0-7
- Fix: Resolve bwrap(sh) exit code 1 error during rpm-ostree install
- Fix: Remove broken %%systemd_post macros

