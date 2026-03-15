"""
config.py — Sonder configuration loader.
Single source of truth. Import `get_config()` everywhere — never the module-level `config`.
"""
import os
import shutil
from pathlib import Path
from pydantic import BaseModel
import yaml

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
EXAMPLE_PATH = BASE_DIR / "config.example.yaml"

BUILTIN_PROVIDERS: dict[str, str | None] = {
    "openai":       "OPENAI_API_KEY",
    "anthropic":    "ANTHROPIC_API_KEY",
    "openrouter":   "OPENROUTER_API_KEY",
    "groq":         "GROQ_API_KEY",
    "mistral":      "MISTRAL_API_KEY",
    "gemini":       "GEMINI_API_KEY",
    "xai":          "XAI_API_KEY",
    "together":     "TOGETHER_API_KEY",
    "huggingface":  "HUGGINGFACE_HUB_TOKEN",
    "ollama":       None,
}


class CustomProvider(BaseModel):
    base_url: str
    api_key: str = ""
    models: list[dict] = []


class SonderConfig(BaseModel):
    model: str = "ollama/llama3.3"
    keys: dict[str, str] = {}
    custom_providers: dict[str, CustomProvider] = {}
    max_agents: int = 20
    simulation_tick_ms: int = 1500
    host: str = "0.0.0.0"
    port: int = 8080
    open_browser: bool = True
    web_search_enabled: bool = False

    def get_provider(self) -> str:
        return self.model.split("/")[0]

    def get_api_key(self) -> str:
        provider = self.get_provider()
        if self.keys.get(provider):
            return self.keys[provider]
        env_var = BUILTIN_PROVIDERS.get(provider)
        if env_var and os.environ.get(env_var):
            return os.environ[env_var]
        if provider in self.custom_providers:
            return self.custom_providers[provider].api_key
        return ""

    def get_base_url(self) -> str:
        provider = self.get_provider()
        if provider in self.custom_providers:
            return self.custom_providers[provider].base_url
        return ""

    def is_setup(self) -> bool:
        provider = self.get_provider()
        if provider == "ollama":
            return True
        # OAuth providers: check token file
        from providers.oauth import OAUTH_PROVIDERS, get_access_token
        if provider in OAUTH_PROVIDERS:
            return bool(get_access_token(provider))
        return bool(self.get_api_key())


# ── Module-level singleton — always use get_config() in hot paths ─────────────
_config: SonderConfig | None = None


def get_config() -> SonderConfig:
    global _config
    if _config is None:
        _config = _load()
    return _config


def load_config() -> SonderConfig:
    """Alias kept for compatibility."""
    return get_config()


def save_config(updates: dict) -> SonderConfig:
    global _config
    if not CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    if "keys" in updates and "keys" in data and isinstance(data["keys"], dict):
        data["keys"].update(updates.pop("keys"))
    data.update(updates)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    _config = _load()
    return _config


def _load() -> SonderConfig:
    if not CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    return SonderConfig(**{k: v for k, v in data.items() if v is not None})


# Legacy attribute access — points at live singleton
class _ConfigProxy:
    def __getattr__(self, name):
        return getattr(get_config(), name)

config = _ConfigProxy()  # noqa: used by old imports
