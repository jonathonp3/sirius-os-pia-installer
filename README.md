# sirius-os-pia-manager
Automated, container-based provisioning pipeline for Private Internet Access (PIA) on Fedora Atomic and Workstation, using a decoupled model for seamless persistent VPN management.

# Sirius-OS PIA VPN Manager

This repository contains RPM source and automation scripts to install the PIA VPN client on **Sirius-OS** and **Wolf-OS**.

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
   - Applies the Atomic Bridge logic for UI compatibility.
   - Preserves credentials in `/var/opt/piavpn/etc`.
   - Restarts the systemd VPN daemon.
   - Checks for updates at boot and skips installation when nothing new is available.
   

## 🚀 Key Features

- **Atomic-Native**: Built for OSTree-based systems.
- **Idempotent**: Quick version checks with no boot-time impact when already up to date.
- **Self-Healing**: Repairs broken symlinks or missing binaries on reboot.
- **Credential-Safe**: Updates binaries without altering your login session or settings.
- **Universal**: Detects and adapts to both Atomic and Workstation environments.

## 📦 Building the RPM

This project is built and hosted via [Fedora COPR](https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/). 

To build manually:
1. Install rpkg.
2. Run rpkg srpm to generate the source package.
3. Build and deploy the resulting RPM to your image build or local machine.

## 📜 License
This automation logic is licensed under GPL-3.0. The provisioned software (PIA) is subject to its own proprietary license and terms.
