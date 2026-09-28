# Sirius-OS PIA Installer — Testing Guide

**A reference for validating a new release. Every command, path, and expected result in one place.**

## Table of Contents

- [Overview](#overview)
- [Test Environments](#test-environments)
- [Build & Install](#build--install)
- [Test 1 — First Install (Full Pipeline)](#test-1--first-install-full-pipeline)
- [Test 2 — Skip on Fresh Stamp](#test-2--skip-on-fresh-stamp)
- [Test 3 — Deleted Stamp Directory](#test-3--deleted-stamp-directory)
- [Test 4 — Stale Stamp](#test-4--stale-stamp)
- [Test 5 — Offline with PIA Installed](#test-5--offline-with-pia-installed)
- [Test 6 — Offline without PIA Installed](#test-6--offline-without-pia-installed)
- [Test 7 — Simulated New PIA Release](#test-7--simulated-new-pia-release)
- [Test 8 — Bazzite First Boot (cross-reboot)](#test-8--bazzite-first-boot-cross-reboot)
- [Test 9 — Uninstall / Dormant Cleanup](#test-9--uninstall--dormant-cleanup)
- [Reference — File Locations](#reference--file-locations)
- [Reference — Common Journal Commands](#reference--common-journal-commands)
- [Reference — Clearing the Stamp](#reference--clearing-the-stamp)
- [Reference — Simulating a New PIA Release](#reference--simulating-a-new-pia-release)
- [Reference — Offline Testing](#reference--offline-testing)
- [Reference — Verifying the Interval Boundary](#reference--verifying-the-interval-boundary)
- [Test Matrix](#test-matrix)

---

## Overview

The package has two independent scripts that need testing:

- **`piavpn-extract.sh`** — runs as UID 1000, downloads PIA, builds the Distrobox container, stages a tarball.
- **`piavpn-deploy.sh`** — runs as root, triggered by a path unit, deploys the tarball to `/var/opt/piavpn`, restarts `piavpn.service`.

The validation matrix covers:

- Atomic vs. non-atomic (`is_atomic` branch of `piavpn-deploy.sh`)
- Online vs. offline (offline branch of `piavpn-extract.sh`)
- First-install vs. update (version comparison)
- Fresh vs. stale vs. missing stamp (stamp cache)
- Cross-reboot on Bazzite (first-boot teardown, timer delay)
- Install vs. uninstall (dormant uninstaller)

## Test Environments

| Environment | Type | Atomic? | First-Boot Reboot? | Purpose |
|---|---|---:|---:|---|
| **Workstation VM** | Fedora Workstation | No | No | Fast iteration and testing the non-atomic path. |
| **Silverblue VM** | Fedora Silverblue | Yes | No | Testing the atomic path without Bazzite-specific behavior. |
| **Bazzite bare metal** | Bazzite | Yes | Yes | Testing the scenario that caused version `2.0.0-4` to fail. |

**Important:** first-boot bugs only appear on true first boots. Upgrading an existing system does not exercise the same code paths. If you want to test first-boot behavior, use a fresh install or a snapshotted pre-first-boot VM.

## Build & Install

### On the Workstation VM (build host)

```bash
# 1. Sync sources from the repo
cp /path/to/repo/piavpn-*.sh        ~/rpmbuild/SOURCES/
cp /path/to/repo/piavpn-*.service   ~/rpmbuild/SOURCES/
cp /path/to/repo/piavpn-*.timer     ~/rpmbuild/SOURCES/
cp /path/to/repo/piavpn-*.path      ~/rpmbuild/SOURCES/
cp /path/to/repo/pia-uninstall-provision.* ~/rpmbuild/SOURCES/
cp /path/to/repo/README.md          ~/rpmbuild/SOURCES/
cp /path/to/repo/sirius-os-pia.sysusers ~/rpmbuild/SOURCES/
cp /path/to/repo/sirius-os-pia-installer.spec ~/rpmbuild/SPECS/

# 2. Sanity-check the scripts
bash -n ~/rpmbuild/SOURCES/piavpn-extract.sh
bash -n ~/rpmbuild/SOURCES/piavpn-deploy.sh
bash -n ~/rpmbuild/SOURCES/piavpn-provision.sh
bash -n ~/rpmbuild/SOURCES/pia-uninstall-provision.sh

# 3. Build
cd ~/rpmbuild/SPECS
rpmbuild -ba sirius-os-pia-installer.spec

# 4. Verify the RPM contains the fixed script
rpm2cpio ~/rpmbuild/RPMS/noarch/sirius-os-pia-installer-*.rpm \
  | cpio -idmv --to-stdout ./usr/libexec/piavpn-extract.sh 2>/dev/null \
  | grep -n "STAMP_FILE=\|RAW=\|head -n 1 || true"

# 5. Output artifacts
ls -la ~/rpmbuild/RPMS/noarch/
ls -la ~/rpmbuild/SRPMS/
```

### On Workstation VM (install)

```bash
sudo dnf install -y --allowerasing ~/rpmbuild/RPMS/noarch/sirius-os-pia-installer-*.rpm

# Reboot for systemd units to be picked up
sudo systemctl reboot
```

### On Silverblue / Bazzite (install)

```bash
# Copy the RPM to the target machine first (scp, usb, whatever)
sudo rpm-ostree install /path/to/sirius-os-pia-installer-*.rpm
sudo systemctl reboot
```

---

## Test 1 — First Install (Full Pipeline)

**Goal:** Confirm the entire pipeline runs end-to-end on first install.

**Environment:** Any (Workstation, Silverblue, Bazzite). On Bazzite, this is the test that used to fail.

### Steps

```bash
# 1. Ensure no prior state
ls -la /var/opt/piavpn 2>&1
ls -la /etc/sirius-os/pia-provisioned 2>&1
ls -la ~/.local/state/sirius-os/pia/.last-check 2>&1

# 2. Reboot into the new deployment
sudo systemctl reboot

# 3. Log in as UID 1000, then WAIT 3 MINUTES. Do not touch anything.

# 4. Check the provisioner ran (system-level)
sudo systemctl status piavpn-provision.service
ls -la /etc/sirius-os/pia-provisioned

# 5. Check the extraction timer armed (user-level)
systemctl --user status piavpn-extract.timer

# 6. Check the extraction ran
systemctl --user status piavpn-extract.service
journalctl --user -u piavpn-extract.service -b --no-pager

# 7. Check the path unit is watching
sudo systemctl status piavpn-deploy.path

# 8. Check the deploy ran
sudo systemctl status piavpn-deploy.service
sudo journalctl -u piavpn-deploy.service -b --no-pager

# 9. Check the stamp was created
ls -la ~/.local/state/sirius-os/pia/.last-check

# 10. Check PIA is running
systemctl status piavpn.service
pgrep -a pia-daemon
```

### Expected Results

- `piavpn-provision.service`: `active (exited)`, marker file exists
- `piavpn-extract.timer`: `active (waiting)`
- `piavpn-extract.service`: `active (exited)`, exit code 0, journal shows successful extraction
- `piavpn-deploy.path`: `active (waiting)`
- `piavpn-deploy.service`: `inactive (dead)` or `active (exited)`, journal shows `✨ Update applied successfully.`
- Stamp file exists with today's timestamp
- `piavpn.service`: `active (running)`
- `pia-daemon` process: running from `/var/opt/piavpn/bin/pia-daemon`

---

## Test 2 — Skip on Fresh Stamp

**Goal:** Confirm the 7-day stamp cache prevents a redundant network check.

**Environment:** Any, after Test 1 has passed.

### Steps

```bash
# 1. Confirm the stamp is fresh
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check

# 2. Trigger the service
systemctl --user restart piavpn-extract.service

# 3. Check the journal
journalctl --user -u piavpn-extract.service -b --no-pager | tail -6
```

### Expected Results

Expected journal lines (in order):

```text
⏩ Last check was 0d ago; skipping (interval: 7 days).
Finished piavpn-extract.service
```

Not expected:

```text
🔍 Sirius-OS: Checking for PIA VPN updates...
```

- No curl, no container build
- The service exits in under a second
- The stamp file's mtime is unchanged

---

## Test 3 — Deleted Stamp Directory

**Goal:** Confirm the script recreates the stamp directory if it's missing.

**Environment:** Any.

### Steps

```bash
# 1. Delete the stamp tree
rm -rf ~/.local/state/sirius-os

# 2. Trigger the service
systemctl --user restart piavpn-extract.service

# 3. Check the journal
journalctl --user -u piavpn-extract.service -b --no-pager | tail -6

# 4. Check the stamp was recreated
ls -la ~/.local/state/sirius-os/pia/
```

### Expected Results

- Journal shows a real check (`🔍 Sirius-OS: Checking...` then `✅ Already up to date`)
- Directory and stamp file recreated
- Owned by UID 1000, mode 644

---

## Test 4 — Stale Stamp

**Goal:** Confirm a stale stamp triggers a real check and gets refreshed.

**Environment:** Any.

### Steps

```bash
# 1. Backdate the stamp past the 7-day window
touch -d "8 days ago" ~/.local/state/sirius-os/pia/.last-check

# 2. Verify the timestamp
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check
# Expect: a timestamp 8 days in the past

# 3. Trigger the service
systemctl --user restart piavpn-extract.service

# 4. Check the journal
journalctl --user -u piavpn-extract.service -b --no-pager | tail -6

# 5. Verify the stamp was refreshed
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check
# Expect: a timestamp within the last minute
```

### Expected Results

- Journal shows `🔍 Sirius-OS: Checking for PIA VPN updates...` and `✅ Already up to date`
- No `⏩` skip line
- Stamp mtime is refreshed to now

---

## Test 5 — Offline with PIA Installed

**Goal:** Confirm the script exits cleanly when offline and PIA is already installed.

**Environment:** Any, with PIA already installed from Test 1.

### Steps

```bash
# 1. Disable networking
nmcli networking off

# 2. Backdate the stamp so the check runs
touch -d "8 days ago" ~/.local/state/sirius-os/pia/.last-check

# 3. Trigger the service
systemctl --user restart piavpn-extract.service

# 4. Check the journal
journalctl --user -u piavpn-extract.service -b --no-pager | tail -8

# 5. Check the service state
systemctl --user status piavpn-extract.service | grep -E "Active|status="

# 6. Verify the stamp was NOT refreshed (should still be 8 days ago)
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check

# 7. Restore networking
nmcli networking on
```

### Expected Results

Expected journal lines (in order):

```text
🔍 Sirius-OS: Checking for PIA VPN updates...
⚠️  Network unavailable; PIA already installed, skipping check.
    The next boot or monthly timer will retry.
Finished piavpn-extract.service
```

- `Active: active (exited)`, `status=0/SUCCESS`
- Not failed, no exit-code
- **Stamp mtime is unchanged (still 8 days ago)** — this is critical for the retry-on-next-boot behavior

---

## Test 6 — Offline without PIA Installed

**Goal:** Confirm the script fails loudly when offline AND PIA is not installed.

**Environment:** Any, but requires moving PIA aside temporarily.

### Steps

```bash
# 1. Move PIA aside
sudo mv /var/opt/piavpn /var/opt/piavpn.backup

# 2. Disable networking
nmcli networking off

# 3. Delete the stamp so the check is guaranteed to run
rm -f ~/.local/state/sirius-os/pia/.last-check

# 4. Trigger the service
systemctl --user restart piavpn-extract.service

# 5. Check the journal
journalctl --user -u piavpn-extract.service -b --no-pager | tail -8

# 6. Check the service state
systemctl --user status piavpn-extract.service | grep -E "Active|status="

# 7. Restore
nmcli networking on
sudo mv /var/opt/piavpn.backup /var/opt/piavpn
```

### Expected Results

Expected journal lines (in order):

```text
🔍 Sirius-OS: Checking for PIA VPN updates...
❌ Error: Could not find download URL, and no local install exists.
```

- `Active: failed (Result: exit-code)`, `status=1/FAILURE`
- **This is the only path that should fail**

---

## Test 7 — Simulated New PIA Release

**Goal:** Confirm the "update available" path runs the full pipeline.

**Environment:** Any, with PIA already installed.

### Steps

```bash
# 1. Back up the current version file
sudo cp /var/opt/piavpn/share/version.txt /var/opt/piavpn/share/version.txt.bak

# 2. Replace the first line with a fake old version
sudo sed -i '1s/.*/3.5.7+00000/' /var/opt/piavpn/share/version.txt
cat /var/opt/piavpn/share/version.txt

# 3. Delete the stamp so the check runs
rm -f ~/.local/state/sirius-os/pia/.last-check

# 4. Trigger the extraction
systemctl --user restart piavpn-extract.service

# 5. Watch in one terminal
journalctl --user -u piavpn-extract.service -f

# 6. In another terminal, watch the deploy
sudo journalctl -u piavpn-deploy.service -f

# 7. After both complete, verify the version file was updated
cat /var/opt/piavpn/share/version.txt

# 8. Verify the stamp was refreshed
stat -c '%y' ~/.local/state/sirius-os/pia/.last-check

# 9. Verify PIA is running
systemctl status piavpn.service
pgrep -a pia-daemon

# 10. Verify the next run skips
systemctl --user restart piavpn-extract.service
journalctl --user -u piavpn-extract.service -b --no-pager | tail -4

# 11. Clean up
sudo rm /var/opt/piavpn/share/version.txt.bak
```

### Expected Results

**Extraction journal:**

```text
🔍 Sirius-OS: Checking for PIA VPN updates...
🏗️ Update found: 3.5.7-00000 -> 3.7.2-08420
🏗️ Preparing build environment...
📦 Creating fresh build environment (Fedora)...
🛠️ Entering container to prepare binaries...
   -> Phase 1/4: Installing build dependencies (dnf)...
   -> Phase 2/4: Downloading and verifying PIA v3.7.2-08420...
   -> Phase 3/4: Running installer...
   -> Phase 4/4: Creating staging archive from container files...
🚚 Extracting archive to user staging area...
🚀 SUCCESS: Archive ready for deployment.
🧹 Auto-cleanup: Removing container 'pia-factory'...
```

**Deploy journal:**

```text
🚀 Sirius-OS PIA VPN Deployment starting...
💻 Workstation environment detected.     (or 🏗️ Atomic environment detected.)
🚚 New update found! Deploying to persistent store...
...
✨ Update applied successfully.
```

**Post-checks:**

- `version.txt` shows current version (deploy overwrote the fake one)
- Stamp refreshed
- `piavpn.service` active, `pia-daemon` running
- Next run shows `⏩ Last check was 0d ago; skipping (interval: 7 days).`

---

## Test 8 — Bazzite First Boot (cross-reboot)

**Goal:** Confirm the 2.0.0-5 fix works: extraction survives Bazzite's first-boot reboot and the second boot skips cleanly.

**Environment:** Bazzite, bare metal, fresh install.

### Steps

````bash
# ===== BEFORE INSTALL =====
ls -la /var/opt/piavpn 2>&1            # should not exist
ls -la /etc/sirius-os/ 2>&1            # should not exist

# ===== INSTALL =====
sudo rpm-ostree install /path/to/sirius-os-pia-installer-*.rpm
sudo systemctl reboot

# ===== FIRST BOOT =====
# Bazzite may reboot again automatically as part of its first-boot sequence.
# Do not touch anything. Wait for the machine to settle.

# After you have logged in on a stable session, IMMEDIATELY check:
journalctl --list-boots | tail -5
# Note how many boots are listed since install. Two boots means Bazzite rebooted once.

# ===== WAIT 3 MINUTES without touching anything =====

# ===== VERIFY FIRST BOOT EXTRACTION =====
sudo journalctl -b -1 -u piavpn-provision.service --no-pager | tail -30
ls -la /etc/sirius-os/pia-provisioned
systemctl --user status piavpn-extract.timer
systemctl --user status piavpn-extract.service
journalctl --user -u piavpn-extract.service -b -1 --no-pager | tail -20

sudo systemctl status piavpn-deploy.path
sudo systemctl status piavpn-deploy.service
sudo journalctl -u piavpn-deploy.service -b -1 --no-pager | tail -20

ls -la ~/.local/state/sirius-os/pia/.last-check
systemctl status piavpn.service
pgrep -a pia-daemon

# ===== REBOOT AGAIN (SECOND BOOT) =====
sudo systemctl reboot

# ===== SECOND BOOT =====
# Log in. Wait 3 minutes.

# Verify the provisioner did NOT re-run
sudo systemctl status piavpn-provision.service
# Expect: Active: inactive (dead) — because ConditionPathExists saw the marker

# Verify the timer fired but skipped
journalctl --user -u piavpn-extract.service -b --no-pager | tail -6
# Expect: ⏩ Last check was 0d ago; skipping (interval: 7 days).

# Verify PIA is still running
systemctl status piavpn.service
```

Expected Results

First boot:

    piavpn-provision.service ran once, marker exists

    Timer fired at 1 minute 30 seconds

    Extraction ran to completion

    Deploy ran off the path unit

    Stamp created

    PIA running

Second boot:

    piavpn-provision.service did not re-run

    Timer fired at 1 minute 30 seconds

    Extraction service shows ⏩ Last check was 0d ago; skipping (interval: 7 days). — no re-extraction

    PIA still running, no disruption

Critical check: if the second boot shows 🔍 Sirius-OS: Checking... and re-runs the extraction, the stamp was not created during first boot. That would be the failure mode to investigate.

Test 9 — Uninstall / Dormant Cleanup

Goal: Confirm removal cleans up everything on the next boot.

Environment: Any, after successful install.

Steps

```bash
# 1. Before uninstall, note what exists
ls -la /var/opt/piavpn 2>&1
ls -la /opt/piavpn 2>&1
ls -la /etc/systemd/system/piavpn* 2>&1
ls -la /etc/systemd/user/piavpn* 2>&1
ls -la ~/.local/state/sirius-os/ 2>&1
systemctl status piavpn.service

# 2. Remove the package
# Layered:
sudo rpm-ostree remove sirius-os-pia-installer
# OR BlueBuild: remove from recipe.yml and redeploy

# 3. Reboot
sudo systemctl reboot

# 4. After reboot, check the dormant uninstaller ran
sudo journalctl -u pia-uninstall-provision.service -b --no-pager
sudo journalctl -u piavpn-uninstall.service -b --no-pager

# 5. Verify cleanup
ls -la /var/opt/piavpn 2>&1                # should not exist
ls -la /opt/piavpn 2>&1                    # should not exist (or be a dangling symlink)
ls -la /etc/systemd/system/piavpn* 2>&1    # should not exist
ls -la /etc/systemd/user/piavpn* 2>&1      # should not exist
ls -la /etc/sirius-os/ 2>&1                # should not exist
ls -la ~/.local/state/sirius-os/ 2>&1      # should not exist
systemctl status piavpn.service 2>&1       # should be "not found"
systemctl --user status piavpn-extract.timer 2>&1  # should be "not found"

# 6. Check for failed units
systemctl --failed
systemctl --user --failed
```

Expected Results

    Dormant uninstaller journal shows ✨ VPN has been completely removed from Sirius-OS.

    All PIA files gone from /var/opt/piavpn, /opt/piavpn, /etc/systemd/system/, /etc/systemd/user/, /etc/sirius-os/

    The user-level stamp directory (~/.local/state/sirius-os/) is gone

    systemctl --failed shows no PIA-related units

    systemctl --user --failed shows no PIA-related units
    
## Reference — File Locations

### Installed by the RPM

| Path | Purpose |
| --- | --- |
| `/usr/libexec/piavpn-extract.sh` | User-level extraction script |
| `/usr/libexec/piavpn-deploy.sh` | Root-level deployment script |
| `/usr/libexec/piavpn-provision.sh` | Root-level first-boot provisioner |
| `/usr/libexec/pia-uninstall-provision.sh` | Root-level uninstall provisioner |
| `/usr/share/sirius-os/pia/piavpn-extract.service` | Blueprint for the user service |
| `/usr/share/sirius-os/pia/piavpn-extract.timer` | Blueprint for the user timer |
| `/usr/share/sirius-os/pia/piavpn-deploy.service` | Blueprint for the system service |
| `/usr/share/sirius-os/pia/piavpn-deploy.path` | Blueprint for the system path unit |
| `/usr/lib/systemd/system/piavpn-provision.service` | Vendor-layer provisioner unit |
| `/usr/lib/systemd/system/pia-uninstall-provision.service` | Vendor-layer uninstaller unit |
| `/usr/lib/sysusers.d/sirius-os-pia.conf` | Group definitions: `piahnsd` and `piavpn` |
| `/usr/share/doc/sirius-os-pia-installer/README.md` | Documentation |


## Files Created at Runtime

| Path | Created By | Purpose |
| --- | --- | --- |
| `/etc/systemd/system/piavpn-deploy.service` | Provisioner; copied from `/usr/share/sirius-os/` | System service for deployment |
| `/etc/systemd/system/piavpn-deploy.path` | Provisioner | Watches for the staging archive |
| `/etc/systemd/user/piavpn-extract.service` | Provisioner | User service for extraction |
| `/etc/systemd/user/piavpn-extract.timer` | Provisioner | User timer for extraction |
| `/etc/systemd/system/piavpn.service` | Deploy script; extracted from the PIA archive | PIA daemon service |
| `/etc/systemd/system/piavpn-uninstall.service` | Uninstall provisioner | Dormant uninstaller |
| `/etc/piavpn-uninstall/pia-uninstaller.sh` | Uninstall provisioner | Embedded uninstall script |
| `/etc/sirius-os/pia-provisioned` | Provisioner | Marker indicating provisioning is complete |
| `/var/opt/piavpn/` | Deploy script | Persistent PIA installation |
| `/usr/local/bin/piactl` | Deploy script | Symlink to the CLI tool |
| `/usr/local/bin/pia-daemon` | Deploy script | Symlink to the daemon binary |
| `/usr/local/bin/pia-client` | Deploy script | Symlink to the GUI client |
| `/usr/local/bin/pia-unbound` | Deploy script | Symlink to the DNS resolver |
| `/usr/local/share/applications/piavpn.desktop` | Deploy script | Desktop entry |
| `/usr/local/share/pixmaps/piavpn.png` | Deploy script | Application icon |
| `/opt/piavpn` | Deploy script; workstation only | Symlink to `/var/opt/piavpn` |
| `/run/user/1000/cache/pia-vpn/` | Extraction script | Temporary staging area stored in RAM |
| `/run/user/1000/cache/pia-vpn/pia-stage.tar.gz` | Extraction script | Staging archive |
| `/run/user/1000/cache/pia-vpn/.extract.lock` | Extraction script | `flock` guard file |
| `~/.local/state/sirius-os/pia/.last-check` | Extraction script | 7-day update-check cache |

## Logged-In and Referenced Paths

| Path | Purpose |
| --- | --- |
| `/var/opt/piavpn/share/version.txt` | Stores the current PIA version; read by the extraction script and written by the deploy script |
| `/etc/NetworkManager/conf.d/wgpia.conf` | WireGuard interface configuration from the PIA archive |
| `/var/lib/systemd/linger/jonathon` | Enables user services to run without an active login session |


## Reference — Common Journal Commands

### User-level services (run as yourself)

User-level services (run as yourself)

```bash
# Follow the extraction service in real time
journalctl --user -u piavpn-extract.service -f

# Last 20 lines of the current boot
journalctl --user -u piavpn-extract.service -b --no-pager | tail -20

# Only entries since a specific time
journalctl --user -u piavpn-extract.service --since "20:00" --no-pager

# The timer's schedule and last/next fire
systemctl --user status piavpn-extract.timer

# List all user-level PIA units
systemctl --user list-units | grep piavpn

System-level services (need sudo)
bash

# Follow the deploy service in real time
sudo journalctl -u piavpn-deploy.service -f

# Follow the path unit
sudo journalctl -u piavpn-deploy.path -f

# Follow the provisioner
sudo journalctl -u piavpn-provision.service -f

# Follow the PIA daemon
sudo journalctl -u piavpn.service -f

# All PIA-related system units on this boot
sudo journalctl -b --no-pager | grep -i piavpn | tail -50
```

## Previous boots

```bash
# List all boots
journalctl --list-boots

# Provisioner on the previous boot
sudo journalctl -b -1 -u piavpn-provision.service --no-pager

# Extraction on the previous boot
journalctl --user -u piavpn-extract.service -b -1 --no-pager

# Deploy on the previous boot
sudo journalctl -u piavpn-deploy.service -b -1 --no-pager

Service states
bash

# System services
systemctl status piavpn.service
systemctl status piavpn-provision.service
systemctl status piavpn-deploy.path
systemctl status piavpn-deploy.service

# User services
systemctl --user status piavpn-extract.timer
systemctl --user status piavpn-extract.service

# Any failed units
systemctl --failed
systemctl --user --failed
```

## Manual triggering

```bash
# Trigger the extraction (as UID 1000)
systemctl --user restart piavpn-extract.service

# Trigger the deploy (as root)
sudo systemctl restart piavpn-deploy.service

# Verify the path unit is armed
systemctl status piavpn-deploy.path
# Expect: Active: active (waiting)

# List what the path unit is watching
systemctl cat piavpn-deploy.path
# PathExists=/run/user/1000/cache/pia-vpn/pia-stage.tar.gz
```

Journal cleanup (test VMs only)

```bash
# Rotate and vacuum (frees space, clears history)
sudo journalctl --rotate
sudo journalctl --vacuum-time=1s

# Check current usage
journalctl --disk-usage

Reference — Clearing the Stamp

For any test that needs the extraction to do a real check instead of skipping:
bash

# Option 1 — delete the stamp (also exercises the recreate-directory path)
rm -f ~/.local/state/sirius-os/pia/.last-check

# Option 2 — backdate it past the 7-day window (keeps the directory in place)
touch -d "8 days ago" ~/.local/state/sirius-os/pia/.last-check

# Then trigger
systemctl --user restart piavpn-extract.service
```

### Option 2 is preferred for testing because the stamp file remains in place, so you don't exercise the "recreate directory" path unless that's what you want to test.

## Reference — Simulating a New PIA Release

To test the update pipeline without waiting for PIA to actually release a new version:

```bash
# Back up the real version
sudo cp /var/opt/piavpn/share/version.txt /var/opt/piavpn/share/version.txt.bak

# Replace line 1 with a fake old version
sudo sed -i '1s/.*/3.5.7+00000/' /var/opt/piavpn/share/version.txt

# Clear the stamp
rm -f ~/.local/state/sirius-os/pia/.last-check

# Trigger
systemctl --user restart piavpn-extract.service

After the deploy runs, version.txt will be overwritten with the real current version. Remove the backup:
bash

sudo rm /var/opt/piavpn/share/version.txt.bak
```

## Reference — Offline Testing

```bash
# Disable networking (NetworkManager)
nmcli networking off

# ... run test ...

# Re-enable
nmcli networking on

# Verify state
nmcli networking

Alternative: block PIA's host in /etc/hosts:
bash

sudo sh -c 'echo "0.0.0.0 www.privateinternetaccess.com" >> /etc/hosts'
sudo resolvectl flush-caches

# ... run test ...

sudo sed -i '/0.0.0.0 www.privateinternetaccess.com/d' /etc/hosts
sudo resolvectl flush-caches

The nmcli networking off approach is cleaner and tests the same code path (curl fails, offline branch runs).
Reference — Verifying the Interval Boundary
```

## The script compares AGE < CHECK_INTERVAL. To confirm the boundary is where you think it is:

```bash
# Just inside the window — should SKIP
touch -d "6 days ago" ~/.local/state/sirius-os/pia/.last-check
systemctl --user restart piavpn-extract.service
journalctl --user -u piavpn-extract.service -b --no-pager | tail -3
# Expect: ⏩ Last check was 6d ago; skipping (interval: 7 days).

# Exactly at the boundary — should CHECK (not less-than)
touch -d "7 days ago" ~/.local/state/sirius-os/pia/.last-check
systemctl --user restart piavpn-extract.service
journalctl --user -u piavpn-extract.service -b --no-pager | tail -3
# Expect: 🔍 Sirius-OS: Checking for PIA VPN updates...

# Just outside — should CHECK
touch -d "8 days ago" ~/.local/state/sirius-os/pia/.last-check
systemctl --user restart piavpn-extract.service
journalctl --user -u piavpn-extract.service -b --no-pager | tail -3
# Expect: 🔍 Sirius-OS: Checking for PIA VPN updates...
```

If any of these three behaves differently, the interval or the comparison operator has changed. This is the test to run after touching CHECK_INTERVAL or the age check.

## Test Matrix

| Test | Environment | Depends On | Estimated Time |
| --- | --- | --- | --- |
| 1 — First Install | Any | Fresh install | ~10 minutes |
| 2 — Skip on Fresh Stamp | Any | Test 1 | ~1 minute |
| 3 — Deleted Stamp Directory | Any | Test 1 | ~2 minutes |
| 4 — Stale Stamp | Any | Test 1 | ~2 minutes |
| 5 — Offline + Installed | Any | Test 1 | ~2 minutes |
| 6 — Offline + Not Installed | Any | Test 1 | ~2 minutes |
| 7 — Simulated New Release | Any | Test 1 | ~10 minutes |
| 8 — Bazzite First Boot | Bazzite bare metal | Fresh install | ~20 minutes |
| 9 — Uninstall | Any | Test 1 | ~5 minutes |


Typical validation sequence for a new release:

    Rebuild on Workstation VM

    Tests 1–7 on Workstation VM (about 30 min total)

    Tests 1, 2, 5, 7 on Silverblue VM (about 20 min)

    Tests 1, 8 on Bazzite bare metal (about 20 min)

    Merge testing → main

    Let COPR rebuild

    Optionally: Test 9 on one machine before final release

End of testing guide. 


