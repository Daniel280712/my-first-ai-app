"""FastAPI dashboard for Pi VPN."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from dashboard import wg_manager

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


def _session_secret() -> str:
    env = wg_manager.read_dashboard_env()
    secret = env.get("SESSION_SECRET")
    if secret:
        return secret
    import os

    fallback = os.environ.get("SESSION_SECRET")
    if fallback:
        return fallback
    return secrets.token_hex(32)


app = FastAPI(title="Pi VPN Dashboard")
app.add_middleware(SessionMiddleware, secret_key=_session_secret(), https_only=False)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class LoginIn(BaseModel):
    password: str


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    dns: str = "1.1.1.1"


class SettingsIn(BaseModel):
    endpoint: str = Field(min_length=3)
    dashboard_password: str | None = None


def auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Login required")


def _check_password(password: str) -> bool:
    env = wg_manager.read_dashboard_env()
    expected = env.get("DASHBOARD_PASSWORD")
    if not expected:
        return False
    return secrets.compare_digest(password, expected)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/api/login")
def login(payload: LoginIn, request: Request) -> dict:
    if _check_password(payload.password):
        request.session["authenticated"] = True
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid password")


@app.post("/api/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request) -> dict:
    return {"authenticated": bool(request.session.get("authenticated"))}


@app.get("/api/status")
def status(_auth: None = Depends(auth)) -> dict:
    server = wg_manager.get_server_status()
    return {
        "server": asdict(server),
        "peers": wg_manager.list_peers(),
        "saved_clients": wg_manager.list_saved_clients(),
        "installed": wg_manager.server_installed(),
    }


@app.get("/api/settings")
def get_settings(_auth: None = Depends(auth)) -> dict:
    env = wg_manager.read_dashboard_env()
    return {"endpoint": env.get("ENDPOINT", ""), "has_password": bool(env.get("DASHBOARD_PASSWORD"))}


@app.put("/api/settings")
def update_settings(payload: SettingsIn, _auth: None = Depends(auth)) -> dict:
    updates: dict[str, str] = {"ENDPOINT": payload.endpoint.strip()}
    if payload.dashboard_password:
        updates["DASHBOARD_PASSWORD"] = payload.dashboard_password.strip()
    wg_manager.write_dashboard_env(updates)
    return {"ok": True}


@app.post("/api/clients")
def create_client(payload: ClientIn, _auth: None = Depends(auth)) -> dict:
    try:
        return wg_manager.add_client(payload.name, dns=payload.dns)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/clients/{name}/config")
def client_config(name: str, _auth: None = Depends(auth)) -> dict:
    try:
        config = wg_manager.get_client_config(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"name": name, "config": config, "qr_png_base64": wg_manager.qr_png_base64(config)}


@app.delete("/api/clients/{name}")
def delete_client(name: str, _auth: None = Depends(auth)) -> dict:
    try:
        wg_manager.remove_client(name)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
