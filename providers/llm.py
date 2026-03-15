"""
providers/llm.py — LiteLLM wrapper using Sonder's provider config.
Supports all built-in providers + custom OpenAI-compatible endpoints.
"""
from litellm import acompletion
from config import config


async def chat(system_prompt: str, messages: list[dict], temperature: float = 0.9, max_tokens: int = 4096) -> str:
    """Single LLM call. Returns the text response."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    kwargs: dict = {
        "model": config.model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    api_key = config.get_api_key()
    if api_key:
        kwargs["api_key"] = api_key

    base_url = config.get_base_url()
    if base_url:
        kwargs["api_base"] = base_url

    response = await acompletion(**kwargs)
    return response.choices[0].message.content.strip()
