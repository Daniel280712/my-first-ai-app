"""Read GPS fixes from gpsd (USB GPS on the Pi)."""

from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class GpsFix:
    lat: float | None
    lon: float | None
    altitude_m: float | None
    speed_mps: float | None
    track_deg: float | None
    satellites: int | None
    hdop: float | None
    mode: int
    source: str
    timestamp: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_gpsd(host: str = "127.0.0.1", port: int = 2947, timeout: float = 2.0) -> GpsFix:
    """Return the latest TPV fix from a local gpsd instance."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
        sock.settimeout(timeout)
        for _ in range(40):
            chunk = sock.recv(4096).decode("utf-8", errors="replace")
            for line in chunk.splitlines():
                if not line.startswith("{"):
                    continue
                payload = json.loads(line)
                if payload.get("class") != "TPV":
                    continue
                if payload.get("mode", 0) < 2:
                    continue
                return GpsFix(
                    lat=payload.get("lat"),
                    lon=payload.get("lon"),
                    altitude_m=payload.get("alt"),
                    speed_mps=payload.get("speed"),
                    track_deg=payload.get("track"),
                    satellites=None,
                    hdop=None,
                    mode=int(payload.get("mode", 0)),
                    source="gpsd",
                    timestamp=_now(),
                )
    return GpsFix(
        lat=None,
        lon=None,
        altitude_m=None,
        speed_mps=None,
        track_deg=None,
        satellites=None,
        hdop=None,
        mode=0,
        source="gpsd",
        timestamp=_now(),
    )


def read_gpsd_status(host: str = "127.0.0.1", port: int = 2947, timeout: float = 2.0) -> dict:
    """Sky view / satellite info when available."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
        sock.settimeout(timeout)
        for _ in range(60):
            chunk = sock.recv(8192).decode("utf-8", errors="replace")
            for line in chunk.splitlines():
                if not line.startswith("{"):
                    continue
                payload = json.loads(line)
                if payload.get("class") == "SKY":
                    return {
                        "satellites_visible": len(payload.get("satellites", [])),
                        "satellites_used": payload.get("uSat"),
                        "hdop": payload.get("hdop"),
                        "source": "gpsd",
                        "timestamp": _now(),
                    }
    return {"satellites_visible": None, "satellites_used": None, "hdop": None, "source": "gpsd", "timestamp": _now()}


def read_gpsd_raw(max_messages: int = 15, timeout: float = 2.5) -> list[dict]:
    """Collect recent raw gpsd JSON messages (TPV, SKY, DEVICE, etc.)."""
    messages: list[dict] = []
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=timeout) as sock:
            sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
            sock.settimeout(timeout)
            while len(messages) < max_messages:
                chunk = sock.recv(8192).decode("utf-8", errors="replace")
                if not chunk:
                    break
                for line in chunk.splitlines():
                    if not line.startswith("{"):
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("class") in {"TPV", "SKY", "DEVICE", "VERSION", "WATCH"}:
                        messages.append(payload)
                        if len(messages) >= max_messages:
                            break
    except OSError:
        return [{"error": "gpsd not reachable on 127.0.0.1:2947"}]
    return messages or [{"error": "no gpsd messages yet"}]
