"""Append-only track log on the Pi."""

from __future__ import annotations

import json
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "track.jsonl"


def append_snapshot(snapshot: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def read_track(limit: int = 500) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows[-limit:]
