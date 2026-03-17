"""
plugins/__init__.py — Plugin loader for Sonder.

Scans plugins/ for installed plugins and dispatches hooks.
Each plugin type is optional — missing plugins are silently skipped.
"""
from __future__ import annotations
import importlib, asyncio
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent
_cache: dict = {}


def _load(prefix: str):
    if prefix in _cache:
        return _cache[prefix]
    for path in _PLUGIN_DIR.glob(f"{prefix}_*.py"):
        name = path.stem  # e.g. voice_elevenlabs
        try:
            mod = importlib.import_module(f"plugins.{name}")
            _cache[prefix] = mod
            return mod
        except Exception:
            pass
    _cache[prefix] = None
    return None


async def on_agent_speak(agent_name: str, text: str, config: dict = {}) -> None:
    """Called after each agent message. Dispatches to voice plugin if installed."""
    mod = _load("voice")
    if mod and hasattr(mod, "speak"):
        try:
            await mod.speak(agent_name, text, config)
        except Exception:
            pass


async def on_world_start(world) -> None:
    """Called when a world starts. Dispatches to memory plugin if installed."""
    mod = _load("memory")
    if mod and hasattr(mod, "on_world_start"):
        try:
            await mod.on_world_start(world)
        except Exception:
            pass


async def on_agent_avatar(agent) -> str | None:
    """Called when an agent is created. Returns image URL or None."""
    mod = _load("avatar")
    if mod and hasattr(mod, "generate"):
        try:
            return await mod.generate(agent)
        except Exception:
            pass
    return None


async def on_export(world, turns: list) -> None:
    """Called to export a session. Dispatches to export plugin if installed."""
    mod = _load("export")
    if mod and hasattr(mod, "export"):
        try:
            await mod.export(world, turns)
        except Exception:
            pass
