# PIA VPN Functional Testing Guide

A companion to the main testing guide. Where the first guide validates the package (does the pipeline run, does the deploy work, does the stamp cache behave correctly), this one validates the VPN itself — that PIA installed by this package actually functions as a VPN.
Table of Contents

## Overview

    **Prerequisites**

    Test 1 — Daemon & Client Health

    Test 2 — Connection Establishment

    Test 3 — Traffic Routing Through the Tunnel

    Test 4 — DNS Leak Check

    Test 5 — IPv6 Leak Check

    Test 6 — Kill Switch Behavior

    Test 7 — Reconnect After Network Change

    Test 8 — Credential Persistence Across Updates

    Test 9 — Firewall Interaction

    Test 10 — Performance Sanity Check

    Reference — PIA CLI Commands

    Reference — Where to Look When Things Break

## Overview

The Sirius-OS PIA Installer deploys PIA's official Linux client. It does not modify PIA's networking logic, DNS handling, kill switch, or WireGuard implementation. This guide tests the deployed installation against PIA's own expected behavior.

Scope of these tests:

    Confirm the daemon is running and healthy

    Confirm the client can connect to PIA servers

    Confirm traffic is routed through the tunnel

    Confirm DNS is resolved through PIA's resolver

    Confirm IPv6 is blocked or tunneled (no leaks)

    Confirm the kill switch prevents traffic when the tunnel drops

    Confirm credentials survive rebases and updates

    Confirm firewall coexistence (especially with sirius-os-virtualization)

Not in scope:

    Testing PIA's cryptographic correctness (trust the upstream client)

    Testing PIA's server selection algorithm

    Testing PIA's account/billing integration

Prerequisites

    PIA installed via sirius-os-pia-installer (i.e., /var/opt/piavpn exists, piavpn.service is running)

    Valid PIA account credentials

    A working network connection

    Terminal access as UID 1000 (for piactl commands) and root (for systemctl/journalctl)

Recommended baseline: run these tests before logging into PIA, and again after logging in, so you can see the state transitions. The first three tests don't require an account.

## Test 1 — Daemon & Client Health

Goal: Confirm the daemon is running, the client binary works, and the CLI can talk to the daemon.

Environment: Any.

Steps

```bash
# 1. Is the systemd service running?
systemctl status piavpn.service

# 2. Is the daemon process alive?
pgrep -a pia-daemon

# 3. Can the CLI reach the daemon?
piactl --version
piactl get connectionstate
piactl get vpnip

# 4. Check daemon logs for errors
sudo journalctl -u piavpn.service -b --no-pager | tail -40

# 5. Check the PIA var directory state
ls -la /var/opt/piavpn/etc/
sudo cat /var/opt/piavpn/etc/account.json 2>/dev/null | head -c 200
```

Expected Results

    piavpn.service: active (running) since boot or since deploy

    pia-daemon: process running from /var/opt/piavpn/bin/pia-daemon

    piactl --version: prints the PIA version (matches /var/opt/piavpn/share/version.txt)

    piactl get connectionstate: prints one of Disconnected, Connecting, Connected, Disconnecting, Interrupted

    piactl get vpnip: prints an IP (or empty if not connected)

    Journal: no error, fatal, or repeated warn lines

    /var/opt/piavpn/etc/ contains account.json, data.json, settings.json (data.json may be missing until first connect)

If It Fails

```bash
# Check capabilities on the daemon binary
getcap /var/opt/piavpn/bin/pia-daemon
# Expect: cap_net_admin,cap_net_raw,cap_sys_admin=ep

# Check group membership
getent group piavpn
ls -la /var/opt/piavpn/etc/

# Check SELinux denials
sudo ausearch -m avc -ts recent | grep piavpn | head -20
```

## Test 2a — Connection Establishment

Goal: Confirm the client can connect to a PIA server.

Environment: Any, with valid account.

```bash
## Logging In and Connecting

### One-time: log in via the GUI

Open the PIA GUI client and log in with your PIA username and
password. This writes the session token to
`/var/opt/piavpn/etc/account.json`, which `piactl` will use
automatically.

You do not need to run `piactl login` separately if you've logged
in via the GUI. `piactl` will report "Already logged into account
<username>" if you try.

### Ongoing: use the CLI

All subsequent operations work from a terminal without the GUI:

```bash
# 1. Confirm the daemon is up and you're logged in
piactl get connectionstate
# Expect: Disconnected (or Connected if already connected)

