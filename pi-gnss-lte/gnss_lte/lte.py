"""Read LTE signal metrics from ModemManager (USB LTE dongle on the Pi)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lte_available() -> bool:
    return shutil.which("mmcli") is not None


def read_lte() -> dict:
    """Best-effort LTE metrics via mmcli. Requires modem + SIM."""
    if not lte_available():
        return {
            "available": False,
            "reason": "mmcli not installed or no modem configured",
            "timestamp": _now(),
        }

    try:
        listing = subprocess.run(
            ["mmcli", "-L"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "No modem found", "timestamp": _now()}

    match = re.search(r"/Modem/(\d+)", listing.stdout)
    if not match:
        return {"available": False, "reason": "No modem found", "timestamp": _now()}

    modem_id = match.group(1)
    try:
        detail = subprocess.run(
            ["mmcli", "-m", modem_id, "--output-keyvalue"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": str(exc), "timestamp": _now()}

    kv = {}
    for line in detail.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            kv[key.strip()] = value.strip()

    return {
        "available": True,
        "operator": kv.get("modem.3gpp.operator-name") or kv.get("modem.generic.manufacturer"),
        "state": kv.get("modem.generic.state"),
        "signal_quality_percent": _parse_int(kv.get("modem.generic.signal-quality.value")),
        "rsrp_dbm": _parse_signal(kv, "rsrp"),
        "rsrq_db": _parse_signal(kv, "rsrq"),
        "access_tech": kv.get("modem.generic.access-technologies"),
        "timestamp": _now(),
    }


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_signal(kv: dict[str, str], metric: str) -> float | None:
    for key, value in kv.items():
        if metric in key.lower():
            try:
                return float(re.sub(r"[^\d.\-]", "", value))
            except ValueError:
                continue
    return None
