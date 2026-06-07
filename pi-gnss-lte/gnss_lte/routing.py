"""Online geocoding + routing (proxied through the Pi for CORS and API keys)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "PiGnssLteLab/1.0 (personal navigation lab)"
OSRM_BASE = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
NOMINATIM_BASE = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")


def _get(url: str, timeout: float = 15.0) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Routing service error ({exc.code}): {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error — is the Pi online? {exc}") from exc


def geocode(query: str, limit: int = 5) -> list[dict]:
    if not query.strip():
        return []
    params = urllib.parse.urlencode({"q": query.strip(), "format": "json", "limit": limit})
    results = _get(f"{NOMINATIM_BASE}/search?{params}")
    return [
        {
            "label": row.get("display_name", ""),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
        }
        for row in results
        if "lat" in row and "lon" in row
    ]


def _instruction(step: dict) -> str:
    maneuver = step.get("maneuver", {})
    if maneuver.get("instruction"):
        return maneuver["instruction"]
    mtype = maneuver.get("type", "continue")
    modifier = maneuver.get("modifier", "")
    name = step.get("name") or "the road"
    parts = [mtype.replace("_", " ")]
    if modifier:
        parts.append(modifier.replace("_", " "))
    parts.append(name)
    return " ".join(parts).capitalize()


def route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    profile: str = "driving",
) -> dict:
    if profile not in {"driving", "foot", "bike"}:
        profile = "driving"

    coords = f"{from_lon},{from_lat};{to_lon},{to_lat}"
    params = urllib.parse.urlencode(
        {"overview": "full", "geometries": "geojson", "steps": "true", "annotations": "false"}
    )
    url = f"{OSRM_BASE}/route/v1/{profile}/{coords}?{params}"
    data = _get(url)

    if data.get("code") != "Ok" or not data.get("routes"):
        message = data.get("message", "No route found")
        raise RuntimeError(message)

    best = data["routes"][0]
    geometry = best["geometry"]["coordinates"]
    latlngs = [[pt[1], pt[0]] for pt in geometry]

    steps = []
    for leg in best.get("legs", []):
        for step in leg.get("steps", []):
            loc = step.get("maneuver", {}).get("location", [from_lon, from_lat])
            steps.append(
                {
                    "instruction": _instruction(step),
                    "distance_m": round(step.get("distance", 0)),
                    "duration_s": round(step.get("duration", 0)),
                    "lat": loc[1],
                    "lon": loc[0],
                }
            )

    return {
        "profile": profile,
        "distance_m": round(best.get("distance", 0)),
        "duration_s": round(best.get("duration", 0)),
        "geometry": latlngs,
        "steps": steps,
        "start": {"lat": from_lat, "lon": from_lon},
        "end": {"lat": to_lat, "lon": to_lon},
    }