# 2. Set region to auto (nearest server)
piactl set region auto

# 3. Connect (skip if the GUI already connected you)
piactl connect

# 4. Watch the transition until it shows Connected
watch -n 1 'piactl get connectionstate; echo "---"; piactl get vpnip'
# Ctrl+C when connectionstate shows Connected

# 5. Confirm final state
piactl get connectionstate
# Expect: Connected

# 6. Get the assigned VPN IP
piactl get vpnip

# 7. Get the assigned region
piactl get region

# 8. Verify traffic is routed through PIA
curl -s https://ipinfo.io/json | python3 -m json.tool
# Look for:
#   "ip"     — should NOT be your real IP
#   "org"    — should be PIA or a PIA hosting provider, not your ISP
#   "city" — should be the exit location, not yours
```

Expected Results

    piactl login: no errors, prompts for credentials

    piactl get connectionstate: transitions from Disconnected → Connecting → Connected within 5–30 seconds

    piactl get vpnip: returns a non-local IP (not your LAN IP, not 127.0.0.1)

    piactl get region: returns a region name like UK London or US East

If It Fails

```bash
# Check what regions are available
piactl get regions | head -20

# Check for connection errors in the journal
sudo journalctl -u piavpn.service -b --no-pager | grep -iE 'error|fail|connect' | tail -20

# Check the daemon's network namespace
sudo lsns -t net | grep pia-daemon

# Verify the WireGuard interface exists
ip link show | grep -iE 'wg|pia'
```

## Test 3 — Traffic Routing Through the Tunnel

Goal: Confirm traffic actually exits through PIA, not through your ISP.

Environment: Any, connected to PIA.

```bash
# 1. Get your "public IP" as seen by the outside world
curl -s https://ipinfo.io/ip
# Note the IP and the org (ISP name)

# 2. Check PIA's claimed VPN IP
piactl get vpnip

# 3. The two should match, and the org should be PIA, not your ISP

curl -s https://ipinfo.io/json | python3 -m json.tool

# 4. Check the exit route
ip route get 1.1.1.1
# Should show the tunnel interface (wg0 or similar)

# 5. Trace a route
traceroute -n -m 5 1.1.1.1 2>/dev/null || tracepath -m 5 1.1.1.1
# First hop should be the PIA gateway, not your router

# 6. Disconnect
piactl disconnect

# 7. Re-check the public IP
curl -s https://ipinfo.io/ip
# Should now be your real IP

# 8. Reconnect for the remaining tests
piactl connect
```

Expected Results

    With VPN connected: curl ipinfo.io/ip returns the same IP as piactl get vpnip

    ipinfo.io/json org field shows PIA's hosting provider (often "Private Internet Access" or a datacenter name like "M247" or "DataCamp")

    ip route get 1.1.1.1 shows the VPN interface, not the default route

    traceroute first hop is on the PIA network (not 192.168.x.x)

    After disconnect: IP returns to your real ISP IP

If It Fails

```bash
# Check the routing table
ip route
ip rule list

# Check for policy-based routing rules PIA uses
ip route show table all | grep -iE 'pia|wg|1[0-9]{3}'

# Check the wgpia interface config
cat /etc/NetworkManager/conf.d/wgpia.conf
nmcli connection show | grep -i pia
```

### Test 4 — Disconnect/Reconnect Verification

**Goal:** Confirm the VPN routes traffic when connected and reverts
to the ISP when disconnected.

```bash
# 1. With VPN disconnected, capture the real IP
piactl disconnect
sleep 3
curl -s https://ipinfo.io/json | python3 -m json.ool > /tmp/no-vpn.json
cat /tmp/no-vpn.json

# 2. Connect and capture the VPN IP
piactl connect
sleep 15
piactl get connectionstate  # Expect: Connected
curl -s https://ipinfo.io/json | python3 -m json.tool > /tmp/with-vpn.json
cat /tmp/with-vpn.json

# 3. Compare
echo "=== Without VPN ==="
grep -E '"ip"|"org"' /tmp/no-vpn.json
echo ""
echo "=== With VPN ==="
grep -E '"ip"|"org"' /tmp/with-vpn.json

