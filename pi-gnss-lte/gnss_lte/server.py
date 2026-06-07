"""GNSS/LTE lab — live map + metrics for phone browser / PWA."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gnss_lte import gps, lte, storage

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
SAMPLE = ROOT / "sample_data" / "demo_track.json"

app = FastAPI(title="Pi GNSS/LTE Lab")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_latest: dict = {"mode": "waiting", "gps": None, "sky": None, "lte": None}
_last_log_at: float = 0.0


def _load_demo_track() -> list[dict]:
    if SAMPLE.exists():
        return json.loads(SAMPLE.read_text(encoding="utf-8"))
    return []


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/live")
def live_snapshot() -> dict:
    fix = gps.read_gpsd()
    sky = gps.read_gpsd_status()
    cell = lte.read_lte()

    has_fix = fix.lat is not None and fix.lon is not None
    payload = {
        "mode": "live" if has_fix else "no_fix",
        "gps": fix.__dict__,
        "sky": sky,
        "lte": cell,
    }
    global _latest
    _latest = payload

    if has_fix:
        global _last_log_at
        now = time.time()
        if now - _last_log_at >= 10:
            _last_log_at = now
            storage.append_snapshot(
                {
                    "lat": fix.lat,
                    "lon": fix.lon,
                    "altitude_m": fix.altitude_m,
                    "speed_mps": fix.speed_mps,
                    "track_deg": fix.track_deg,
                    "satellites_used": sky.get("satellites_used"),
                    "hdop": sky.get("hdop"),
                    "lte": cell if cell.get("available") else None,
                    "timestamp": fix.timestamp,
                }
            )
    return payload


@app.get("/api/track")
def track(limit: int = Query(default=300, le=2000)) -> dict:
    points = storage.read_track(limit)
    if points:
        return {"mode": "logged", "points": points}
    return {"mode": "demo", "points": _load_demo_track()}


@app.get("/api/demo")
def demo() -> dict:
    return {"mode": "demo", "points": _load_demo_track()}
