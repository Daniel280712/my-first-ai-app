#!/usr/bin/env python3
"""WK2 garage log — dump a note in plain English, keep a structured history."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "garage" / "profile.json"
LOG_PATH = ROOT / "garage" / "log.jsonl"


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text())


def append_entry(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_entries() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    entries = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def parse_with_ai(note: str, profile: dict) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "type": "note",
            "summary": note,
            "mileage": None,
            "cost_gbp": None,
            "tags": [],
            "parsed_by": "raw",
        }

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install deps: pip install -r requirements.txt") from exc

    client = OpenAI(api_key=api_key)
    vehicle = f"{profile['year']} {profile['make']} {profile['model']} {profile['engine']}"
    prompt = f"""You parse garage notes for a {vehicle}.

Return JSON only with keys:
- type: one of service, mod, fuel, issue, trip, note
- summary: one short sentence
- mileage: integer or null
- cost_gbp: number or null
- tags: array of short strings

Note: {note}"""

    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "You extract structured garage log data. Reply with JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    parsed = json.loads(response.choices[0].message.content)
    parsed["parsed_by"] = "ai"
    return parsed


def cmd_add(note: str) -> None:
    profile = load_profile()
    parsed = parse_with_ai(note, profile)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw": note,
        **parsed,
    }
    append_entry(entry)
    print(f"Logged: {entry['summary']}")
    if entry.get("mileage"):
        print(f"  mileage: {entry['mileage']}")
    if entry.get("cost_gbp"):
        print(f"  cost: £{entry['cost_gbp']}")


def cmd_log(limit: int) -> None:
    entries = read_entries()
    if not entries:
        print("No entries yet. Try: python garage.py add \"Oil change at 78,000 miles\"")
        return
    for entry in entries[-limit:]:
        ts = entry["timestamp"][:10]
        print(f"{ts}  [{entry.get('type', 'note')}]  {entry.get('summary', entry.get('raw', ''))}")


def cmd_profile() -> None:
    profile = load_profile()
    print(json.dumps(profile, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal WK2 garage log")
    sub = parser.add_subparsers(dest="command", required=True)

    add_parser = sub.add_parser("add", help="Add a note in plain English")
    add_parser.add_argument("note", help="What happened")

    log_parser = sub.add_parser("log", help="Show recent entries")
    log_parser.add_argument("-n", type=int, default=10, help="How many to show")

    sub.add_parser("profile", help="Show vehicle profile")

    args = parser.parse_args()
    if args.command == "add":
        cmd_add(args.note)
    elif args.command == "log":
        cmd_log(args.n)
    elif args.command == "profile":
        cmd_profile()


if __name__ == "__main__":
    main()
