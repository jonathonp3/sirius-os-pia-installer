Sirius-OS PIA Installer (v2.0.0)
🏗️ The Architecture

The Sirius-OS PIA Installer implements an innovative "Relay" model designed specifically for the unique constraints of Fedora Atomic desktops (Silverblue, Bazzite). Because traditional RPM %post scripts are restricted in these environments, this project uses a decoupled, multi-stage pipeline to manage the application lifecycle precisely.

    [!IMPORTANT]
    Project Transparency & Compliance
    This repository contains provisioning and automation scripts only. It does not include any Private Internet Access (PIA) source code or proprietary binaries. The PIA Linux application is fetched directly from the official PIA website during the extraction phase and is then prepared to run natively on Atomic environments.

Stage 1: The Extraction (User-Level)

    Unit: piavpn-extract.service (Triggered by piavpn-extract.timer)
    Context: Runs in the user session (UID 1000).
    Action: Scrapes the official PIA web portal for the latest release and builds the binaries inside a temporary, isolated Distrobox factory.
    Output: Writes a staging archive to a private, RAM-based cache: /run/user/1000/cache/pia-vpn/.
    Efficiency: Includes a Fast-Exit idempotency check to skip the container build if the local version is already up-to-date.

Stage 2: The Deployment (Root-Level)

    Unit: piavpn-deploy.service (Triggered by piavpn-deploy.path)
    Context: Runs with System/Root privileges.
    Action: Monitors the staging cache. As soon as Stage 1 delivers a new archive, Root wakes up to:
        Deploy binaries to persistent storage (/var/opt/piavpn).
        Patch and integrate systemd units and UI assets.
        Preserve credentials and configurations across OS upgrades and rebases.

🛡️ Key Innovations & Design Goals
Secure Zero-Sudo Handoff

To maintain a high security posture, Stage 2 is activated via a Systemd Path Unit. This enables a controlled, event-driven link between User-level extraction and Root-level deployment. This architecture ensures the extraction logic never requires broad sudo privileges.
The Blueprint Provisioning Model

Unlike standard packages that "hide" units inside the read-only vendor layer (/usr/lib), Wolf-OS uses a transparent provisioning workflow:

    Blueprints: Service templates are stored in /usr/share/wolf-os.
    Deployment: Units are deployed at runtime into /etc/systemd/.

This approach solves the limitations of immutable filesystems by providing:

    Auditability: You can see exactly what is running in your system directories.
    Sovereignty: You can permanently modify, enable, or disable timers and services without being blocked by a read-only filesystem.
    Self-Healing: The system can automatically re-provision the environment if binaries are detected as missing on boot.

This project is built and hosted via the Fedora COPR jonathonp3/sirius-os. 
📜 License

This automation logic is licensed under GPL-3.0. The provisioned software (PIA) is subject to its own proprietary license and terms.


📦 Installation
1. On an Existing System (Silverblue, Bazzite, Wolf-OS)

Add the repository manually and then layer the package:

Add the Copr Repository
```bash
sudo curl -Lo /etc/yum.repos.d/_copr_jonathonp3-sirius-os.repo https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/repo/fedora-44/jonathonp3-sirius-os-fedora-44.repo
```
Install the Provisioner
```bash
rpm-ostree install sirius-os-pia-installer
systemctl reboot
```

2. Via BlueBuild / Custom Image

If you are building your own image via BlueBuild, add the repository URL to your recipe.yml and include the package:
yaml
```bash
# Inside recipe.yml
- type: rpm-ostree
  install:
    - sirius-os-pia-installer
```

🚀 Post-Install Provisioning

After rebooting, log into your primary account (UID 1000). The background pipeline will automatically begin building the isolated VPN environment. 

    Wait for Completion: The process usually takes 2–5 minutes depending on your internet speed.
    Monitor Progress (Optional): You can follow the logs in your terminal:

## Follow User-level extraction logs
```bash
journalctl --user -u piavpn-extract.service -f
```

## Follow Root-level deployment logs
```
sudo journalctl -u piavpn-deploy.service -f
```

🛡️ Uninstall (Atomic & Custom Image Support)

Sirius-OS PIA Installer is designed for the lifecycle of Atomic systems. If you stop using the package, it removes the installation in its entirety.

    Layered users: If you rpm-ostree remove sirius-os-pia-installer, the uninstaller runs on the next boot and purges all binaries, configurations, and VPN firewall rules.
    Custom image / BlueBuild users: If you remove the package from the recipe.yml and redeploy, the uninstaller triggers in the new deployment to clean the host.

