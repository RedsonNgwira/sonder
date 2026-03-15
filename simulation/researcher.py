"""
simulation/researcher.py — Web search for behavioral grounding.
Searches for real human behavior patterns relevant to the scene,
returns a concise research summary to inform agent creation.
"""
import asyncio
import httpx


async def research_scene(scene_prompt: str) -> str:
    """
    Generate search queries from the scene, fetch DuckDuckGo snippets,
    return a behavioral research summary string.
    Falls back to empty string if search fails — world creation still works.
    """
    queries = await _generate_queries(scene_prompt)
    snippets = await asyncio.gather(*[_ddg_search(q) for q in queries[:3]])
    flat = [s for group in snippets for s in group]
    if not flat:
        return ""
    return "## Behavioral Research\n" + "\n".join(f"- {s}" for s in flat[:12])


async def _generate_queries(scene: str) -> list[str]:
    """Use the LLM to generate 3 targeted behavioral search queries."""
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
        # Fallback: derive queries directly from scene words
        words = scene.lower().split()[:6]
        return [f"human behavior {' '.join(words[:4])}", f"psychology {' '.join(words[:3])}"]


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
