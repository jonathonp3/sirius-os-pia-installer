# Sirius-OS PIA Installer
Automated, container-based provisioning pipeline for Private Internet Access (PIA) on Fedora Atomic and Workstation, using a decoupled model for seamless persistent VPN management.

This repository contains RPM source and automation scripts to install the PIA VPN Linux client on **Sirius-OS** and **Wolf-OS**.

On Silverblue, Bazzite, and Aurora (atomic, immutable/read-only filesystems), the installer downloads the PIA Linux app using a decoupled two-stage systemd architecture.

## 🏗️ The Architecture

The manager implements a 2 stage model to bridge the gap between user-level container engine and root-level system deployment:

1. **Stage 1 (`piavpn-extract.service`)**: 
   - Runs as a standard user (UID 1000).
   - Scrapes the web for the latest PIA version.
   - Uses a temporary **Distrobox** factory to extract binaries.
   - Writes a staging archive to`/tmp`.

2. **Stage 2 (`piavpn-deploy.service`)**:
   - Runs as **Root**.
   - Monitors the staging archive.
   - Deploys binaries to persistent storage (`/var/opt/piavpn`).
   - Ensures the application runs properly on immutable OSTree systems.
   - Preserves credentials across updates. `/var/opt/piavpn/etc`.
   - Restarts the systemd VPN daemon.
   - Checks for updates at boot and skips installation when nothing new is available.
 
## OSTree behavior

    - Install/provision writes runtime state under `/var/opt/piavpn` and uses `/var` for persistence across deployments.
    - Uninstall cleanup is deferred to a boot-time systemd oneshot so it still runs correctly after `rpm-ostree remove` and reboot.

## 🚀 Key Features
    
    - OSTree-Friendly: Designed for persistent deployment state on immutable systems.
    - Idempotent: Checks for updates and skips work when nothing changed.
    - Credential-Safe: Preserves credentials/settings while updating binaries.
    - Universal: Adapts to Atomic and Workstation environments.

This project is built and hosted via [Fedora COPR](https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/). 

## 📜 License
This automation logic is licensed under GPL-3.0. The provisioned software (PIA) is subject to its own proprietary license and terms.

## How to install Sirius-OS PIA Installer

1. Install Repository:
```bash
sudo curl -Lo /etc/yum.repos.d/_copr_jonathonp3-sirius-os.repo https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/repo/fedora-44/jonathonp3-sirius-os-fedora-44.repo
```

2. Install Sirius-OS PIA Installer
```bash
rpm-ostree install sirius-os-pia-installer
```

3. Reboot
```bash
reboot
```

4. Log in to the admin account system (default group is 1000 on Fedora) and wait for the installation to complete. It usually takes a few minutes.


### How to remove PIA

1. 
```bash
rpm-ostree install sirius-os-pia-installer
```

2. Reboot into the new deployment
```bash
reboot
```


