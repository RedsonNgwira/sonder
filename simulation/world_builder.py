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
- Pre-existing opinions about others in the scene (use real tension — not everyone starts neutral)
- A dominant personality flaw (jealousy, pride, bitterness, impulsiveness, etc.)
- A distinct speaking style

For relationships, use realistic values based on who these people actually are to each other.
High hostility = genuine conflict. Low trust = suspicion. High affection = real warmth.
Do NOT default everyone to trust=50, hostility=20, affection=30.

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
      }},
      "relationships": {{
        "OtherName": {{"trust": <0-100>, "hostility": <0-100>, "affection": <0-100>}}
      }}
    }}
  ]
}}"""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


async def build_world(prompt: str, agent_count: int, progress=None) -> World:
    async def _p(msg: str):
        if progress:
            await progress(msg)

    # Step 1: research real behavior for this scene
    await _p("🔍 Researching the scene…")
    research = await research_scene(prompt)
    await _p("📚 Behavioral research complete")

    # Step 2: generate world + agents
    await _p("🧠 Generating characters…")
    user = BUILDER_PROMPT.format(prompt=prompt, agent_count=agent_count, research=research or "(none available)")
    raw = await chat(
        "You are a world-building engine. Return only valid JSON.",
        [{"role": "user", "content": user}],
        temperature=0.85, max_tokens=8192,
    )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1:
        raise ValueError(f"No JSON in response: {raw[:300]}")
    raw = raw[start:end]

    # Attempt parse — if it fails, retry once without relationships to get a valid world
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await _p("⚠️ Retrying world generation…")
        # Strip relationships from prompt to reduce JSON size
        simple_prompt = user + "\n\nIMPORTANT: Omit the relationships field from each agent to keep JSON short."
        raw2 = await chat(
            "You are a world-building engine. Return only valid JSON.",
            [{"role": "user", "content": simple_prompt}],
            temperature=0.7, max_tokens=8192,
        )
        raw2 = raw2.strip()
        if raw2.startswith("```"):
            raw2 = raw2.split("```")[1].lstrip("json").strip()
        s2, e2 = raw2.find("{"), raw2.rfind("}") + 1
        data = json.loads(raw2[s2:e2])

    names = [a["name"] for a in data["agents"]]
    world_slug = _slugify(data["name"]) + "-" + str(int(time.time()))[-5:]

    agents = []
    for a in data["agents"]:
        await _p(f"✍️  Writing {a['name']}…")
        # Use LLM-generated relationships if provided, else default
        llm_rels = a.get("relationships", {})
        relationships = []
        for n in names:
            if n == a["name"]:
                continue
            if n in llm_rels:
                r = llm_rels[n]
                relationships.append(RelationshipEntry(
                    target_name=n,
                    trust=int(r.get("trust", 50)),
                    hostility=int(r.get("hostility", 20)),
                    affection=int(r.get("affection", 30)),
                ))
            else:
                relationships.append(RelationshipEntry(target_name=n))
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
    await _p(f"🌍 Building {world.name}…")
    write_world_md(world_slug, world.name, world.location,
                   world.scene_description, world.atmosphere, research)
    for agent in agents:
        write_agent_md(world_slug, agent)

    await _p(f"✅ {world.name} is ready")
    return world