# 4. Clean up
rm -f /tmp/no-vpn.json /tmp/with-vpn.json
```

## Test 5 — DNS Leak Check

Goal: Confirm DNS queries go through PIA's resolver, not your ISP.

Environment: Any, connected to PIA.

```bash
# 1. Check which DNS server is in use
resolvectl status | grep -A2 'Current DNS'

# 2. Query a DNS resolver identification service
dig +short whoami.akamai.net @resolver1.opendns.com

# Expected communications error to 208.67.222.222#53: connection refused

# Or use a web-based check:
curl -s https://www.dnsleaktest.com/ -o /dev/null  # opens in browser normally

# 3. Query via PIA's resolver directly
dig +short @10.0.0.242 example.com 2>/dev/null || \
dig +short @10.0.0.243 example.com 2>/dev/null
# PIA typically uses 10.0.0.242/243 as in-tunnel DNS

# 4. Do a leak test in a browser
# Open https://www.dnsleaktest.com/ and run the extended test
```

### Expected Results

- `resolvectl status` shows the `wgpia0` interface with:
- `Current DNS Server: 10.0.0.243` (or `.242`)
- `DNS Domain: ~.` — this is the **catch-all**, meaning all
   queries not matched by a more specific domain go here
- `+DefaultRoute` and `Default Route: yes`

- The physical interface (`enpXsY` or `wlpXsY`) may also show
  a `Default Route: yes` with your router's DNS (`192.168.x.1`).
  This is not a conflict — the `~.` on `wgpia0` wins for all
  public DNS. The router is only used for link-local names.

- `dig +short @10.0.0.243 example.com` returns real IPs

- `dig +short @8.8.8.8 example.com` or `@resolver1.opendns.com`
  fails with "connection refused" or "no servers could be reached"
  (kill switch blocks external DNS)

- `ps aux | grep pia-unbound` shows no PIA unbound process
  (current PIA doesn't run a local resolver; kernel `kworker`
  threads named `*_unbound` are unrelated)

If It Fails

```bash
# Check what's listening on port 53
sudo ss -tulnp | grep ':53'

# Check unbound's status
systemctl status pia-unbound 2>&1 || \
ps aux | grep -i unbound

# Verify resolvectl is using the PIA DNS
resolvectl status

# Check NetworkManager's DNS handling
nmcli device show | grep -i dns
```

Important: If sirius-os-virtualization is installed, libvirt may be running its own DNS resolver on virbr0 (typically 192.168.122.1). This is expected and doesn't leak host DNS — it's a bridge-local resolver for VMs. Don't confuse it with a leak.

---


## Test 6 — IPv6 Leak Check

Goal: Confirm IPv6 traffic isn't bypassing the tunnel.

Environment: Any, connected to PIA.

Steps

```bash
# 1. Check if IPv6 is enabled on your system
ip -6 addr show scope global
sysctl net.ipv6.conf.all.disable_ipv6

# 2. Attempt an IPv6 connection
curl -6 -s --max-time 5 https://ipv6.google.com 2>&1
curl -6 -s --max-time 5 https://ipinfo.io/ip 2>&1

# 3. Browser check
# Open https://test-ipv6.com/ or https://ipv6-test.com/
```
Expected Results

Depending on your system's IPv6 configuration:

If IPv6 is disabled on the host:

    ip -6 addr show scope global shows no global addresses

    curl -6 fails with "Network is unreachable"

    No IPv6 leak possible

If IPv6 is enabled on the host:

    PIA's client should route IPv6 through the tunnel (if your region supports it) OR block it

    Browser test shows no IPv6 address, or an IPv6 address from PIA

    Never shows your real ISP's IPv6 address while the VPN is connected

If It Fails

```bash
# Check the IPv6 routing table
ip -6 route

# Check if PIA is managing IPv6
piactl get allowlan
piactl get requestportforward

# Force-disable IPv6 if PIA doesn't handle it
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
```

Note: IPv6 handling varies by PIA region. Some servers support IPv6 tunneling, others don't and rely on the kill switch to block it. If IPv6 is disabled on the host, there's no leak vector.

---

## Test 7 — Kill Switch Behavior

Goal: Confirm that if the tunnel drops, traffic is blocked (not leaked through your ISP).

Environment: Any, connected to PIA.

Steps

```bash
# 1. Confirm connected
piactl get connectionstate
# Expect: Connected

