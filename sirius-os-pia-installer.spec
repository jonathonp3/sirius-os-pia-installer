# Disable debug packages
%define debug_package %{nil}

Name:           sirius-os-pia-installer
Version:        2.0.0
Release:        5%{?dist}
Summary:        Automated PIA VPN provisioner for Sirius-OS (Provisioning Model)
License:        GPL-3.0-only
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
Source8:        piavpn-extract.timer
Source9:        piavpn-deploy.path
Source10:       piavpn-provision.sh
Source11:       piavpn-provision.service
Source12:       README.md

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
Background pipeline to automate the deployment of PIA VPN on Fedora
Atomic desktops. Designed to overcome rpm-ostree limitations using an
innovative two-stage relay and provisioning model.

Note: This package contains ONLY provisioning/automation scripts. It
does NOT include any Private Internet Access (PIA) source code. The PIA
app is fetched directly from the official PIA website during the
extraction process

%prep
%setup -c -T

%install
mkdir -p %{buildroot}/usr/libexec
mkdir -p %{buildroot}/usr/lib/systemd/system
mkdir -p %{buildroot}/usr/lib/sysusers.d
mkdir -p %{buildroot}/usr/share/sirius-os/pia
mkdir -p %{buildroot}/usr/lib/systemd/system/multi-user.target.wants

# 1. Install Executable Scripts to libexec
install -p -m 755 %{SOURCE1} %{buildroot}/usr/libexec/piavpn-extract.sh
install -p -m 755 %{SOURCE2} %{buildroot}/usr/libexec/piavpn-deploy.sh
install -p -m 755 %{SOURCE3} %{buildroot}/usr/libexec/pia-uninstall-provision.sh
install -p -m 755 %{SOURCE10} %{buildroot}/usr/libexec/piavpn-provision.sh

# 2. Install Service Blueprints to /usr/share (Immutable Templates)
install -p -m 644 %{SOURCE4} %{buildroot}/usr/share/sirius-os/pia/piavpn-extract.service
install -p -m 644 %{SOURCE8} %{buildroot}/usr/share/sirius-os/pia/piavpn-extract.timer
install -p -m 644 %{SOURCE5} %{buildroot}/usr/share/sirius-os/pia/piavpn-deploy.service
install -p -m 644 %{SOURCE9} %{buildroot}/usr/share/sirius-os/pia/piavpn-deploy.path

# 3. Install the Provisioner & Uninstaller Infrastructure
install -p -m 644 %{SOURCE11} %{buildroot}/usr/lib/systemd/system/piavpn-provision.service
install -p -m 644 %{SOURCE6} %{buildroot}/usr/lib/systemd/system/pia-uninstall-provision.service

# 4. Install Sysusers
install -p -m 644 %{SOURCE7} %{buildroot}/usr/lib/sysusers.d/sirius-os-pia.conf

# 5. Enable Provisioners via Symlinks (Hard-enable in Vendor Layer)
ln -sf ../piavpn-provision.service %{buildroot}/usr/lib/systemd/system/multi-user.target.wants/piavpn-provision.service
ln -sf ../pia-uninstall-provision.service %{buildroot}/usr/lib/systemd/system/multi-user.target.wants/pia-uninstall-provision.service

# 6. Install README
install -Dpm 0644 %{SOURCE12} %{buildroot}%{_docdir}/%{name}/README.md

%files
%doc %{_docdir}/%{name}/README.md

/usr/libexec/piavpn-extract.sh
/usr/libexec/piavpn-deploy.sh
/usr/libexec/pia-uninstall-provision.sh
/usr/libexec/piavpn-provision.sh

/usr/share/sirius-os/pia/piavpn-extract.service
/usr/share/sirius-os/pia/piavpn-extract.timer
/usr/share/sirius-os/pia/piavpn-deploy.service
/usr/share/sirius-os/pia/piavpn-deploy.path

/usr/lib/systemd/system/piavpn-provision.service
/usr/lib/systemd/system/pia-uninstall-provision.service
/usr/lib/systemd/system/multi-user.target.wants/piavpn-provision.service
/usr/lib/systemd/system/multi-user.target.wants/pia-uninstall-provision.service

/usr/lib/sysusers.d/sirius-os-pia.conf

* Mon Sep 28 2026  Jonathon P <jonathon@sirius-os> - 2.0.0-5
- Fixed extraction failing on BlueBuild/Bazzite first boot. Two
  problems stacked:
  1. piavpn-extract.service's After=network-online.target was not
     a reliable guarantee that the network was usable on an initial
     rebase to Bazzite. NetworkManager reported the network "up"
     before DHCP had completed and DNS was resolving. curl to the
     PIA download URL failed, and set -e killed the extraction.
  2. Bazzite's first-boot sequence tears down or restarts the UID
     1000 user manager after multi-user.target completes. The
     root provisioner's --no-block start of piavpn-extract.service
     returned success while the job died silently, and the
     ConditionPathExists gate meant it never re-armed on the
     following boot.
