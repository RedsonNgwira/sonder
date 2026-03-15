"""
main.py — Sonder FastAPI application entry point.
Serves the web UI and exposes the simulation API + WebSocket.
"""
import asyncio
import json
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config as _cfg
from config import save_config, load_config
from db.database import init_db, save_world, load_world, list_worlds, delete_world
from db.models import Message, World
from simulation.world_builder import build_world
from simulation.loop import run_turn

STATIC_DIR = Path(__file__).parent / "static"

# Active WebSocket connections per world_id
connections: dict[str, list[WebSocket]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if _cfg.config.open_browser:
        asyncio.get_event_loop().call_later(
            1.0, webbrowser.open, f"http://localhost:{_cfg.config.port}"
        )
    yield


app = FastAPI(title="Sonder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Config / Onboarding ───────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    return _cfg.config.model_dump(exclude={"api_key"})


@app.get("/api/setup/needed")
def setup_needed():
    return {"needed": not _cfg.config.is_setup()}


@app.get("/api/providers")
def get_providers():
    from config import BUILTIN_PROVIDERS
    import os
    result = []
    for provider, env_var in BUILTIN_PROVIDERS.items():
        has_key = (
            bool(_cfg.config.keys.get(provider))
            or (env_var and bool(os.environ.get(env_var)))
            or provider == "ollama"
        )
        result.append({"id": provider, "env_var": env_var, "configured": has_key})
    return result


class ConfigUpdate(BaseModel):
    model: str | None = None
    keys: dict | None = None
    max_agents: int | None = None
    simulation_tick_ms: int | None = None
    web_search_enabled: bool | None = None


@app.post("/api/config")
def update_config(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    _cfg.config = save_config(updates)
    return {"ok": True, "model": _cfg.config.model}


@app.get("/api/models")
async def get_models(provider: str = "openrouter"):
    """Fetch live model list from provider API."""
    import httpx
    from config import BUILTIN_PROVIDERS

    key = _cfg.config.keys.get(provider) or ""

    try:
        if provider == "openrouter":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://openrouter.ai/api/v1/models",
                                     headers={"Authorization": f"Bearer {key}"} if key else {})
            models = [f"openrouter/{m['id']}" for m in r.json().get("data", [])]

        elif provider == "groq":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.groq.com/openai/v1/models",
                                     headers={"Authorization": f"Bearer {key}"})
            models = [f"groq/{m['id']}" for m in r.json().get("data", [])]

        elif provider == "ollama":
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get("http://localhost:11434/api/tags")
            models = [f"ollama/{m['name']}" for m in r.json().get("models", [])]

        elif provider == "openai":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.openai.com/v1/models",
                                     headers={"Authorization": f"Bearer {key}"})
            models = sorted(
                [f"openai/{m['id']}" for m in r.json().get("data", [])
                 if "gpt" in m["id"]],
            )

        else:
            models = []

        return {"models": models}

    except Exception as e:
        return {"models": [], "error": str(e)}


# ── Worlds ────────────────────────────────────────────────────────────────────

@app.get("/api/worlds")
def get_worlds():
    return list_worlds()


@app.delete("/api/worlds/{world_id}")
def remove_world(world_id: str):
    delete_world(world_id)
    return {"ok": True}


class CreateWorldRequest(BaseModel):
    prompt: str
    agent_count: int = 5


@app.post("/api/worlds")
async def create_world(body: CreateWorldRequest):
    agent_count = max(2, min(body.agent_count, _cfg.config.max_agents))
    world = await build_world(body.prompt, agent_count)
    save_world(world)
    return world.model_dump()


@app.get("/api/worlds/{world_id}")
def get_world(world_id: str):
    world = load_world(world_id)
    if not world:
        raise HTTPException(404, "World not found")
    return world.model_dump()


# ── WebSocket — real-time simulation ─────────────────────────────────────────

@app.websocket("/ws/{world_id}")
async def simulation_ws(websocket: WebSocket, world_id: str):
    await websocket.accept()
    connections.setdefault(world_id, []).append(websocket)

    async def broadcast(message: dict):
        dead = []
        for ws in connections.get(world_id, []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections[world_id].remove(ws)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            world = load_world(world_id)
            if not world:
                await websocket.send_text(json.dumps({"error": "World not found"}))
                continue

            user_msg = None
            if payload.get("text"):
                user_msg = Message(speaker="You", text=payload["text"])

            await run_turn(world, user_msg, broadcast)

            # Send updated atmosphere after each turn
            await broadcast({
                "type": "atmosphere",
                "tension": world.tension,
                "noise": world.noise,
                "warmth": world.warmth,
                "agents": [
                    {"name": a.name, "mood": a.mood.model_dump()}
                    for a in world.agents
                ],
            })

    except WebSocketDisconnect:
        connections[world_id].remove(websocket)


# ── Frontend routes ───────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/onboarding")
def onboarding():
    return FileResponse(STATIC_DIR / "onboarding.html")


@app.get("/settings")
def settings():
    return FileResponse(STATIC_DIR / "settings.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=_cfg.config.host, port=_cfg.config.port, reload=False)