# 2. Start a long-running ping in the background
ping 1.1.1.1 > /tmp/ping.log 2>&1 &
PING_PID=$!
echo "Ping PID: $PING_PID"

# 3. Verify the ping is succeeding through the tunnel
sleep 2
tail -3 /tmp/ping.log
# Should show successful replies

# 4. Simulate a tunnel drop by killing the daemon
# WARNING: this is disruptive; do it in a test environment
sudo systemctl stop piavpn.service

# 5. Watch the ping
sleep 5
tail -10 /tmp/ping.log
# Should show either:
#   (a) "Destination Net Unreachable" / timeouts — kill switch blocked
#   (b) continued replies — kill switch NOT working, LEAK

# 6. Restore the daemon
sudo systemctl start piavpn.service
sleep 5
piactl get connectionstate

# 7. Clean up
kill $PING_PID 2>/dev/null
rm -f /tmp/ping.log
```
Expected Results

    Before daemon stop: ping succeeds

    After daemon stop: ping fails (kill switch engaged)

    After daemon restart: PIA reconnects automatically (depending on settings), ping succeeds again

If It Fails

If the ping continues after the daemon stops, the kill switch is not working. Check:

```bash
# Is the kill switch enabled?
piactl get killswitch

# Is PIA managing firewall rules?
sudo nft list ruleset | grep -i pia
sudo iptables -L -n | grep -i pia

# Check PIA's firewall integration config
cat /var/opt/piavpn/etc/settings.json | python3 -m json.tool | grep -i kill
```
Note: This test is destructive on the host it runs on. Run it on a test VM, not a machine you're actively using. Killing piavpn.service while connected will drop your VPN and the kill switch will (correctly) block traffic — your current SSH session or browser will freeze until the daemon restarts.

---

## Test 8 — Reconnect After Network Change

**Goal:** Confirm PIA reconnects automatically when the network
drops and comes back.

**Environment:** Any, connected to PIA.

### Steps

```bash
# 1. Confirm starting state
piactl connect
sleep 5
piactl get connectionstate
# Expect: Connected

# 2. Disable networking
nmcli networking off

# 3. Wait for PIA to notice (may take 5-30 seconds)
sleep 10
piactl get connectionstate
# Expect: Reconnecting (or still Connected if PIA hasn't
# noticed yet — WireGuard is connectionless, so the tunnel
# "breaks" lazily)

# 4. Restore networking
nmcli networking on

# 5. Wait for reconnect
sleep 15
piactl get connectionstate
# Expect: Connected

# 6. Verify traffic flows through the VPN again
curl -s --max-time 5 https://ipinfo.io/ip
# Should return a PIA IP, not fail
```

---

## Test 9 — Credential Persistence Across Updates

Goal: Confirm credentials and settings survive a rebase, upgrade, or reinstall of the package.

Environment: Any, with valid PIA account and connected VPN.

Steps

```bash
## Test 8 — Credential Persistence Across Updates

**Goal:** Confirm credentials and settings survive a rebase, upgrade,
or reinstall of the package.

**Environment:** Any, with valid PIA account and connected VPN.

### Steps

```bash
# 1. Confirm connected and logged in
piactl get connectionstate
# Expect: Connected

# 2. Note the account.json contents (login indicator)
sudo cat /var/opt/piavpn/etc/account.json | head -c 100
echo ""
# Expect: JSON with "active":true, "expirationTime":<future>

# 3. Note the connection state and region
piactl get region
# Expect: auto or a specific region name

# 4. Simulate an update by removing and reinstalling the package
# WARNING: this drops the VPN temporarily
sudo rpm-ostree remove sirius-os-pia-installer
sudo systemctl reboot

# 5. After reboot, the dormant uninstaller runs and cleans up.
# Wait for it to complete, then verify:
ls -la /etc/systemd/system/piavpn-uninstall.service 2>&1
# Expect: "No such file or directory" (uninstaller removed itself)

ls -la /var/opt/piavpn 2>&1
# Expect: "No such file or directory" (PIA data removed)

# 6. Reinstall the package
sudo rpm-ostree install /path/to/sirius-os-pia-installer-*.rpm
sudo systemctl reboot

# 7. Wait for the pipeline to rebuild (2-5 minutes after login)
# Then check the credentials
ls -la /var/opt/piavpn/etc/account.json
# Expect: file exists, owned root:piavpn, mode 600

sudo cat /var/opt/piavpn/etc/account.json | head -c 100
echo ""
# Expect: JSON content — but it may be empty or missing account data
# because the uninstaller deleted /var/opt/piavpn

# 8. Verify the client state
piactl get connectionstate
# Expect: Disconnected

piactl connect
sleep 15
piactl get connectionstate
# Expect: Connected (or prompts for login if credentials were lost)
```

