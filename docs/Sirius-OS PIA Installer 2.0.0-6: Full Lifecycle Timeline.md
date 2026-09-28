## Phase 0 — Package layering (rpm-ostree install)

```text

┌─────────────────────────────────────────────────────────────────────┐
│ [PKG] rpm-ostree install sirius-os-pia-installer                    │
│       ↓                                                             │
│       Unpacks files into /usr (read-only vendor layer):             │
│         /usr/libexec/piavpn-provision.sh                            │
│         /usr/libexec/pia-uninstall-provision.sh                     │
│         /usr/libexec/piavpn-extract.sh                              │
│         /usr/libexec/piavpn-deploy.sh                               │
│         /usr/share/sirius-os/pia/*.service / *.timer / *.path       │
│         /usr/lib/systemd/system/piavpn-provision.service            │
│         /usr/lib/systemd/system/pia-uninstall-provision.service     │
│         /usr/lib/sysusers.d/sirius-os-pia.conf                      │
│       ↓                                                             │
│       Vendor-layer symlinks (enabled immediately on layering):      │
│         multi-user.target.wants/piavpn-provision.service     → ON   │
│         multi-user.target.wants/pia-uninstall-provision.service → ON│
│       ↓                                                             │
│       sysusers creates groups:  piahnsd(954), piavpn(955)           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                        reboot required
```
Nothing has run yet. No extraction, no deployment. Just files in /usr and two enabled system units.


## Phase 1 — First boot after install


```text

t=0  Boot starts
     │
     ├─ systemd reaches multi-user.target
     │
     ├──────────────────────────────────────────────────────────────┐
     │ [SYS] piavpn-provision.service                               │
     │       ConditionPathExists=!/etc/sirius-os/pia-provisioned    │
     │       → marker absent → RUNS                                 │
     │                                                              │
     │   piavpn-provision.sh:                                       │
     │   1. Copies blueprints /usr/share/sirius-os/pia/* → /etc/    │
     │      (atomic .tmp + mv -f, so systemd never sees partial)    │
     │   2. Enables linger for UID 1000                             │
     │   3. Waits for /run/user/1000/systemd/private (≤15s)         │
     │   4. systemctl daemon-reload                                 │
     │      systemctl enable --now piavpn-deploy.path               │
     │      systemctl enable piavpn-deploy.service                  │
     │      systemctl --user -M jonathon@ enable --now              │
     │                       piavpn-extract.timer                   │
     │   5. touch /etc/sirius-os/pia-provisioned                    │
     │                                                              │
     │   NOTE: does NOT kickstart the extract script anymore.       │
     │         The timer owns first run.                            │
     └──────────────────────────────────────────────────────────────┘
     │
     └──────────────────────────────────────────────────────────────┐
        │ [SYS] pia-uninstall-provision.service                     │
        │       ConditionPathExists=!.../piavpn-uninstall.service   │
        │       → not present → RUNS (provisions the dormant        │
        │         uninstaller for later; does nothing now)          │
        └──────────────────────────────────────────────────────────────┘
     │
     │  user logs in (UID 1000)
     │
     ▼
t=+1min 30sec   [TMR] piavpn-extract.timer fires
                │
                ├─ Stamp check: ~/.local/state/sirius-os/pia/.last-check
                │  → absent (first install) → continue
                │
                ├─ flock -n 9 on /run/user/1000/cache/pia-vpn/.extract.lock
                │  → acquired → continue
                │
                ├─ [USR] piavpn-extract.sh runs:
                │     1. curl PIA download page (|| true, --max-time 30)
                │     2. grep for latest .run URL (|| true)
                │     3. If URL empty AND version file exists
                │        → exit 0, DON'T write stamp (retry next boot)
                │     4. If URL empty AND no version file
                │        → exit 1 (genuine first-install failure)
                │     5. Compare LATEST_VER vs $VERSION_FILE
                │        → equal → touch stamp, exit 0
                │        → different → continue
                │     6. Purge any stale pia-factory container
                │     7. distrobox create pia-factory (fedora:latest)
                │     8. distrobox enter:
                │          dnf install deps
                │          wget .run file
                │          .run --check
                │          .run --quiet   ← installs into container
                │          tar czf /tmp/pia-stage.tar.gz …
                │     9. podman cp container:/tmp/pia-stage.tar.gz
                │          → $STAGING_TAR.tmp
                │    10. sync $STAGING_TAR.tmp
                │    11. mv -f $STAGING_TAR.tmp $STAGING_TAR
                │        ← ATOMIC: this mv is the handoff event
                │    12. touch stamp
                │    13. trap cleanup removes pia-factory container
                │
                ▼
        /run/user/1000/cache/pia-vpn/pia-stage.tar.gz now exists
                │
                ▼
        [PATH] piavpn-deploy.path detects PathExists= on staging tar
                │
                ▼
        [SYS] piavpn-deploy.service
             ConditionPathExists=/usr/libexec/piavpn-deploy.sh
             After=piavpn-provision.service, user@1000.service
             Before=piavpn.service, Wants=piavpn.service
                │
                └─ piavpn-deploy.sh runs:
                   1. Atomic check (/run/ostree-booted)
                   2. If workstation: fix /opt/piavpn symlink bridge
                   3. Staging tar exists → deploy path:
                        tar -xzf → /etc/*
                        tar -xzf → /usr/local/share/applications
                        tar -xzf → /usr/local/share/pixmaps
                        tar -xzf → /var/opt/piavpn/bin (excl. etc/)
                   4. ln -sf binaries → /usr/local/bin/
                   5. sed patch piavpn.service + .desktop
                      (=/opt → =/var/opt)
                   6. chown root:root, chgrp piavpn(955) etc/
                   7. chmod 755 dirs/binaries
                   8. chmod 4750 support-tool-launcher
                   9. chmod 600 account.json, 644 data/settings.json
                  10. setcap on pia-unbound, pia-daemon
                  11. rm $STAGING_TAR (+ .tmp)
                  12. systemctl daemon-reload
                  13. systemctl restart piavpn.service --no-block
                  14. touch /usr/local/share/applications (menu nudge)
                │
                ▼
        [SYS] piavpn.service (from PIA installer tar)
             → daemon starts, VPN available
```
End state after first boot: PIA installed, daemon running, stamp written, timer still armed for next boot.

