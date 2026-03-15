"""
simulation/agent_loader.py — Load and parse agent .md files.
Agents are defined in worlds/{world_slug}/agents/{name}.md
Changes to .md files take effect on the next simulation tick.
"""
from __future__ import annotations
import re
import time
from pathlib import Path
from db.models import Agent, MoodState, RelationshipEntry

WORLDS_DIR = Path(__file__).parent.parent / "worlds"


def world_dir(world_slug: str) -> Path:
    return WORLDS_DIR / world_slug


def agent_md_path(world_slug: str, agent_name: str) -> Path:
    slug = agent_name.lower().replace(" ", "-")
    return world_dir(world_slug) / "agents" / f"{slug}.md"


def write_agent_md(world_slug: str, agent: Agent, research: str = "") -> Path:
    """Write an agent's .md definition file. Returns the path."""
    path = agent_md_path(world_slug, agent.name)
    path.parent.mkdir(parents=True, exist_ok=True)

    rels = "\n".join(
        f"- {r.target_name}: trust={r.trust}, hostility={r.hostility}, affection={r.affection}"
        for r in agent.relationships
    ) or "- None yet"

    md = f"""# {agent.name}

## Identity
- Age: {agent.age}
- Background: {agent.background}

## Personality
- Traits: {', '.join(agent.personality_traits)}
- Speaking style: {agent.speaking_style or 'natural'}
- Current grievance: {agent.current_grievance or 'none'}

{research}

## Relationships
{rels}

## Emotional State
- Anger: {agent.mood.anger}
- Sadness: {agent.mood.sadness}
- Happiness: {agent.mood.happiness}
- Social willingness: {agent.mood.social_willingness}

## Behavioral Notes
<!-- Edit freely. Changes take effect on next simulation tick. -->
"""
    path.write_text(md)
    return path


def write_world_md(world_slug: str, name: str, location: str, scene_description: str,
                   atmosphere: str, research: str = "") -> Path:
    path = world_dir(world_slug) / "world.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""# {name}

## Location
{location}

## Scene
{scene_description}

## Atmosphere
{atmosphere}

{research}

## Notes
<!-- World-level behavioral notes. Edit freely. -->
""")
    return path


def load_agent_from_md(path: Path, all_agent_names: list[str]) -> Agent | None:
    """Parse an agent .md file back into an Agent model."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None

    def _get(section: str, default: str = "") -> str:
        m = re.search(rf"## {section}\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else default

    def _field(label: str, block: str, default: str = "") -> str:
        m = re.search(rf"- {label}:\s*(.+)", block)
        return m.group(1).strip() if m else default

    def _mood_val(label: str, block: str, default: int = 50) -> int:
        m = re.search(rf"- {label}:\s*(\d+)", block)
        return int(m.group(1)) if m else default

    # Name from H1
    name_m = re.search(r"^# (.+)", text)
    name = name_m.group(1).strip() if name_m else path.stem.capitalize()

    identity = _get("Identity")
    personality = _get("Personality")
    emotional = _get("Emotional State")
    rels_block = _get("Relationships")

    age_m = re.search(r"- Age:\s*(\d+)", identity)
    age = int(age_m.group(1)) if age_m else 30

    background = _field("Background", identity, "Unknown background")
    traits_m = re.search(r"- Traits:\s*(.+)", personality)
    traits = [t.strip() for t in traits_m.group(1).split(",")] if traits_m else ["unknown"]
    speaking_style = _field("Speaking style", personality)
    grievance = _field("Current grievance", personality)

    mood = MoodState(
        anger=_mood_val("Anger", emotional, 20),
        sadness=_mood_val("Sadness", emotional, 20),
        happiness=_mood_val("Happiness", emotional, 60),
        social_willingness=_mood_val("Social willingness", emotional, 70),
    )

    # Parse relationships
    relationships = []
    for line in rels_block.splitlines():
        m = re.match(r"- (.+?):\s*trust=(\d+),\s*hostility=(\d+),\s*affection=(\d+)", line)
        if m:
            relationships.append(RelationshipEntry(
                target_name=m.group(1), trust=int(m.group(2)),
                hostility=int(m.group(3)), affection=int(m.group(4))
            ))
    # Ensure all agents have a relationship entry
    existing = {r.target_name for r in relationships}
    for n in all_agent_names:
        if n != name and n not in existing:
            relationships.append(RelationshipEntry(target_name=n))

    # Behavioral notes go into memory slot 0 for prompt injection
    behavioral_notes = _get("Behavioral Notes").replace("<!-- Edit freely. Changes take effect on next simulation tick. -->", "").strip()

    agent = Agent(
        name=name, age=age, background=background,
        personality_traits=traits, speaking_style=speaking_style,
        current_grievance=grievance, mood=mood, relationships=relationships,
    )
    if behavioral_notes:
        agent.memory = [behavioral_notes]

    return agent


def reload_agents_if_changed(world_slug: str, agents: list[Agent]) -> tuple[list[Agent], bool]:
    """
    Check if any agent .md file has been modified since last load.
    Returns (updated_agents, changed).
    """
    changed = False
    names = [a.name for a in agents]
    updated = []
    for agent in agents:
        path = agent_md_path(world_slug, agent.name)
        if not path.exists():
            updated.append(agent)
            continue
        mtime = path.stat().st_mtime
        last = getattr(agent, "_md_mtime", 0)
        if mtime > last:
            reloaded = load_agent_from_md(path, names)
            if reloaded:
                reloaded._md_mtime = mtime  # type: ignore
                updated.append(reloaded)
                changed = True
                continue
        updated.append(agent)
    return updated, changed