Expected Results

Important: The dormant uninstaller removes /var/opt/piavpn
entirely, including account.json. So credentials are NOT
preserved across a remove + reinstall cycle. This is documented
behavior in the README.

What is preserved:

    Across a rebase (Silverblue → Bazzite, or version upgrade
    without removal): credentials survive because /var/opt/piavpn
    isn't touched.

    Across a package upgrade (2.0.0-5 → 2.0.0-6 without removal):
    same.

What is not preserved:

    Across a remove + reinstall: the uninstaller deletes
    /var/opt/piavpn, including credentials.

After a reinstall, you will need to log in again via the GUI, or
via piactl login <file>.

If You Want to Preserve Credentials Across Reinstall

You'd need to change the uninstaller to keep /var/opt/piavpn/etc/. That's a design decision — the current behavior is intentional (clean removal means clean removal). 

---

## Test Variant — Rebase

```bash
# On Silverblue, rebase to a different ref (e.g., different Fedora version)
sudo rpm-ostree rebase fedora:fedora/44/x86_64/silverblue
sudo systemctl reboot

# After reboot, check credentials survived
cat /var/opt/piavpn/etc/account.json | head -c 100
piactl get connectionstate
```

Expected Results

    Credentials survive

    PIA reconnects (or can be manually connected with piactl connect)

    The version file and binaries are still present

---

## Test 9 — Firewall Interaction

Goal: Confirm PIA coexists with firewalld and (optionally) libvirt.

Environment: Any.

Steps

```bash
# 1. Check firewalld status
systemctl status firewalld
sudo firewall-cmd --state
sudo firewall-cmd --get-default-zone
sudo firewall-cmd --list-all

# 2. Connect to PIA
piactl connect

# 3. Re-check firewalld
sudo firewall-cmd --list-all
# PIA may add rules to the default zone or create a dedicated zone

# 4. Check for libvirt's zone (if sirius-os-virtualization is installed)
sudo firewall-cmd --get-active-zones
sudo firewall-cmd --zone=libvirt --list-all

# 5. Verify VMs still have DHCP if virt is installed
# (Run in a VM hosted on this machine)
# ping 192.168.122.1
# sudo dhclient -v
```

Expected Results

    firewalld: active (running)

    PIA's rules are in a dedicated zone or the default zone (specifics depend on PIA's client)

    libvirt zone exists and virbr0 is bound to it

    VMs on this host still get DHCP and can reach the internet

If It Fails

