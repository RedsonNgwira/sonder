"""
providers/llm.py — LiteLLM wrapper. All LLM calls go through here.
Swap model/provider in config.yaml — nothing else changes.
"""
from litellm import acompletion
from config import config


async def chat(system_prompt: str, messages: list[dict], temperature: float = 0.9) -> str:
    """Single LLM call. Returns the text response."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    kwargs = {
        "model": config.model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": 200,
    }

    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.api_base:
        kwargs["api_base"] = config.api_base

    response = await acompletion(**kwargs)
    return response.choices[0].message.content.strip()
