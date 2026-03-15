"""
providers/llm.py — LiteLLM wrapper. Always reads live config via get_config().
"""
import litellm
from config import get_config

litellm.suppress_debug_info = True


async def chat(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.9,
    max_tokens: int = 4096,
) -> str:
    cfg = get_config()
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    kwargs: dict = {
        "model": cfg.model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key := cfg.get_api_key():
        kwargs["api_key"] = api_key
    if base_url := cfg.get_base_url():
        kwargs["api_base"] = base_url

    response = await litellm.acompletion(**kwargs)
    return response.choices[0].message.content.strip()
