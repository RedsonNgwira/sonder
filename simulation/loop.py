"""
simulation/loop.py — Simulation turn runner.
Agents speak in weighted order (angrier = more likely to speak).
The world keeps running even when the user is silent.
"""
from __future__ import annotations
import asyncio
import random
from db.models import World, Message
from db.database import save_world
from simulation.agent import AgentRunner


def _pick_speakers(world: World) -> list:
    """
    Weight by emotional intensity. Angrier/sadder agents speak more.
    Always pick 1-3 agents per turn.
    """
    def weight(a):
        return max(1, (a.mood.anger + a.mood.sadness + (100 - a.mood.social_willingness)) / 3)

    k = random.randint(1, min(3, len(world.agents)))
    weights = [weight(a) for a in world.agents]
    # random.choices allows repeats — deduplicate by id
    seen, picked = set(), []
    for a in random.choices(world.agents, weights=weights, k=k * 3):
        if a.id not in seen:
            seen.add(a.id)
            picked.append(a)
        if len(picked) == k:
            break
    return picked


async def run_turn(
    world: World,
    user_message: Message | None,
    broadcast,
) -> World:
    cfg = get_config()

    if user_message:
        world.conversation.append(user_message)
        await broadcast(user_message.model_dump())

    speakers = _pick_speakers(world)
    runners = [AgentRunner(a, world.scene_description) for a in speakers]

    responses = await asyncio.gather(
        *[r.respond(world.conversation, world.agents) for r in runners],
        return_exceptions=True,
    )

    for runner, response in zip(runners, responses):
        if isinstance(response, Exception) or response is None:
            continue

        world.conversation.append(response)

        # Every agent updates mood/relationships in response to this message
        for a_runner in [AgentRunner(a, world.scene_description) for a in world.agents]:
            a_runner.update_mood(response, world.agents)

        await broadcast(response.model_dump())
        await asyncio.sleep(0.8)  # stagger messages within a turn

    # Recompute atmosphere from agent moods
    if world.agents:
        n = len(world.agents)
        world.tension = int(sum(a.mood.anger for a in world.agents) / n * 0.9)
        world.warmth  = int(sum(a.mood.happiness for a in world.agents) / n * 0.7)
        world.noise   = int(sum(
            100 - a.mood.social_willingness for a in world.agents
        ) / n * 0.6)

    await broadcast({
        "type": "atmosphere",
        "tension": world.tension,
        "noise": world.noise,
        "warmth": world.warmth,
        "agents": [{"name": a.name, "mood": a.mood.model_dump()} for a in world.agents],
    })

    save_world(world)
    return world
