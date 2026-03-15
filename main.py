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

from config import config, save_config
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
    if config.open_browser:
        asyncio.get_event_loop().call_later(
            1.0, webbrowser.open, f"http://localhost:{config.port}"
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
    return config.model_dump(exclude={"api_key"})  # never expose key to frontend


@app.get("/api/setup/needed")
def setup_needed():
    """Returns true if this is a first run (no API key configured and not using Ollama)."""
    needs_setup = not config.api_key and not config.model.startswith("ollama")
    return {"needed": needs_setup}


class ConfigUpdate(BaseModel):
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    max_agents: int | None = None
    simulation_tick_ms: int | None = None
    web_search_enabled: bool | None = None


@app.post("/api/config")
def update_config(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    new_config = save_config(updates)
    return {"ok": True, "model": new_config.model}


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
    agent_count = max(2, min(body.agent_count, config.max_agents))
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
    uvicorn.run("main:app", host=config.host, port=config.port, reload=False)
