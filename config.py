"""
config.py — loads config.yaml, resolves API keys from env vars,
supports built-in and custom providers.
"""
import os
import shutil
from pathlib import Path
from pydantic import BaseModel
import yaml

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
EXAMPLE_PATH = BASE_DIR / "config.example.yaml"

# Built-in provider → env var name
BUILTIN_PROVIDERS = {
    "openai":       "OPENAI_API_KEY",
    "anthropic":    "ANTHROPIC_API_KEY",
    "openrouter":   "OPENROUTER_API_KEY",
    "groq":         "GROQ_API_KEY",
    "mistral":      "MISTRAL_API_KEY",
    "gemini":       "GEMINI_API_KEY",
    "xai":          "XAI_API_KEY",
    "together":     "TOGETHER_API_KEY",
    "huggingface":  "HUGGINGFACE_HUB_TOKEN",
    "ollama":       None,  # no key needed
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
        """Extract provider name from model string (e.g. 'openai' from 'openai/gpt-4o')."""
        return self.model.split("/")[0]

    def get_api_key(self) -> str:
        """Resolve API key: config keys → env var → empty string."""
        provider = self.get_provider()

        # Check config keys first
        if self.keys.get(provider):
            return self.keys[provider]

        # Fall back to env var
        env_var = BUILTIN_PROVIDERS.get(provider)
        if env_var and os.environ.get(env_var):
            return os.environ[env_var]

        # Custom provider key
        if provider in self.custom_providers:
            return self.custom_providers[provider].api_key

        return ""

    def get_base_url(self) -> str:
        """Return custom base_url if provider is a custom provider."""
        provider = self.get_provider()
        if provider in self.custom_providers:
            return self.custom_providers[provider].base_url
        return ""

    def is_setup(self) -> bool:
        """Returns True if the active model has a usable auth config."""
        provider = self.get_provider()
        if provider == "ollama":
            return True
        return bool(self.get_api_key())


def load_config() -> SonderConfig:
    if not CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}

    return SonderConfig(**{k: v for k, v in data.items() if v is not None})


def save_config(updates: dict) -> SonderConfig:
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    # Deep merge keys dict
    if "keys" in updates and "keys" in data:
        data["keys"].update(updates.pop("keys"))
    data.update(updates)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return load_config()


config = load_config()
