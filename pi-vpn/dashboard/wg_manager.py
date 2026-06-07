"""WireGuard server management for the Pi VPN dashboard."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

WG_DIR = Path("/etc/wireguard")
WG_IF = "wg0"
CLIENTS_DIR = WG_DIR / "clients"
WG_CONF = WG_DIR / f"{WG_IF}.conf"


@dataclass
class ServerStatus:
    running: bool
    public_key: str | None
    listen_port: int | None
    endpoint: str | None


@dataclass
class PeerStatus:
    name: str
    public_key: str
    allowed_ip: str | None
    last_handshake: str | None
    last_handshake_seconds: int | None
    rx_bytes: int
    tx_bytes: int
    connected: bool


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def read_dashboard_env(path: Path = Path("/etc/wireguard/dashboard.env")) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"')
    return env


def write_dashboard_env(values: dict[str, str], path: Path = Path("/etc/wireguard/dashboard.env")) -> None:
    existing = read_dashboard_env(path) if path.exists() else {}
    existing.update(values)
    lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(600)


def server_installed() -> bool:
    return (WG_DIR / "server.pub").exists() and WG_CONF.exists()


def _parse_peer_names() -> dict[str, str]:
    """Map public keys to friendly names from wg0.conf comments."""
    if not WG_CONF.exists():
        return {}
    text = WG_CONF.read_text(encoding="utf-8")
    names: dict[str, str] = {}
    current_name = "unknown"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_name = stripped.lstrip("#").strip() or current_name
        match = re.match(r"PublicKey\s*=\s*(\S+)", stripped)
        if match:
            names[match.group(1)] = current_name
    return names


def get_server_status() -> ServerStatus:
    env = read_dashboard_env()
    if not server_installed():
        return ServerStatus(running=False, public_key=None, listen_port=None, endpoint=env.get("ENDPOINT"))

    public_key = (WG_DIR / "server.pub").read_text(encoding="utf-8").strip()
    running = False
    listen_port = None

    try:
        result = _run(["wg", "show", WG_IF])
        running = True
        for line in result.stdout.splitlines():
            if line.strip().startswith("listening port:"):
                listen_port = int(line.split(":", 1)[1].strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        running = False

    if listen_port is None and WG_CONF.exists():
        match = re.search(r"ListenPort\s*=\s*(\d+)", WG_CONF.read_text(encoding="utf-8"))
        if match:
            listen_port = int(match.group(1))

    return ServerStatus(
        running=running,
        public_key=public_key,
        listen_port=listen_port,
        endpoint=env.get("ENDPOINT"),
    )


def _format_handshake(seconds: int | None) -> tuple[str | None, int | None]:
    if seconds is None or seconds == 0:
        return None, seconds
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC"), seconds


def list_peers() -> list[dict]:
    if not server_installed():
        return []

    names = _parse_peer_names()
    peers: list[PeerStatus] = []

    try:
        result = _run(["wg", "show", WG_IF, "dump"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    for line in result.stdout.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        _interface, public_key, _, endpoint, allowed_ips, handshake, rx, tx = parts[:8]
        hs = int(handshake) if handshake else 0
        hs_label, hs_raw = _format_handshake(hs if hs > 0 else None)
        ip = allowed_ips.split(",")[0] if allowed_ips else None
        peers.append(
            PeerStatus(
                name=names.get(public_key, public_key[:8]),
                public_key=public_key,
                allowed_ip=ip,
                last_handshake=hs_label,
                last_handshake_seconds=hs_raw,
                rx_bytes=int(rx),
                tx_bytes=int(tx),
                connected=hs > 0 and (datetime.now(tz=timezone.utc).timestamp() - hs) < 180,
            )
        )

    return [asdict(p) for p in peers]


def _next_client_ip() -> str:
    used = set(re.findall(r"AllowedIPs = (10\.8\.0\.\d+)", WG_CONF.read_text(encoding="utf-8")))
    for i in range(2, 255):
        candidate = f"10.8.0.{i}"
        if candidate not in used:
            return candidate
    raise RuntimeError("No free client IPs in 10.8.0.0/24")


def add_client(name: str, endpoint: str | None = None, dns: str = "1.1.1.1") -> dict:
    if not server_installed():
        raise RuntimeError("WireGuard server is not installed.")

    env = read_dashboard_env()
    endpoint = endpoint or env.get("ENDPOINT")
    if not endpoint:
        raise RuntimeError("Set ENDPOINT in dashboard settings or pass endpoint explicitly.")

    safe_name = re.sub(r"[^\w\-]", "-", name.strip().lower())
    if not safe_name:
        raise RuntimeError("Client name is required.")

    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    client_conf_path = CLIENTS_DIR / f"{safe_name}.conf"
    if client_conf_path.exists():
        raise RuntimeError(f"Client '{safe_name}' already exists.")

    client_ip = _next_client_ip()
    client_priv = _run(["wg", "genkey"]).stdout.strip()
    client_pub = _run(["bash", "-c", f"echo '{client_priv}' | wg pubkey"]).stdout.strip()
    server_pub = (WG_DIR / "server.pub").read_text(encoding="utf-8").strip()

    config = f"""[Interface]
PrivateKey = {client_priv}
Address = {client_ip}/32
DNS = {dns}

[Peer]
PublicKey = {server_pub}
Endpoint = {endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""
    client_conf_path.write_text(config, encoding="utf-8")
    client_conf_path.chmod(600)

    with WG_CONF.open("a", encoding="utf-8") as f:
        f.write(f"\n[Peer]\n# {safe_name}\nPublicKey = {client_pub}\nAllowedIPs = {client_ip}/32\n")

    strip = _run(["wg-quick", "strip", WG_IF]).stdout
    subprocess.run(["wg", "syncconf", WG_IF, "-"], input=strip, text=True, check=True)

    return {
        "name": safe_name,
        "ip": client_ip,
        "config": config,
        "qr_png_base64": qr_png_base64(config),
    }


def remove_client(name: str) -> None:
    if not WG_CONF.exists():
        raise RuntimeError("WireGuard config not found.")

    safe_name = re.sub(r"[^\w\-]", "-", name.strip().lower())
    text = WG_CONF.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"\n?\[Peer\]\n# {re.escape(safe_name)}\nPublicKey = \S+\nAllowedIPs = \S+\n",
        re.MULTILINE,
    )
    new_text, count = pattern.subn("\n", text)
    if count == 0:
        raise RuntimeError(f"Client '{safe_name}' not found.")

    WG_CONF.write_text(new_text.strip() + "\n", encoding="utf-8")
    client_conf = CLIENTS_DIR / f"{safe_name}.conf"
    if client_conf.exists():
        client_conf.unlink()

    strip = _run(["wg-quick", "strip", WG_IF]).stdout
    subprocess.run(["wg", "syncconf", WG_IF, "-"], input=strip, text=True, check=False)


def get_client_config(name: str) -> str:
    path = CLIENTS_DIR / f"{name}.conf"
    if not path.exists():
        raise FileNotFoundError(f"No config for client '{name}'.")
    return path.read_text(encoding="utf-8")


def qr_png_base64(config: str) -> str:
    import base64

    proc = subprocess.run(
        ["qrencode", "-t", "PNG", "-o", "-"],
        input=config,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(proc.stdout).decode("ascii")


def list_saved_clients() -> list[str]:
    if not CLIENTS_DIR.exists():
        return []
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.conf"))
