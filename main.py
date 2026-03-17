"""
main.py — Sonder FastAPI application.
"""
import asyncio
import json
import os
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import get_config, save_config, BUILTIN_PROVIDERS
from db.database import init_db, save_world, load_world, list_worlds, delete_world
from db.models import Message
from simulation.world_builder import build_world
from simulation.loop import run_turn
from simulation.narrator import narrate
from plugins import on_world_start as _plugin_world_start

STATIC_DIR = Path(__file__).parent / "static"
connections: dict[str, list[WebSocket]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cfg = get_config()
    if cfg.open_browser:
        asyncio.get_event_loop().call_later(1.0, webbrowser.open, f"http://localhost:{cfg.port}")
    yield


app = FastAPI(title="Sonder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def api_get_config():
    cfg = get_config()
    return {k: v for k, v in cfg.model_dump().items() if k != "keys"}


@app.get("/api/setup/needed")
def setup_needed():
    return {"needed": not get_config().is_setup()}


@app.get("/api/providers")
def get_providers():
    cfg = get_config()
    result = []
    for provider, env_var in BUILTIN_PROVIDERS.items():
        has_key = (
            bool(cfg.keys.get(provider))
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
    message_pace_ms: int | None = None
    web_search_enabled: bool | None = None


@app.post("/api/config")
def api_update_config(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = save_config(updates)
    return {"ok": True, "model": cfg.model}


@app.get("/api/models")
async def api_get_models(provider: str = "openrouter"):
    cfg = get_config()
    key = cfg.keys.get(provider, "")
    auth = {"Authorization": f"Bearer {key}"} if key else {}

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            if provider == "openrouter":
                r = await client.get("https://openrouter.ai/api/v1/models", headers=auth)
                models = [f"openrouter/{m['id']}" for m in r.json().get("data", [])]
            elif provider == "groq":
                r = await client.get("https://api.groq.com/openai/v1/models", headers=auth)
                models = [f"groq/{m['id']}" for m in r.json().get("data", [])]
            elif provider == "openai":
                r = await client.get("https://api.openai.com/v1/models", headers=auth)
                models = sorted([f"openai/{m['id']}" for m in r.json().get("data", []) if "gpt" in m["id"]])
            elif provider == "ollama":
                r = await client.get("http://localhost:11434/api/tags")
                models = [f"ollama/{m['name']}" for m in r.json().get("models", [])]
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
    cfg = get_config()
    agent_count = max(2, min(body.agent_count, cfg.max_agents))

    import asyncio
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(msg: str):
        await queue.put({"type": "progress", "message": msg})

    async def run():
        try:
            world = await build_world(body.prompt, agent_count, progress)
            save_world(world)
            await queue.put({"type": "done", "world": world.model_dump()})
        except Exception as e:
            msg = str(e)
            if "402" in msg or "credits" in msg.lower():
                msg = "Provider has no credits. Pick a free model or add credits."
            elif "401" in msg or "invalid" in msg.lower():
                msg = "Invalid API key. Run `python onboard.py` to reconfigure."
            await queue.put({"type": "error", "message": msg})

    async def stream():
        task = asyncio.create_task(run())
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("done", "error"):
                break
        task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream")


class NarratorRequest(BaseModel):
    question: str


@app.post("/api/worlds/{world_id}/narrator")
async def narrator_endpoint(world_id: str, body: NarratorRequest):
    world = load_world(world_id)
    if not world:
        raise HTTPException(404, "World not found")
    try:
        answer = await narrate(world, body.question)
    except Exception as e:
        msg = str(e)
        if "RateLimit" in msg or "quota" in msg.lower() or "429" in msg:
            msg = "Rate limit reached — your free quota is exhausted. Wait a moment or switch providers with `python onboard.py`."
        elif "401" in msg or "invalid" in msg.lower():
            msg = "Auth error — run `python onboard.py` to re-authenticate."
        raise HTTPException(500, msg)
    return {"answer": answer}


@app.get("/api/worlds/{world_id}")
def get_world(world_id: str):
    world = load_world(world_id)
    if not world:
        raise HTTPException(404, "World not found")
    return world.model_dump()


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{world_id}")
async def simulation_ws(websocket: WebSocket, world_id: str):
    await websocket.accept()
    connections.setdefault(world_id, []).append(websocket)

    world = load_world(world_id)
    if world:
        await _plugin_world_start(world)

    user_queue: asyncio.Queue = asyncio.Queue()
    stop = asyncio.Event()

    async def broadcast(msg: dict):
        dead = []
        for ws in connections.get(world_id, []):
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections[world_id].remove(ws)

    participant_name: list[str] = ["You"]  # mutable container so receive_loop can set it

    async def receive_loop():
        try:
            while True:
                data = await websocket.receive_text()
                payload = json.loads(data)
                if payload.get("join"):
                    participant_name[0] = payload["join"]
                elif payload.get("text"):
                    text = payload["text"]
                    target = payload.get("target") or None
                    speaker = payload.get("speaker") or participant_name[0]
                    user_queue.put_nowait(Message(speaker=speaker, text=text, target=target))
        except Exception:
            stop.set()

    async def simulation_loop():
        await asyncio.sleep(1.0)  # let client finish rendering before first turn
        while not stop.is_set():
            world = load_world(world_id)
            if not world:
                break

            user_msg = None
            while not user_queue.empty():
                user_msg = user_queue.get_nowait()

            try:
                await run_turn(world, user_msg, broadcast, participant_name[0] if participant_name[0] != "You" else None)
            except Exception as e:
                msg = str(e)
                if "RateLimit" in msg or "quota" in msg.lower() or "429" in msg:
                    msg = "Rate limit reached — free quota exhausted. Wait a moment or run `python onboard.py` to switch providers."
                await broadcast({"type": "error", "message": msg})

            await asyncio.sleep(max(1.0, get_config().simulation_tick_ms / 1000))

    recv_task = asyncio.create_task(receive_loop())
    sim_task  = asyncio.create_task(simulation_loop())

    try:
        await recv_task
    finally:
        stop.set()
        sim_task.cancel()
        if websocket in connections.get(world_id, []):
            connections[world_id].remove(websocket)


# ── Static routes ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/onboarding")
def onboarding():
    return FileResponse(STATIC_DIR / "onboarding.html")

@app.get("/about")
def about_page():
    return FileResponse(STATIC_DIR / "about.html")

@app.get("/settings")
def settings_page():
    return FileResponse(STATIC_DIR / "settings.html")


if __name__ == "__main__":
    import uvicorn
    from onboard import BANNER
    cfg = get_config()
    print(BANNER)
    print(f"\033[2m  → http://{cfg.host}:{cfg.port}\033[0m\n")
    uvicorn.run("main:app", host=cfg.host, port=cfg.port, reload=False)
