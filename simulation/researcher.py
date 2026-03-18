"""
simulation/researcher.py — Web search for behavioral grounding.
Uses Tavily if TAVILY_API_KEY is configured, otherwise DuckDuckGo (no key needed).
Falls back gracefully — world creation always works even if search fails.
"""
import asyncio
import httpx


async def research_scene(scene_prompt: str) -> str:
    queries = await _generate_queries(scene_prompt)
    snippets = await asyncio.gather(*[_search(q) for q in queries[:3]])
    flat = [s for group in snippets for s in group]
    if not flat:
        return ""
    return "## Behavioral Research\n" + "\n".join(f"- {s}" for s in flat[:12])


async def _generate_queries(scene: str) -> list[str]:
    from providers.llm import chat
    prompt = (
        "Given this scene, write exactly 3 web search queries to find real human behavioral research "
        "that would help simulate realistic people in this situation.\n"
        "Return only the 3 queries, one per line, no numbering.\n\n"
        f"Scene: {scene}"
    )
    try:
        raw = await chat("You generate search queries.", [{"role": "user", "content": prompt}], max_tokens=100)
        return [q.strip() for q in raw.strip().splitlines() if q.strip()][:3]
    except Exception:
        words = scene.lower().split()[:6]
        return [f"human behavior {' '.join(words[:4])}", f"psychology {' '.join(words[:3])}"]


async def _search(query: str) -> list[str]:
    """Route to Tavily if key available, else DuckDuckGo."""
    from config import get_config
    key = get_config().get_tavily_key()
    if key:
        return await _tavily_search(query, key)
    return await _ddg_search(query)


async def _tavily_search(query: str, api_key: str) -> list[str]:
    """Tavily search — returns full web content optimised for LLMs."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": 4, "search_depth": "basic"},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            data = r.json()
            results = []
            if data.get("answer"):
                results.append(data["answer"][:200])
            for item in data.get("results", [])[:4]:
                if item.get("content"):
                    results.append(item["content"][:150])
            return results
    except Exception:
        return await _ddg_search(query)  # fallback to DDG on any error


async def _ddg_search(query: str) -> list[str]:
    """DuckDuckGo instant answer API — no key needed."""
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "Sonder/1.0"},
            )
            data = r.json()
            results = []
            if data.get("AbstractText"):
                results.append(data["AbstractText"][:200])
            for topic in data.get("RelatedTopics", [])[:4]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(topic["Text"][:150])
            return results
    except Exception:
        return []
