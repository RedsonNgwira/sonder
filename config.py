"""
config.py — loads and validates config.yaml (or config.example.yaml as fallback).
Creates config.yaml from example on first run.
"""
import os
import shutil
from pathlib import Path
from pydantic import BaseModel
import yaml

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
EXAMPLE_PATH = BASE_DIR / "config.example.yaml"


class SonderConfig(BaseModel):
    model: str = "ollama/llama3"
    api_key: str = ""
    api_base: str = ""
    max_agents: int = 20
    simulation_tick_ms: int = 1500
    host: str = "0.0.0.0"
    port: int = 8080
    open_browser: bool = True
    web_search_enabled: bool = False


def load_config() -> SonderConfig:
    if not CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}

    # Allow env vars to override config (e.g. SONDER_API_KEY)
    for field in SonderConfig.model_fields:
        env_key = f"SONDER_{field.upper()}"
        if env_key in os.environ:
            data[field] = os.environ[env_key]

    return SonderConfig(**data)


def save_config(updates: dict) -> SonderConfig:
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    data.update(updates)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return SonderConfig(**data)


config = load_config()