If VMs lost DHCP after PIA was installed, the kill switch may have flushed firewall rules. This was the exact bug fixed in 2.0.0-4 (the nft flush ruleset line that also cleared firewalld's rules). Verify you're on 2.0.0-4 or later:

```bash
rpm -q sirius-os-pia-installer
# Expect: 2.0.0-4 or higher

# Check the libvirt zone binding
sudo firewall-cmd --zone=libvirt --list-all
# Should show virbr0 in interfaces

# If missing, restore it
sudo firewall-cmd --zone=libvirt --add-interface=virbr0
sudo firewall-cmd --zone=libvirt --add-interface=virbr0 --permanent
```

### Note on the firewalld zone target

If you have sirius-os-virtualization installed and you use VMs,
check the libvirt zone target:

```bash
firewall-cmd --info-zone=libvirt | grep target
# Expect: target: ACCEPT
```
---

## Test 10 — Performance Sanity Check

**Goal:** Confirm the VPN doesn't introduce pathological latency
or throughput loss.

**Environment:** Any, connected to PIA.

### Steps

```bash
# 1. Baseline: disconnect from PIA
piactl disconnect
sleep 3

# 2. Measure latency and bandwidth without VPN
echo "=== Without VPN ==="
ping -c 10 1.1.1.1 | tail -3
speedtest-cli --simple 2>/dev/null || \
    curl -o /dev/null -s -w 'Download: %{speed_download} bytes/s\n' \
    https://speed.cloudflare.com/__down?bytes=10000000

# 3. Connect to PIA
piactl connect
sleep 5
piactl get connectionstate
# Expect: Connected

# 4. Measure latency and bandwidth with VPN
echo "=== With VPN ==="
ping -c 10 1.1.1.1 | tail -3
speedtest-cli --simple 2>/dev/null || \
    curl -o /dev/null -s -w 'Download: %{speed_download} bytes/s\n' \
    https://speed.cloudflare.com/__down?bytes=10000000
```

Expected Results

    Latency: typically 20–80 ms higher with VPN, depending on server distance

    Throughput: typically 30–70% of baseline, depending on server load and protocol

    No packet loss (or minimal)

Expected Results

WireGuard typically adds minimal overhead:

    Latency: 5–50 ms higher, depending on server distance.
    Occasionally lower if PIA's route is more direct than your
    ISP's (see note below).

    Throughput: 70–100% of baseline. Overhead comes from
    encryption, encapsulation, and the extra network hop.

    Packet loss: 0% (any loss indicates a problem)

The exact numbers depend on your ISP, the PIA server, and your distance to it. The point of this test is to confirm the VPN isn't introducing pathological degradation (e.g., <1 Mbps, or >500 ms latency).


If It Fails

```bash
# Try a different region
piactl set region "US East"
piactl disconnect
piactl connect

# Try a different protocol (if configurable)
piactl get protocol
# OpenVPN vs WireGuard may perform differently

# Check for CPU saturation on the daemon
top -p $(pgrep pia-daemon)
```

## Reference — PIA CLI Commands

Quick reference for the commands used in these tests.

### Connection

| Command | Description |
|---|---|
| `piactl connect` | Connect to the current region |
| `piactl disconnect` | Disconnect from the VPN |
| `piactl get connectionstate` | Display the connection state: `Disconnected`, `Connecting`, `Connected`, or `Interrupted` |
| `piactl get vpnip` | Display the IP address assigned by PIA |
| `piactl get region` | Display the current region |
| `piactl set region "US East"` | Set the current region |
| `piactl get regions` | List all available regions |

### Account

| Command | Description |
|---|---|
| `piactl login` | Prompt for account credentials |
| `piactl logout` | Log out of the PIA account |

### Settings

| Command | Description |
|---|---|
| `piactl background enable/disable` | Set killswitch enabled or disabled |
| `piactl get allowlan` | Display whether local network access is enabled or disabled |
| `piactl get protocol` | Display the VPN protocol currently in use |
| `piactl get requestportforward` | Display whether port forwarding is enabled or disabled |


### Debugging

| Command | Description |
|---|---|
| `piactl monitor connectionstate` | Continuously display VPN connection-state changes |
| `piactl monitor vpnip` | Continuously display VPN IP-address changes |
| `piactl --version` | Display the installed PIA client version |
| `piactl --help` | Display the complete command list |


### Location

| Path | Description |
|---|---|
| `/usr/local/bin/piactl` | Symlink to `/var/opt/piavpn/bin/piactl` |
| `/var/opt/piavpn/bin/piactl` | Actual `piactl` binary |


Reference — Where to Look When Things Break
Service Logs

```bash
# The PIA daemon
sudo journalctl -u piavpn.service -b --no-pager | tail -50

# The unbound DNS resolver (if it has its own unit)
systemctl status pia-unbound 2>&1
sudo journalctl -u pia-unbound -b --no-pager | tail -30

# NetworkManager events
sudo journalctl -u NetworkManager -b --no-pager | tail -50
```
### Files

```bash
# Account and settings (private, root-owned, group piavpn)
sudo cat /var/opt/piavpn/etc/account.json
sudo cat /var/opt/piavpn/etc/settings.json
sudo cat /var/opt/piavpn/etc/data.json

# Version info
cat /var/opt/piavpn/share/version.txt

# Binaries (with capabilities)
getcap /var/opt/piavpn/bin/pia-daemon
getcap /var/opt/piavpn/bin/pia-unbound

# Network config from PIA's installer
cat /etc/NetworkManager/conf.d/wgpia.conf
```

### Network State

```bash
# Interfaces
ip -br addr
ip link show | grep -iE 'wg|pia|tun'

# Routes
ip route
ip -6 route
ip rule list

# DNS
resolvectl status
cat /etc/resolv.conf

# Firewall
sudo firewall-cmd --list-all
sudo nft list ruleset | head -50

# Sockets
sudo ss -tulnp | grep -iE 'pia|unbound|:53'

# Which process opened which connection
sudo ss -tunp | grep pia-daemon
```

Process State

```bash
# What PIA processes are running
ps auxf | grep -iE 'pia|unbound' | grep -v grep

# What the daemon is doing
sudo strace -f -p $(pgrep pia-daemon) -e trace=network 2>&1 | head -50

# What's in the daemon's cgroup
systemd-cgls /system.slice/piavpn.service
```

## Common Failure Signatures

| Symptom | Likely Cause | Where to Look |
|---|---|---|
| `piactl get connectionstate` hangs | The PIA daemon is not running. | `systemctl status piavpn.service` |
| `piactl` reports `Cannot connect to daemon` | Required capabilities are missing from the daemon. | `getcap /var/opt/piavpn/bin/pia-daemon` |
| VPN connects, but there is no traffic | The routing table was not configured correctly. | `ip route`<br>`ip rule list` |
| DNS fails while connected | `unbound` is not running or is not bound to port 53. | `ss -tulnp \| grep :53`<br>`getcap /var/opt/piavpn/bin/pia-unbound` |
| VPN IP matches the real IP | The VPN tunnel did not establish correctly. | `ip link show`<br>`journalctl -u piavpn.service` |
| VPN drops after a network change | Automatic reconnection is disabled. | `piactl get autoreconnect` |
| Virtual machines lose DHCP after PIA installation | The kill switch flushed the `firewalld` rules for the `libvirt` zone. | `firewall-cmd --zone=libvirt --list-all` |
| Service fails to start after an update | A file is missing from the archive, or deployment did not run. | `journalctl -u piavpn-deploy.service` |


## Test Matrix Summary

| Test | Requires Account | Disruptive | Estimated Time |
|---|---:|---|---:|
| **1 — Daemon Health** | No | No | ~2 minutes |
| **2 — Connection** | Yes | No | ~3 minutes |
| **3 — Traffic Routing** | Yes | No | ~3 minutes |
| **4 — DNS Leak** | Yes | No | ~3 minutes |
| **5 — IPv6 Leak** | Yes | No | ~2 minutes |
| **6 — Kill Switch** | Yes | Yes — drops the VPN connection | ~5 minutes |
| **7 — Reconnect** | Yes | No | ~5 minutes |
| **8 — Credential Persistence** | Yes | Yes — removes PIA | ~15 minutes |
| **9 — Firewall Interaction** | No | No | ~3 minutes |
| **10 — Performance** | Yes | No | ~5 minutes |


## Correct leak test

```bash
### From the terminal — should show the VPN IP
curl -s https://ifconfig.me
curl -s https://api.ipify.org

# Compare to PIA's own report
piactl get vpnip
```

Typical validation sequence:

    Tests 1, 9 on a fresh install (no account needed)

    Log in to PIA

    Tests 2, 3, 4, 5 (basic functionality)

    Test 7 (network resilience)

    Test 6 (kill switch — do this last, it's disruptive)

    Test 8 (credential persistence — only when testing updates/reinstalls)

    Test 10 (performance — optional, only if you want to compare)

## sirius-os-virtualization
    
**Changing the libvirt firewalld zone target breaks VM connectivity.**

If `/etc/firewalld/zones/libvirt.xml` has been customized with
`<zone target="default">` (or `REJECT`) instead of `ACCEPT`, VM
traffic stops being forwarded once PIA's rules take effect. VMs
lose DHCP and internet access until PIA is stopped.

Restore the stock zone:

```bash
sudo rm -f /etc/firewalld/zones/libvirt.xml
sudo firewall-cmd --reload
firewall-cmd --info-zone=libvirt | grep target
# Expect: target: ACCEPT
```

The sirius-os-virtualization package installs the correct zone on
first provisioning. This only applies if the zone was modified after
install.

End of PIA functional testing guide.
