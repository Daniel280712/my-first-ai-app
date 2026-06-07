# my-first-ai-app

Personal projects lab — currently: **Pi 3 VPN**.

## Active project: WireGuard on Raspberry Pi 3

Run your own VPN at home. Connect your phone (Pixel 5) or laptop when you're out.

**Start here:** [pi-vpn/README.md](pi-vpn/README.md)

```bash
cd pi-vpn
sudo ./scripts/install-wireguard.sh
sudo ENDPOINT=yourname.duckdns.org:51820 ./scripts/add-client.sh pixel5
```

## Platform

- **Raspberry Pi 3** — always-on home server
- **WireGuard** — lightweight VPN (better than OpenVPN on Pi 3)

## Other ideas (parked)

- Nav/LTE learning lab (GPS + cell signal — can live on the same Pi later)
- WK2 garage log (parked — car has service counter)