---


## Phase 2 — Subsequent boots (nothing changed upstream)

```text

t=0  Boot
     │
     ├─ [SYS] piavpn-provision.service
     │       ConditionPathExists=!/etc/sirius-os/pia-provisioned
     │       → marker EXISTS → SKIPPED  (near-zero cost)
     │
     ├─ [SYS] pia-uninstall-provision.service
     │       ConditionPathExists=!.../piavpn-uninstall.service
     │       → already provisioned → SKIPPED
     │
     │  user logs in
     ▼
t=+1min 30sec   [TMR] piavpn-extract.timer fires
                │
                ├─ flock acquired
                │
                ├─ [USR] piavpn-extract.sh:
                │     Stamp check: ~/.local/state/sirius-os/pia/.last-check
                │     age < 7 days ?
                │        → YES → "Last check was Nd ago; skipping."
                │               exit 0   ← NO NETWORK, NO CONTAINER
                │
                ▼
             (nothing else happens)
```

Boot 2–7 after a successful check = one stat call and exit. No curl, no distrobox, no root deploy. The whole pipeline is dormant.
Phase 3 — Boot after stamp expires (>7 days)

```text

t=0  Boot
     │  (provisioners skipped as in Phase 2)
     │  user logs in
     ▼
t=+1min 30sec   [TMR] piavpn-extract.timer fires
                │
                ├─ flock acquired
                │
                ├─ [USR] piavpn-extract.sh:
                │     Stamp age ≥ 7 days → continue
                │     curl PIA download page
                │     grep latest .run URL
                │
                ├─── CASE A: LATEST_VER == CURRENT_VER
                │       "Already up to date"
                │       rm staging tar + .tmp
                │       touch stamp
                │       exit 0
                │       → no deploy, no restart, VPN stays up
                │
                └─── CASE B: LATEST_VER != CURRENT_VER
                        distrobox build → new staging tar
                        mv -f → $STAGING_TAR
                        touch stamp
                        ↓
                        [PATH] piavpn-deploy.path fires
                        ↓
                        [SYS] piavpn-deploy.service
                             deploy script:
                               - PROTECTS /var/opt/piavpn/etc (credentials)
                               - wipes everything else under PIA_VAR_DIR
                               - re-extracts binaries + units + UI
                               - re-applies chmod/chown/setcap
                               - systemctl restart piavpn.service
                        ↓
                        VPN updated, credentials preserved
```

