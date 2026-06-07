# Pi GNSS / LTE Lab

Learn **GPS navigation** and **LTE cell signal** on a **Raspberry Pi 3**, then **track it live on your phone** (Pixel 5) like an app.

## What it does

| Piece | Role |
|---|---|
| **USB GPS on Pi** | Real satellite fixes via `gpsd` |
| **USB LTE modem** (optional) | Signal strength (RSRP/RSRQ) via `mmcli` |
| **Web app on Pi** | Live map, **online routing**, turn-by-turn |
| **Your phone** | Open in browser → **Add to Home screen** = nav app |

### Real-time navigation

- **Maps** — **Google Maps** tiles (with your API key) or OpenStreetMap fallback
- **Your pointer** — custom icon on top of the map, driven by Pi GPS (rotates with heading)
- **Search** — address/place lookup (Nominatim)
- **Routing** — driving / walking / cycling (OSRM)
- **Live** — Pi GPS updates your pointer; map follows you; reroutes if you go off course
- **Layer toggles** — strip back map tiles, route, track, pointer, or destination pin
- **Raw panel** — live parsed GNSS/LTE + raw gpsd JSON for learning and diagnosis

### Google Maps API key (optional)

1. Create a key in [Google Cloud Console](https://console.cloud.google.com/) with **Maps JavaScript API** enabled
2. On the Pi: `sudo nano /etc/gnss-lte-lab.env`
3. Set `GOOGLE_MAPS_API_KEY="your-key-here"`
4. `sudo systemctl restart pi-gnss-lte-lab`

Without a key, the app uses OpenStreetMap tiles — routing still works.

```
Satellites → USB GPS → Pi (gpsd) → map API → phone browser/PWA
Cell tower → USB LTE → Pi (mmcli) → metrics panel
```

Works **before hardware arrives** too — demo track plays on the map.

## Hardware

### Required (GPS)
| Item | Cost (approx) |
|---|---|
| Raspberry Pi 3 + SD + power | you have |
| **USB GPS** (u-blox) | £12–25 |

### Optional (LTE learning)
| Item | Cost (approx) |
|---|---|
| USB 4G LTE dongle + data SIM | £20–40 |

## Install on the Pi

```bash
git clone https://github.com/Daniel280712/my-first-ai-app.git
cd my-first-ai-app/pi-gnss-lte
sudo ./scripts/install.sh
```

Open on your phone (same Wi‑Fi):

**`http://<pi-ip>:8090`**

### Install as phone “app” (PWA)

1. Open the URL in **Chrome** on your Pixel  
2. **⋮** menu → **Install app** or **Add to Home screen**  
3. Tap **Live** — map updates every few seconds when GPS has a fix  

## Modes

| Mode | When |
|---|---|
| **Live** | GPS plugged in, Pi logging position |
| **Demo** | No GPS yet — sample track for learning |
| **No fix** | GPS connected but no sky view (indoors) — move near window |

## What you learn

- How a **GNSS fix** appears (lat/lon, speed, HDOP, satellites)
- Why fixes fail indoors / urban canyons
- **LTE metrics** vs **GPS** — separate systems (like car shark-fin antenna)
- Live tracking architecture (collector → API → map)

## Optional LTE setup

```bash
sudo apt install modemmanager
# plug USB modem + SIM, then check:
mmcli -L
```

## Requirements for routing

- **Pi must have internet** (Ethernet/Wi‑Fi) for map tiles + routing APIs
- **Phone on same network** as Pi (or VPN into home later)
- **GPS fix** outdoors / near window for live position

Routing uses free OSRM + Nominatim services — fine for personal lab use; don't hammer them with massive traffic.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/live` | Current GPS + LTE snapshot |
| `GET /api/track` | Logged track points |
| `GET /api/geocode?q=` | Search for a destination |
| `POST /api/route` | Turn-by-turn route between two points |
| `GET /api/demo` | Sample track |

## Next steps

- [ ] Drive/walk test — log a route, replay on map
- [ ] LTE vs GPS comparison chart over time
- [ ] Export GPX from logged track
- [ ] Run on same Pi as ad-blocker (separate ports)
