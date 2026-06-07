# Pi 3 VPN (WireGuard)

Personal VPN server on a **Raspberry Pi 3** — connect your phone or laptop to your home network from anywhere.

Uses **WireGuard** (lightweight, fast, ideal for Pi 3).

## What you get

- Encrypted tunnel from phone/laptop → home Pi
- Browse as if you're on your home network
- Works on public Wi‑Fi, mobile data, travel
- Learn how VPNs actually work (keys, peers, routing, port forwarding)

## What you need

| Item | Notes |
|---|---|
| **Raspberry Pi 3** | Any variant (B/B+) |
| **MicroSD** | Raspberry Pi OS Lite 64-bit or 32-bit |
| **Power supply** | Official Pi PSU recommended |
| **Ethernet** | Preferred for the Pi (always-on server) — Wi‑Fi works too |
| **Router access** | To forward **UDP 51820** to the Pi |
| **Public IP or DDNS** | So your phone can find home when you're out |

Optional: [DuckDNS](https://www.duckdns.org/) free hostname if your home IP changes.

## Quick start on the Pi

```bash
git clone https://github.com/Daniel280712/my-first-ai-app.git
cd my-first-ai-app/pi-vpn

# 1. Install server
sudo ./scripts/install-wireguard.sh

# 2. Add your Pixel 5 as a client (set your public IP or DDNS)
sudo ENDPOINT=yourname.duckdns.org:51820 ./scripts/add-client.sh pixel5

# 3. Scan the QR code with the WireGuard app on your phone
```

## Router setup

1. Give the Pi a **fixed LAN IP** (DHCP reservation in router admin).
2. **Port forward:** external UDP **51820** → Pi LAN IP **51820**.
3. Test from mobile data (not home Wi‑Fi) — turn VPN on, visit [ifconfig.me](https://ifconfig.me) and check your IP.

## Phone setup (Pixel 5)

1. Install **WireGuard** from Google Play.
2. Tap **+** → **Scan from QR code** (shown when you run `add-client.sh`).
3. Toggle the tunnel on when you're away from home.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/install-wireguard.sh` | Install WireGuard, enable routing/NAT on Pi |
| `scripts/add-client.sh` | Create client config + QR for a device |
| `scripts/status.sh` | Check interface, forwarding, clients |

## How it works (learning)

```
Phone (10.8.0.2)  --encrypted UDP-->  Pi (10.8.0.1)  --NAT-->  Internet / home LAN
```

1. **Keys** — server and each client have a key pair; peers trust public keys.
2. **Tunnel** — traffic inside UDP 51820 between phone and Pi.
3. **Routing** — Pi forwards traffic out your home connection (`MASQUERADE`).
4. **Port forward** — router sends inbound 51820 to the Pi so you're reachable from outside.

## Troubleshooting

| Problem | Check |
|---|---|
| Can't connect from outside | Port forward, DDNS, Pi firewall (`sudo ufw allow 51820/udp`) |
| Connects but no internet | IP forwarding enabled? Run `status.sh` |
| Works on Wi‑Fi not mobile data | You're probably still on home network — test on 4G/5G |
| Slow on Pi 3 | Normal for Pi 3 — fine for personal use, not 4K streaming |

## Security notes

- Keep the Pi updated: `sudo apt update && sudo apt upgrade`
- Don't share client `.conf` files — they contain private keys
- One `.conf` per device; revoke by removing the `[Peer]` block from `wg0.conf`

## Pipeline / what's next

- [ ] DuckDNS auto-update script on the Pi
- [ ] Split tunnel option (home LAN only vs full VPN)
- [ ] Optional: combine with Nav/LTE lab on the same Pi later