---

## Phase 4 — Offline boot (network down)

```text

t=0  Boot
     │  user logs in
     ▼
t=+1min 30sec   [TMR] fires
                │
                ├─ flock acquired
                │
                ├─ [USR] piavpn-extract.sh:
                │     curl -sfL --max-time 30 ... || true
                │       → timeout / DNS fail → empty RAW
                │     grep ... || true
                │       → empty LATEST_URL
                │
                ├─── CASE A: $VERSION_FILE exists (PIA already installed)
                │       echo "⚠️  Network unavailable; PIA already installed"
                │       DO NOT touch stamp
                │       exit 0
                │       → next boot retries cleanly
                │
                └─── CASE B: no $VERSION_FILE (genuine first install)
                        echo "❌ Error: no URL, no local install"
                        exit 1
                        → unit failed, visible in journal
                        → stamp still absent, next boot retries
```

---

## Phase 5 — Uninstall (rpm-ostree remove)

```text

┌─────────────────────────────────────────────────────────────────────┐
│ [PKG] rpm-ostree remove sirius-os-pia-installer                     │
│       ↓                                                             │
│       /usr/libexec/piavpn-deploy.sh        GONE                    │
│       /usr/libexec/piavpn-provision.sh     GONE                    │
│       /usr/libexec/piavpn-extract.sh       GONE                    │
│       /usr/share/sirius-os/pia/*           GONE                    │
│       vendor-layer symlinks for provisioners GONE                  │
│       ↓                                                             │
│       BUT: /etc/systemd/system/piavpn-deploy.service still exists   │
│            (provisioned on an earlier boot, lives in /etc)         │
│            → ConditionPathExists=/usr/libexec/piavpn-deploy.sh     │
│              now FALSE → skipped, not failed                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                            reboot
                              ↓
t=0  Boot
     │
     ├─ [SYS] piavpn-provision.service        → GONE (vendor layer)
     ├─ [SYS] pia-uninstall-provision.service → GONE (vendor layer)
     │
     ├─ [SYS] piavpn-deploy.service
     │       ConditionPathExists=/usr/libexec/piavpn-deploy.sh
     │       → FALSE → SKIPPED (the "not-found instead of failed" fix)
     │
     ├─ [SYS] piavpn-uninstall.service   ← STILL PRESENT from earlier
     │       ConditionPathExists=!/usr/libexec/piavpn-deploy.sh
     │       → TRUE → RUNS
     │       ExecStart=/etc/piavpn-uninstall/pia-uninstaller.sh
     │
     │       pia-uninstaller.sh:
     │         1. systemctl disable --now piavpn.service
     │         2. systemctl disable --now piavpn-deploy.path
     │         3. pkill -9 pia-daemon / pia-client / pia-unbound
     │         4. umount /opt/piavpn/etc/cgroup/net_cls
     │         5. rm -rf /var/opt/piavpn /opt/piavpn
     │         6. rm /etc/NetworkManager/conf.d/wgpia.conf
     │         7. rm desktop + pixmap + /usr/local/bin/pia*
     │         8. rm /etc/systemd/system/piavpn-deploy.{service,path}
     │            rm /etc/systemd/system/piavpn-provision.service
     │         9. rm multi-user.target.wants/piavpn-deploy.{path,service}
     │            rm ~/.config/systemd/user/timers.target.wants/
     │                  piavpn-extract.timer
     │        10. rm /etc/systemd/user/piavpn-extract.{service,timer}
     │        11. rm /etc/sirius-os/pia-provisioned
     │        12. rm /etc/systemd/system/piavpn-uninstall.service
     │            rm /etc/piavpn-uninstall/pia-uninstaller.sh
     │            rm multi-user.target.wants/piavpn-uninstall.service
     │        13. systemctl daemon-reload
     │
     └─ (no dangling units, no failed units, /etc clean)
```

