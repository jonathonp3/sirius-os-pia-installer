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

📦 Installation

1. On an Existing System (Sirius-OS, Silverblue, Bazzite)

If you are using a standard atomic desktop, add the repository manually and then layer the package:
bash

Add the Copr Repository
```bash
sudo curl -Lo /etc/yum.repos.d/_copr_jonathonp3-sirius-os.repo https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/repo/fedora-44/jonathonp3-sirius-os-fedora-44.repo
```
Install the Provisioner
```bash
rpm-ostree install sirius-os-pia-installer
```
Reboot to apply changes
```bash
systemctl reboot
```

Via BlueBuild / Custom Image (Bazzite, Aurora, etc.)

If you are building your own image via BlueBuild, add the repository to your recipe.yml or your config directory:

Repository URL:
```bash
https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/repo/fedora-44/jonathonp3-sirius-os-fedora-44.repo
```
Under the packages section in recipe.yml:
yaml
```bash
  - type: rpm-ostree
    install:
      - sirius-os-pia-installer
```

3. Post-Install Provisioning

After rebooting, log into your primary account (UID 1000). The background pipeline will automatically begin building the isolated VPN environment. 

    Wait for Completion: The process usually takes 2–5 minutes depending on your internet speed, as it needs to fetch the latest PIA binaries and configure the container factory.
    Monitor Progress (Optional): If you want to see exactly what the installer is doing, you can follow the logs in your terminal:
```bash
journalctl -u piavpn-extract.service -f
journalctl -u piavpn-deploy.service -f
```


## 🛡️ Uninstall (Atomic & Custom Image Support)

sirius-os-pia-installer is designed for the lifecycle of Atomic systems (Silverblue, Bazzite, Sirius-OS). If you stop using the package, it removes the installation in it's entirety.

- **Layered users:** If you `rpm-ostree remove sirius-os-pia-installer`, the uninstall runs on the next boot and purges installed files.
- **Custom image / BlueBuild users:** If you remove the package from the `recipe.yml` and rebuild/redeploy, the uninstall runs in the new deployment and purges the PIA installation.

