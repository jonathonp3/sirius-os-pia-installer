# Sirius-OS PIA Installer (v2.0.0-5)

**Automated PIA VPN provisioner for Fedora Atomic desktops (Silverblue, Bazzite, Sirius-OS).**

Version: 2.0.0-5 · License: GPL-3.0-only · [COPR: jonathonp3/sirius-os](https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/)

---

## What this is

A background pipeline that installs and maintains the Private Internet
Access VPN on an immutable Fedora system. It works around `rpm-ostree`'s
restriction on `%post` scripts by using two decoupled systemd units: a
user-level extractor that builds the PIA binaries in an isolated
container, and a root-level deployer that installs them into `/var` and
`/etc` when the extractor hands off a staging archive.

> **Compliance note.** This repository contains only provisioning and
> automation scripts. It does not include any PIA source code or
> proprietary binaries. The PIA Linux application is fetched directly
> from the official PIA website during the extraction phase and is then
> prepared to run natively on Atomic environments.

---

## Table of Contents

- [What's new in 2.0.0-5](#whats-new-in-200-5)
- [Install](#install)
- [Post-install provisioning](#post-install-provisioning)
- [Monitoring](#monitoring)
- [Health checks](#health-checks)
- [Failure playbook](#failure-playbook)
- [Things that are not problems](#things-that-are-not-problems)
- [Timing reference](#timing-reference)
- [Uninstall](#uninstall)
- [Architecture](#architecture)
- [Key design goals](#key-design-goals)
- [Where to go for more](#where-to-go-for-more)
- [License](#license)

---

## What's new in 2.0.0-5

**Upgrading from an earlier version?**

Version 2.0.0-5 changes the first-boot scripts to fix extraction on
BlueBuild/Bazzite images. Because the changes are in the provisioning
scripts, users on 2.0.0-4 or earlier must do a remove-reboot-reinstall
cycle to pick them up:

```bash
sudo rpm-ostree remove sirius-os-pia-installer
sudo systemctl reboot
# wait for the dormant uninstaller to complete, verify:
ls -la /etc/systemd/system/piavpn-uninstall.service 2>&1
# should report "No such file or directory"
sudo rpm-ostree install sirius-os-pia-installer
sudo systemctl reboot
```

Future upgrades within the 2.0.x series do not require this step
unless the scripts change again.

**What changed:** extraction was failing on BlueBuild/Bazzite first
boot. Two problems stacked:

1. `piavpn-extract.service` relied on `After=network-online.target`,
   but that target fires before DHCP has completed and DNS is
   resolving on first boot. The `curl` to the PIA download URL
   failed, and `set -euo pipefail` killed the extraction.
2. Bazzite's first-boot sequence tears down or restarts the UID 1000
   user manager after `multi-user.target` completes. Even with a
   usable network, the `--no-block` start from `piavpn-provision.sh`
   would have been killed mid-flight, and the
   `ConditionPathExists=!/etc/sirius-os/pia-provisioned` gate meant
   it never re-armed on the following boot.

The fix:

- The user timer (`piavpn-extract.timer`) now owns the first run,
  firing **1 minute and 30 seconds after boot** instead of being
  started immediately by the provisioner. That is long enough for
  NetworkManager, DHCP, and DNS to be genuinely ready, and late
  enough that the first-boot session teardown (~52s) has already
  happened.
- Added a `flock` guard so the timer and a manual
  `systemctl --user start` cannot race.
- Removed the `/usr/libexec/piavpn-deploy.sh` kickstart from the
  tail of `piavpn-provision.sh`. The `piavpn-deploy.path` unit still
  fires the root deployment the instant the staging tar lands, so
  the zero-sudo relay is unchanged.

**Note:** First install now takes longer than before. See
[Post-install provisioning](#post-install-provisioning) for timing
details.

**If you have `sirius-os-virtualization` installed**

The `nft flush ruleset` line that was removed in 2.0.0-4 had a side
effect beyond PIA. It cleared firewalld's rules as well, including the
binding of `virbr0` to the `libvirt` zone. If you installed
`sirius-os-virtualization` and used virt-manager, and you also removed
PIA at some point, your VMs would have lost DHCP and internet access.
The bridge itself is fine — `virbr0` exists and `virtnetworkd` is
running. What's missing is the firewalld zone binding.

Restore it with:

```bash
sudo firewall-cmd --zone=libvirt --add-interface=virbr0
sudo firewall-cmd --zone=libvirt --add-interface=virbr0 --permanent
```

---

## Install

### 1. On an existing system (Silverblue, Bazzite, Sirius-OS)

Add the COPR repository, then layer the package:

```bash
sudo curl -Lo /etc/yum.repos.d/_copr_jonathonp3-sirius-os.repo \
  https://copr.fedorainfracloud.org/coprs/jonathonp3/sirius-os/repo/fedora-$(rpm -E %fedora)/jonathonp3-sirius-os-fedora-$(rpm -E %fedora).repo

rpm-ostree install sirius-os-pia-installer
systemctl reboot
```

### 2. Via BlueBuild / Custom image

Add the repository URL to your `recipe.yml` and include the package:

```yaml
- type: rpm-ostree
  install:
    - sirius-os-pia-installer
```

---

## Post-install provisioning

After rebooting, log into your primary account (UID 1000). The
pipeline builds the VPN environment automatically. **You do not need
to run anything by hand.**

**Expected timing (first install only):**

| Time | What happens |
|---|---|
| 0:00 | You log in |
| ~1:30 | The extraction timer fires and the Distrobox build starts |
| ~1:30–4:30 | Container build, PIA download, binary extraction |
| ~4:30 | The VPN app appears and the daemon starts |

Total: **about 4–5 minutes from login to a working VPN.**

This delay is **intentional**. The timer waits 1:30 to clear Bazzite's
first-boot session teardown (~52s measured), and to ensure
NetworkManager, DHCP, and DNS are genuinely ready before the network
fetch. On subsequent boots the idempotency check exits immediately and
the VPN is available as soon as you log in — the delay only applies to
the first install, or when a new PIA version is available.

**BlueBuild / Bazzite users:** your machine may reboot once during
first deployment as part of Bazzite's own first-boot sequence. After
that reboot, log in and wait as above. The reboot is a natural retry
point, not a failure mode — if the first boot's extraction was
interrupted, the second boot re-checks automatically because the
success stamp was never written.

---

## Monitoring

The pipeline has two stages, each with its own log. Open two
terminals, or run one command and then the other.

### Stage 1 — extraction (user session, UID 1000)

```bash
# Follow it live:
journalctl --user -u piavpn-extract.service -f

# Current status and last few lines:
systemctl --user status piavpn-extract.service

# Full history for this boot:
journalctl --user -u piavpn-extract.service -b --no-pager
```

### Stage 2 — deployment (root)

```bash
# Current status and last few lines:
systemctl status piavpn-deploy.service

# Follow it live:
sudo journalctl -u piavpn-deploy.service -f
```

### What "done" looks like

| Stage | Success line |
|---|---|
| 1 — extract | `🚀 SUCCESS: Archive ready for deployment.` |
| 2 — deploy | `✨ Update applied successfully.` |
| daemon | `systemctl status piavpn.service` shows `active (running)` |

If Stage 1 exits without `SUCCESS`, read its last 20 lines —
`journalctl --user -u piavpn-extract.service -n 20 --no-pager` — and
check whether the network was up when the timer fired. A network
failure on first install exits 0 without writing the check stamp, so
the next boot retries automatically.

---

## Health checks

Read-only commands. Run these when you want to know the state of the
world without reading logs.

```bash
# Is the daemon running?
systemctl status piavpn.service

# Is the extraction timer armed?
systemctl --user status piavpn-extract.timer

# When did the last successful check happen?
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check

# What version is installed?
cat /var/opt/piavpn/share/version.txt

# Is a staging tar sitting around? (should be absent after deploy)
ls -la /run/user/1000/cache/pia-vpn/

# Did provisioning run for this install?
ls -la /etc/sirius-os/pia-provisioned
```

**Steady-state expectations:**

| Check | Expected |
|---|---|
| `piavpn.service` | `active (running)` |
| `piavpn-extract.timer` | `active (waiting)` |
| Stamp file | exists, mtime within 7 days |
| Version file | exists, non-empty |
| Staging dir | contains `.extract.lock` only |
| Provisioning marker | exists |

---

## Failure playbook

Symptom → diagnosis → fix. Only the failures actually observed.

### "PIA never appeared after first install"

```bash
journalctl --user -u piavpn-extract.service -n 50 --no-pager
```

- If you see `⚠️  Network unavailable` → the network was down when the
  timer fired. **Do nothing.** The next boot retries, because the
  success stamp was not written.
- If you see `❌ Error: Could not find download URL, and no local
  install exists.` → network was down *and* nothing was installed.
  Next boot retries. If it persists, check
  `ping privateinternetaccess.com`.
- If the unit shows `inactive` with no recent run → the timer did not
  fire. Check `systemctl --user status piavpn-extract.timer` and
  `systemctl --user list-timers`.
- If the log ends mid-container-build → distrobox/podman issue. Run
  `podman ps -a` and look for a stale `pia-factory`.

### "Extraction succeeded, but PIA still isn't installed"

Stage 1 finished but Stage 2 did not run.

```bash
systemctl status piavpn-deploy.service
ls -la /run/user/1000/cache/pia-vpn/pia-stage.tar.gz
```

- Tar is gone but `piavpn.service` inactive → deploy ran, daemon
  failed. Check `journalctl -u piavpn.service -n 50`.
- Tar is present, deploy shows no recent run → `piavpn-deploy.path`
  did not fire. Check `systemctl status piavpn-deploy.path`, then
  `sudo systemctl restart piavpn-deploy.path`.
- Deploy shows `ConditionPathExists` failed → `/usr/libexec/piavpn-deploy.sh`
  is missing. Package removed or partially layered. Reinstall.

### "Everything installed, VPN still not connecting"

Not a provisioning problem at this point.

```bash
systemctl status piavpn.service
journalctl -u piavpn.service -n 50 --no-pager
piactl get connectionstate
```

Check caps are intact:

```bash
getcap /var/opt/piavpn/bin/pia-daemon
getcap /var/opt/piavpn/bin/pia-unbound
```

Expected:

- `pia-daemon` → `cap_net_admin,cap_net_raw,cap_sys_admin+ep`
- `pia-unbound` → `cap_net_bind_service+ep`

If caps are missing, re-run the deploy:
`sudo /usr/libexec/piavpn-deploy.sh`.

### "After remove, something is still on the system"

The dormant uninstaller did not fully run.

```bash
systemctl status piavpn-uninstall.service
ls -la /etc/systemd/system/piavpn-*
ls -la /etc/systemd/user/piavpn-*
ls -la ~/.config/systemd/user/timers.target.wants/piavpn-extract.timer
```

The uninstaller should have removed all of those. To force a re-run:

```bash
sudo /etc/piavpn-uninstall/pia-uninstaller.sh
```

Then verify the marker files are gone:

```bash
ls /etc/sirius-os/ 2>&1        # "No such file or directory"
ls /etc/piavpn-uninstall/ 2>&1 # "No such file or directory"
```

### "systemctl --failed shows something PIA-related after removal"

Units enabled before removal, still queued by `multi-user.target` on
the next boot. Expected to be *skipped*, not *failed*. If you see
`not-found`:

```bash
ls -la /etc/systemd/system/multi-user.target.wants/piavpn-deploy.*
```

Remove any dangling symlinks, then:

```bash
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

---

## Things that are not problems

Worth listing so you don't chase them:

- **First boot takes ~5 minutes** — the timer waits 1:30, then the
  distrobox build takes 2–4 minutes. Normal.
- **Subsequent boots do nothing visible** — the stamp skips the check.
  Normal.
- **`journalctl --user -u piavpn-extract.service` shows nothing on
  most boots** — the timer's stamp check exits before the service
  starts. Check `systemctl --user status piavpn-extract.timer`
  instead.
- **`piavpn.service` restarts during an update** — the deploy script
  calls `systemctl restart piavpn.service`. Brief VPN drop during
  version updates is expected.
- **`/opt/piavpn` is a symlink to `/var/opt/piavpn`** — intentional,
  so PIA's hardcoded paths resolve on Atomic.
- **`ConditionPathExists` failures in `systemctl status`** — these are
  the design working. On the boot after package removal, the deploy
  unit is *skipped* rather than *failed*.
- **The stale stamp directory surviving removal** — it shouldn't; the
  dormant uninstaller removes `~/.local/state/sirius-os/`. If it
  survives, see the failure playbook.

---

## Timing reference

The two constants that control the pipeline, and why they are what
they are.

| Constant | Value | Where | Why |
|---|---|---|---|
| `OnBootSec` | `1min 30sec` | `piavpn-extract.timer` | Past Bazzite's ~52s first-boot session teardown, with margin. Paid only on first install; post-stamp boots exit before the network. |
| `CHECK_INTERVAL` | `7 days` | `piavpn-extract.sh` | PIA releases every 3–5 months; 7 days is fresh enough and light enough to look like a normal user, not a scraper. |

**Guard conditions** (each is a `ConditionPathExists` in a unit):

| Condition | Where | Effect |
|---|---|---|
| `!/etc/sirius-os/pia-provisioned` | `piavpn-provision.service` | Run once ever; skip every later boot |
| `/usr/libexec/piavpn-deploy.sh` | `piavpn-deploy.service` | Skip instead of fail on the boot after package removal |
| `!/etc/systemd/system/piavpn-uninstall.service` | `pia-uninstall-provision.service` | Provision the dormant uninstaller only once |

**Idempotency layers** (each stops a different kind of redundancy):

| Layer | Mechanism | Skips |
|---|---|---|
| Boot-level | `ConditionPathExists` on the provisioner | Re-provisioning `/etc` on every boot |
| Day-level | Stamp file `~/.local/state/sirius-os/pia/.last-check` | Network fetch on boots within 7 days |
| Version-level | `$VERSION_FILE` comparison | Container rebuild when already current |

The three layers are independent: any one of them can short-circuit a
boot and the system stays correct.

---

## Uninstall

Designed for the lifecycle of Atomic systems. If you stop using the
package, it removes the installation in its entirety.

- **Layered users:** `rpm-ostree remove sirius-os-pia-installer`. The
  dormant uninstaller runs on the next boot and purges all binaries
  and configurations.
- **Custom image / BlueBuild users:** remove the package from
  `recipe.yml` and redeploy. The uninstaller triggers in the new
  deployment to clean the host.

### If you have `sirius-os-virtualization` installed

The `nft flush ruleset` line removed in 2.0.0-4 had a side effect
beyond PIA: it also cleared firewalld's rules, including the binding
of `virbr0` to the `libvirt` zone. If you removed PIA on an earlier
version and used virt-manager, your VMs may have lost DHCP and
internet access.

Restore the zone binding:

```bash
sudo firewall-cmd --zone=libvirt --add-interface=virbr0
sudo firewall-cmd --zone=libvirt --add-interface=virbr0 --permanent
```

---

## Architecture

The installer implements a "relay" model designed for the constraints
of Fedora Atomic desktops. Because traditional RPM `%post` scripts are
restricted in these environments, the project uses a decoupled,
multi-stage pipeline.

### Stage 1: The extraction (user-level)

- **Unit:** `piavpn-extract.service`, triggered by `piavpn-extract.timer`
- **Context:** Runs in the user session (UID 1000)
- **Action:** Scrapes the official PIA web portal for the latest
  release, builds the binaries inside a temporary, isolated Distrobox
  factory
- **Output:** Writes a staging archive to a private, RAM-based cache:
  `/run/user/1000/cache/pia-vpn/`
- **Efficiency:** Includes a 7-day stamp cache and a version-file
  comparison to skip the container build when already up-to-date

### Stage 2: The deployment (root-level)

- **Unit:** `piavpn-deploy.service`, triggered by `piavpn-deploy.path`
- **Context:** Runs with System/Root privileges
- **Action:** Monitors the staging cache. As soon as Stage 1 delivers a
  new archive, root wakes up to:
  - Deploy binaries to persistent storage (`/var/opt/piavpn`)
  - Patch and integrate systemd units and UI assets
  - Preserve credentials and configurations across OS upgrades and
    rebases

---

## Key design goals

### Secure zero-sudo handoff

Stage 2 is activated via a systemd path unit, not a `sudo` call from
the user session. This creates a controlled, event-driven link between
user-level extraction and root-level deployment, and ensures the
extraction logic never requires broad sudo privileges.

### The blueprint provisioning model

Unit templates are stored in `/usr/share/sirius-os/pia/` (vendor
layer) and deployed to `/etc/systemd/` at runtime. This solves the
immutable-filesystem limitation by providing:

- **Auditability:** You can see exactly what is running in your system
  directories.
- **Sovereignty:** You can permanently modify, enable, or disable
  timers and services without being blocked by a read-only filesystem.
- **Self-healing:** The system can re-provision the environment if
  binaries are detected as missing on boot.

---

## Where to go for more

| Doc | When to open it |
|---|---|
| `docs/TESTING.md` | Validating a new release. Covers every path: first install, skip-on-stamp, offline, simulated update, Bazzite cross-reboot, uninstall. |
| `docs/PIA VPN Functional Testing Guide.md` | Validating that the VPN itself works (daemon health, connection, traffic routing, DNS leak, IPv6 leak, kill switch, credential persistence, firewall coexistence). |
| `docs/Full Lifecycle Timeline.md` | Understanding the order-of-operations. Diagrams every phase from package layering through uninstall. |

---

## License

This automation logic is licensed under GPL-3.0-only. The provisioned
software (PIA) is subject to its own proprietary license and terms.