---


## Full order-of-operations summary (single-line view)
```text

PKG LAYERING
  └─ files → /usr, two provisioner units symlinked ON
        │
        ▼
FIRST BOOT
  [SYS] piavpn-provision.service       ─ copies blueprints to /etc,
  │                                       arms timer + path,
  │                                       writes marker
  [SYS] pia-uninstall-provision.service ─ provisions dormant uninstaller
        │
        ▼ (user logs in)
  [TMR] +1m30s → piavpn-extract.timer
        │
        ▼
  [USR] piavpn-extract.sh
        ├─ stamp check        (skip if <7d)
        ├─ flock guard
        ├─ network check
        ├─ distrobox build
        └─ mv staging tar     ← handoff
        │
        ▼
  [PATH] piavpn-deploy.path  (detects staging tar)
        │
        ▼
  [SYS] piavpn-deploy.service
        └─ piavpn-deploy.sh → binaries, units, caps, permissions
        │
        ▼
  [SYS] piavpn.service → daemon up, VPN available

SUBSEQUENT BOOTS
  [SYS] provision.service       → skipped (marker exists)
  [SYS] uninstall-provision     → skipped (already provisioned)
  [TMR] +1m30s → extract
        └─ stamp < 7d → exit 0   (no network, no container)

BOOT ≥7 DAYS AFTER LAST CHECK
  [TMR] → extract → network check
        ├─ same version → touch stamp, exit
        └─ new version  → full relay again (deploy preserves etc/)

OFFLINE BOOT
  [TMR] → extract → curl fails
        ├─ version file exists → exit 0, stamp untouched, retry next boot
        └─ no version file     → exit 1 (genuine first-install failure)

UNINSTALL
  [PKG] remove → deploy script gone
        │ reboot
        ▼
  [SYS] deploy.service  → skipped (ConditionPathExists fails)
  [SYS] uninstall.service → runs full purge, removes itself last
```

---

## Timing Constants

| Constant | Value | Where | Why |
| --- | --- | --- | --- |
| `OnBootSec` | `1min 30sec` | `piavpn-extract.timer` | Past Bazzite's ~52s first-boot session teardown, with margin. Paid only on first install; post-stamp boots exit before the network. |
| `CHECK_INTERVAL` | `7 days` | `piavpn-extract.sh` | PIA releases every 3–5 months; 7 days is fresh enough and light enough to look like a normal user, not a scraper. |

---

## Guard Conditions

| Condition | Where | Effect |
| --- | --- | --- |
| `ConditionPathExists=!/etc/sirius-os/pia-provisioned` | `piavpn-provision.service` | Runs once ever; skips on every later boot. |
| `ConditionPathExists=/usr/libexec/piavpn-deploy.sh` | `piavpn-deploy.service` | Skips instead of failing on the boot after package removal. |
| `ConditionPathExists=!/etc/systemd/system/piavpn-uninstall.service` | `pia-uninstall-provision.service` | Provisions the dormant uninstaller only once. |


---

## Idempotency Layers

| Layer | Mechanism | Skips |
| --- | --- | --- |
| Boot-level | `ConditionPathExists` on the provisioner | Re-provisioning `/etc` on every boot. |
| Day-level | Stamp file: `~/.local/state/sirius-os/pia/.last-check` | Network fetches on boots within 7 days. |
| Version-level | `$VERSION_FILE` comparison | Container rebuilds when already current. |


The three layers are independent: the marker stops provisioning, the stamp stops the network round trip, and the version file stops the distrobox build. A boot can short-circuit at any of the three and still be correct.


