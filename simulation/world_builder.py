"""
simulation/world_builder.py — Build a World from a scene prompt.
1. Researches real behavioral data for the scene type
2. Generates agents grounded in that research
3. Writes world.md + per-agent .md files
"""
import json
import re
import time
from db.models import World, Agent, MoodState, RelationshipEntry
from providers.llm import chat
from simulation.researcher import research_scene
from simulation.agent_loader import write_agent_md, write_world_md

BUILDER_PROMPT = """You are a social simulation engine. Populate this scene with psychologically realistic people.

Scene: {prompt}

Behavioral research for this scene type:
{research}

Generate exactly {agent_count} people. Each must have:
- A specific reason to be here right now
- A concrete emotional state driven by recent events
- Pre-existing opinions about others in the scene
- A dominant personality flaw (jealousy, pride, bitterness, impulsiveness, etc.)
- A distinct speaking style

Return ONLY valid JSON:
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
      "background": "who they are AND why they're here AND what's eating at them",
      "personality_traits": ["dominant flaw", "secondary trait", "redeeming quality"],
      "speaking_style": "e.g. clipped and sarcastic / loud and defensive / quiet but cutting",
      "current_grievance": "what is bothering them most right now",
      "mood": {{
        "anger": <0-100>,
        "sadness": <0-100>,
        "happiness": <0-100>,
        "social_willingness": <0-100>
      }}
    }}
  ]
}}"""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


async def build_world(prompt: str, agent_count: int) -> World:
    # Step 1: research real behavior for this scene
    research = await research_scene(prompt)

    # Step 2: generate world + agents
    user = BUILDER_PROMPT.format(prompt=prompt, agent_count=agent_count, research=research or "(none available)")
    raw = await chat(
        "You are a world-building engine. Return only valid JSON.",
        [{"role": "user", "content": user}],
        temperature=0.85, max_tokens=4096,
    )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1:
        raise ValueError(f"No JSON in response: {raw[:300]}")
    data = json.loads(raw[start:end])

    names = [a["name"] for a in data["agents"]]
    world_slug = _slugify(data["name"]) + "-" + str(int(time.time()))[-5:]

    agents = []
    for a in data["agents"]:
        relationships = [RelationshipEntry(target_name=n) for n in names if n != a["name"]]
        agent = Agent(
            name=a["name"],
            age=a["age"],
            background=a["background"],
            personality_traits=a["personality_traits"],
            speaking_style=a.get("speaking_style", ""),
            current_grievance=a.get("current_grievance", ""),
            mood=MoodState(**a["mood"]),
            relationships=relationships,
        )
        agents.append(agent)

    world = World(
        name=data["name"],
        location=data["location"],
        scene_description=data["scene_description"],
        atmosphere=data["atmosphere"],
        agents=agents,
        tension=data.get("tension", 40),
        noise=data.get("noise", 40),
        warmth=data.get("warmth", 40),
        slug=world_slug,
    )

    # Step 3: write .md files
    write_world_md(world_slug, world.name, world.location,
                   world.scene_description, world.atmosphere, research)
    for agent in agents:
        write_agent_md(world_slug, agent, research)

    return world
