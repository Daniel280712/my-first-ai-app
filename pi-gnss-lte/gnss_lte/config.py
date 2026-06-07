"""Lab configuration from environment file."""

from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path("/etc/gnss-lte-lab.env")


def read_env(path: Path = ENV_PATH) -> dict[str, str]:
    env: dict[str, str] = dict(os.environ)
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def public_config() -> dict:
    env = read_env()
    google_key = env.get("GOOGLE_MAPS_API_KEY", "").strip()
    return {
        "map_provider": "google" if google_key else "osm",
        "google_maps_api_key": google_key or None,
        "pointer_label": env.get("POINTER_LABEL", "You"),
    }