- The user timer now owns the first run and fires at 1 minute 30
  seconds after boot. That is past Bazzite's measured ~52s
  first-boot teardown, with margin, and long enough for
  NetworkManager, DHCP, and DNS to be genuinely ready. The delay
  is only paid on first install; post-stamp boots exit before the
  network.
- piavpn-provision.sh: removed the /usr/libexec/piavpn-deploy.sh
  kickstart from the tail. The user timer and the path unit now
  own the trigger chain.
- piavpn-extract.sh: added a flock guard on
  /run/user/$UID/cache/pia-vpn/.extract.lock so the timer and a
  manual systemctl --user start cannot race.
- piavpn-extract.sh: added a check stamp at
  ~/.local/state/sirius-os/pia/.last-check with a 7-day interval.
  A successful check writes the stamp; subsequent boots within 7
  days exit immediately without a network round trip. The stamp is
  only written on success, so a machine that was offline during
  its first-install window retries on the next boot with no user
  intervention.
- piavpn-extract.sh: curl now uses -sfL --max-time 30, and both
  pipelines end in '|| true', so an offline boot reaches the
  offline branch instead of dying on pipefail. When offline and
  PIA is already installed, the script exits 0 without writing
  the stamp. When offline and PIA is not installed, it exits 1
  (the genuine first-install failure case).
- pia-uninstall-provision.sh: remove ~/.local/state/sirius-os/pia/
  on uninstall so a reinstall starts with a clean check window.
  Without this, a stale stamp survives the uninstall and the next
  install's extract script skips its first check, leaving PIA
  uninstalled until the stamp expires.
- Documentation: added docs/TESTING.md, docs/PIA VPN Functional
  Testing Guide.md, and docs/Full Lifecycle Timeline.md.
  Restructured README.md around operational use (monitoring,
  health checks, failure playbook, timing reference).

* Tue Sep 22 2026  Jonathon P <jonathon@sirius-os> - 2.0.0-4
- Removed `nft flush ruleset` and the associated `firewall-cmd --reload`
  from the dormant uninstaller. Testing showed that PIA's kill-switch
  rules are in-memory only and are cleared by the daemon when it shuts
  down. The cleanup task already stops the daemon with
  `systemctl disable --now piavpn.service`, so the rules are gone
  before any nft command would run. The flush was clearing an empty
  ruleset while wiping firewalld's and libvirt's rules as a side
  effect, which broke the virbr0 bridge binding and left VMs without
  DHCP.

* Mon Sep 21 2026 Jonathon P <jonathon@sirius-os> - 2.0.0-3
- Added ConditionPathExists to piavpn-deploy.service so it is skipped
  instead of failing on the boot after package removal. Without it,
  systemd queued the unit before the dormant uninstaller removed the
  symlink, and the start attempt failed with "not-found".
- Removed the enablement symlinks during cleanup:
  /etc/systemd/system/multi-user.target.wants/piavpn-deploy.path,
  /etc/systemd/system/multi-user.target.wants/piavpn-deploy.service,
  and the user timer symlink in
  ~/.config/systemd/user/timers.target.wants/piavpn-extract.timer.
  Without this, dangling symlinks persisted after removal and
  appeared in systemctl --failed.

* Sun Sep 20 2026 Jonathon P <jonathon@sirius-os> - 2.0.0-2
- Atomic handoff for unit files: write to .tmp then mv -f, so systemd
  never sees a partial file during enable.
- Removed redundant systemctl --user disable call from the dormant
  uninstaller. The call produced a harmless "Transport endpoint is
  not connected" error in the journal during cleanup.
- License changed from GPLv3 to GPL-3.0-only (valid SPDX identifier).
- Ship README.md as %doc.

* Sat Aug 15 2026 jonathon <jonathon@sirius-os> - 2.0.0-1
- MAJOR RELEASE: Transitioned to an innovative "Atomic-Native" Relay Architecture.
- Compliance & Transparency:
    - Repository contains only provisioning scripts; proprietary code is fetched directly from upstream.
- Designed to solve rpm-ostree limitations:
    - Bypasses the lack of traditional %post scripts by using specialized provisioning services.
    - Implemented a "Relay" model to handle precise installation and uninstallation.
- Feature: Blueprint Provisioning Model:
    - Unit templates are stored in /usr/share/sirius-os and deployed to /etc at runtime.
    - Ensures full user transparency and persistent, auditable control over system services.
- Optimization: Secure User-to-Root Handoff:
    - Added piavpn-deploy.path for a zero-sudo link between User extraction and Root deployment.
    - Staging area migrated to UID-scoped RAM cache (/run/user/1000/cache).
- Enhanced Extraction & Maintenance:
    - User-level engine includes "Phase-based" logging and robust cleanup traps.
    - Migrated to a low-impact Monthly Timer to minimize background resource usage.
- System Hygiene:
    - Thoroughly tested uninstaller logic now includes a mandatory nftables flush.

