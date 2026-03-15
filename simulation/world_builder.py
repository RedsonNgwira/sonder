"""
simulation/world_builder.py — Build a World from a natural language scene prompt.
Uses rich behavioral archetypes so agents feel like real people, not NPCs.
"""
import json
from db.models import World, Agent, MoodState, RelationshipEntry
from providers.llm import chat

BUILDER_PROMPT = """You are a social simulation engine. Your job is to populate a scene with psychologically realistic people.

Scene: {prompt}

Generate exactly {agent_count} people for this scene. Each person must:
- Have a specific reason to be in this scene right now
- Have a concrete emotional state driven by recent events in their life
- Have pre-existing opinions about at least one other person in the scene
- Have a dominant personality flaw (jealousy, pride, anxiety, bitterness, impulsiveness, etc.)

Return ONLY this JSON, no explanation:
{{
  "name": "short evocative scene name",
  "location": "specific place",
  "atmosphere": "one vivid sentence — what it feels like to walk in",
  "scene_description": "2-3 sentences. What is happening. What is the tension.",
  "tension": <0-100>,
  "noise": <0-100>,
  "warmth": <0-100>,
  "agents": [
    {{
      "name": "First name only",
      "age": <number>,
      "background": "One sentence: who they are AND why they're here AND what's eating at them right now",
      "personality_traits": ["dominant flaw", "secondary trait", "one redeeming quality"],
      "speaking_style": "how they talk — e.g. 'clipped and sarcastic', 'loud and defensive', 'quiet but cutting'",
      "current_grievance": "what is bothering them most right now, in one sentence",
      "mood": {{
        "anger": <0-100>,
        "sadness": <0-100>,
        "happiness": <0-100>,
        "social_willingness": <0-100>
      }}
    }}
  ]
}}"""


async def build_world(prompt: str, agent_count: int) -> World:
    system = "You are a world-building engine. Return only valid JSON."
    user = BUILDER_PROMPT.format(prompt=prompt, agent_count=agent_count)
    raw = await chat(system, [{"role": "user", "content": user}], temperature=0.85, max_tokens=4096)

    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1:
        raise ValueError(f"No JSON in response: {raw[:300]}")
    data = json.loads(raw[start:end])

    names = [a["name"] for a in data["agents"]]
    agents = []
    for a in data["agents"]:
        relationships = [RelationshipEntry(target_name=n) for n in names if n != a["name"]]
        agents.append(Agent(
            name=a["name"],
            age=a["age"],
            background=a["background"],
            personality_traits=a["personality_traits"],
            speaking_style=a.get("speaking_style", ""),
            current_grievance=a.get("current_grievance", ""),
            mood=MoodState(**a["mood"]),
            relationships=relationships,
        ))

    return World(
        name=data["name"],
        location=data["location"],
        scene_description=data["scene_description"],
        atmosphere=data["atmosphere"],
        agents=agents,
        tension=data.get("tension", 40),
        noise=data.get("noise", 40),
        warmth=data.get("warmth", 40),
    )
