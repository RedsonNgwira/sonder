"""
simulation/world_builder.py — Parses a natural language scene prompt and
generates a full World with agents using an LLM call.
"""
import json
from db.models import World, Agent, MoodState, RelationshipEntry
from providers.llm import chat


BUILDER_PROMPT = """You are a world-building engine for a social simulation.

Given a scene description, generate a JSON object with this exact structure:
{
  "name": "short scene name",
  "location": "specific location",
  "atmosphere": "one sentence describing the mood of the place",
  "scene_description": "2-3 sentence vivid description",
  "tension": 40,
  "noise": 50,
  "warmth": 40,
  "agents": [
    {
      "name": "First name only",
      "age": 30,
      "background": "one sentence backstory relevant to this scene",
      "personality_traits": ["trait1", "trait2", "trait3"],
      "mood": {
        "anger": 20,
        "sadness": 20,
        "happiness": 60,
        "social_willingness": 70
      }
    }
  ]
}

Rules:
- Generate exactly {agent_count} agents
- Each agent must feel like a distinct real person, not a stereotype
- Mood values must reflect the scene context (e.g. after a loss, anger/sadness should be high for fans)
- tension, noise, warmth are 0-100 atmosphere meters
- Return ONLY valid JSON, no explanation
"""


async def build_world(prompt: str, agent_count: int) -> World:
    """Turn a natural language scene prompt into a full World object."""
    system = BUILDER_PROMPT.replace("{agent_count}", str(agent_count))
    messages = [{"role": "user", "content": f"Scene: {prompt}"}]

    raw = await chat(system, messages, temperature=0.8)

    # Strip markdown code fences if model wraps in ```json
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    # Extract first JSON object if model added extra text
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"Model did not return valid JSON. Got: {raw[:200]}")
    raw = raw[start:end]
    data = json.loads(raw)

    agents = []
    names = [a["name"] for a in data["agents"]]

    for a in data["agents"]:
        # Build relationships to every other agent
        relationships = [
            RelationshipEntry(target_name=n)
            for n in names if n != a["name"]
        ]
        agents.append(Agent(
            name=a["name"],
            age=a["age"],
            background=a["background"],
            personality_traits=a["personality_traits"],
            mood=MoodState(**a["mood"]),
            relationships=relationships,
        ))

    return World(
        name=data["name"],
        scene_description=data["scene_description"],
        location=data["location"],
        atmosphere=data["atmosphere"],
        agents=agents,
        tension=data.get("tension", 30),
        noise=data.get("noise", 40),
        warmth=data.get("warmth", 60),
    )
