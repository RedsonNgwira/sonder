"""
providers/llm.py — LiteLLM wrapper. Handles API keys and OAuth tokens transparently.
"""
import litellm
from config import get_config
from providers.oauth import OAUTH_PROVIDERS, get_access_token

litellm.suppress_debug_info = True

# Base URLs for OAuth providers (LiteLLM needs openai-compatible endpoint)
_OAUTH_BASE_URLS = {
    "qwen-portal": "https://portal.qwen.ai/v1",
}

# LiteLLM model name mapping for OAuth providers
_OAUTH_MODEL_MAP = {
    "qwen-portal/coder-model":  "openai/qwen-coder-plus-latest",
    "qwen-portal/vision-model": "openai/qwen-vl-plus-latest",
}


async def chat(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.9,
    max_tokens: int = 4096,
) -> str:
    cfg = get_config()
    provider = cfg.get_provider()

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # Resolve model string and auth
    model = cfg.model
    api_key = None
    base_url = None

    if provider in OAUTH_PROVIDERS:
        token = get_access_token(provider)
        if not token:
            raise RuntimeError(
                f"{provider} OAuth token missing or expired. "
                f"Run `python onboard.py` and log in again."
            )
        api_key = token
        base_url = _OAUTH_BASE_URLS.get(provider)
        # Map to openai-compatible model name for LiteLLM
        model = _OAUTH_MODEL_MAP.get(cfg.model, cfg.model.split("/", 1)[-1])
        if not model.startswith("openai/"):
            model = f"openai/{model}"
    else:
        api_key = cfg.get_api_key() or None
        base_url = cfg.get_base_url() or None

    kwargs: dict = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    response = await litellm.acompletion(**kwargs)
    return response.choices[0].message.content.strip()
