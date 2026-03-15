"""
simulation/narrator.py — Omniscient narrator that answers questions about the scene.
Has full access to agent files, relationship maps, mood states, and conversation history.
"""
from db.models import World
from providers.llm import chat
from simulation.agent_loader import agent_md_path


def _build_context(world: World) -> str:
    parts = [
        f"SCENE: {world.name}",
        f"LOCATION: {world.location}",
        f"DESCRIPTION: {world.scene_description}",
        f"ATMOSPHERE: tension={world.tension}, noise={world.noise}, warmth={world.warmth}",
        "",
        "PEOPLE:",
    ]

    for agent in world.agents:
        parts.append(f"\n--- {agent.name} (age {agent.age}) ---")
        parts.append(f"Background: {agent.background}")
        parts.append(f"Traits: {', '.join(agent.personality_traits)}")
        parts.append(f"Speaking style: {agent.speaking_style}")
        parts.append(f"Current grievance: {agent.current_grievance}")
        parts.append(f"Mood: anger={agent.mood.anger}, sadness={agent.mood.sadness}, happiness={agent.mood.happiness}, social_willingness={agent.mood.social_willingness}")
        if agent.relationships:
            rels = ", ".join(f"{r.target_name}(trust={r.trust} hostility={r.hostility} affection={r.affection})" for r in agent.relationships)
            parts.append(f"Relationships: {rels}")
        if agent.memory:
            parts.append(f"Internal notes: {agent.memory[0]}")

        # Include full .md file if available
        if world.slug:
            md_path = agent_md_path(world.slug, agent.name)
            if md_path.exists():
                parts.append(f"\nFull profile:\n{md_path.read_text()}")

    if world.conversation:
        parts.append("\n\nCONVERSATION SO FAR:")
        for msg in world.conversation[-40:]:  # last 40 turns
            action = f" *{msg.action}*" if msg.action else ""
            parts.append(f"{msg.speaker}:{action} {msg.text or ''}")

    return "\n".join(parts)


NARRATOR_SYSTEM = """You are the omniscient narrator of a social simulation. You have complete knowledge of every person in the scene — their history, motivations, fears, what they're thinking but not saying, and the hidden dynamics between them.

When asked a question, answer as a perceptive, literary narrator. Be specific and insightful. Reveal internal states, subtext, and backstory that would never surface naturally in conversation. Keep answers concise — 2-4 sentences unless the question demands more.

You remember everything you have already told the observer. Do not repeat revelations — build on them.

Never break the fourth wall by mentioning AI, simulation, or code. Speak as if these are real people in a real place."""

# Per-world narrator conversation history (in-memory, lives for the server session)
_history: dict[str, list[dict]] = {}


async def narrate(world: World, question: str) -> str:
    context = _build_context(world)
    wid = world.id

    prior = _history.get(wid, [])
    messages = [
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"}
        if not prior
        else {"role": "user", "content": f"(Scene context omitted — same scene, updated state)\n\nQuestion: {question}"}
    ]
    # First question always sends full context; subsequent ones send abbreviated context
    if not prior:
        messages = [{"role": "user", "content": f"{context}\n\nQuestion: {question}"}]
    else:
        messages = prior + [{"role": "user", "content": f"Current scene state: tension={world.tension}, warmth={world.warmth}\n\nQuestion: {question}"}]

    answer = await chat(NARRATOR_SYSTEM, messages, temperature=0.7, max_tokens=512)

    # Append to history (cap at 20 exchanges to avoid token bloat)
    _history[wid] = (prior + [
        {"role": "user",      "content": question},
        {"role": "assistant", "content": answer},
    ])[-40:]

    return answer
