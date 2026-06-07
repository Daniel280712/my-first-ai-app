"""GNSS/LTE lab — live map + metrics for phone browser / PWA."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gnss_lte import config, gps, lte, routing, storage

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


def _build_live_payload() -> dict:
    fix = gps.read_gpsd()
    sky = gps.read_gpsd_status()
    cell = lte.read_lte()
    has_fix = fix.lat is not None and fix.lon is not None
    return {
        "mode": "live" if has_fix else "no_fix",
        "gps": asdict(fix),
        "sky": sky,
        "lte": cell,
        "polled_at": datetime.now(timezone.utc).isoformat(),
    }


def _maybe_log_fix(payload: dict) -> None:
    fix = payload["gps"]
    if payload["mode"] != "live":
        return
    global _last_log_at
    now = time.time()
    if now - _last_log_at < 10:
        return
    _last_log_at = now
    cell = payload["lte"]
    storage.append_snapshot(
        {
            "lat": fix["lat"],
            "lon": fix["lon"],
            "altitude_m": fix.get("altitude_m"),
            "speed_mps": fix.get("speed_mps"),
            "track_deg": fix.get("track_deg"),
            "satellites_used": payload["sky"].get("satellites_used"),
            "hdop": payload["sky"].get("hdop"),
            "lte": cell if cell.get("available") else None,
            "timestamp": fix["timestamp"],
        }
    )


@app.get("/api/live")
def live_snapshot() -> dict:
    payload = _build_live_payload()
    global _latest
    _latest = payload
    _maybe_log_fix(payload)
    return payload


@app.get("/api/raw")
def raw_snapshot() -> dict:
    payload = _build_live_payload()
    payload["gpsd_raw"] = gps.read_gpsd_raw()
    global _latest
    _latest = payload
    _maybe_log_fix(payload)
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


@app.get("/api/config")
def app_config() -> dict:
    return config.public_config()


@app.get("/api/geocode")
def geocode(q: str = Query(min_length=2)) -> dict:
    try:
        return {"results": routing.geocode(q)}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class RouteRequest(BaseModel):
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    profile: Literal["driving", "foot", "bike"] = "driving"


@app.post("/api/route")
def build_route(body: RouteRequest) -> dict:
    try:
        return routing.route(
            body.from_lat,
            body.from_lon,
            body.to_lat,
            body.to_lon,
            profile=body.profile,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
