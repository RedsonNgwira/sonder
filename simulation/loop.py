"""
simulation/loop.py — The simulation loop.
Decides which agents speak each turn, runs their LLM calls in parallel,
and broadcasts results via a callback.
"""
from __future__ import annotations
import asyncio
import random
from db.models import World, Message
from db.database import save_world
from simulation.agent import AgentRunner
from config import config


def _pick_speakers(world: World, max_speakers: int = 3) -> list:
    """
    Weight agents by emotional intensity — angrier/sadder agents speak more.
    Returns a subset of agents who will act this turn.
    """
    def weight(agent):
        m = agent.mood
        intensity = (m.anger + m.sadness + (100 - m.social_willingness)) / 3
        return max(1, intensity)

    weights = [weight(a) for a in world.agents]
    k = min(max_speakers, len(world.agents))
    return random.choices(world.agents, weights=weights, k=k)


async def run_turn(
    world: World,
    user_message: Message | None,
    broadcast,  # async callable(message: dict)
) -> World:
    """
    Run one simulation turn:
    1. Add user message to conversation (if any)
    2. Pick which agents respond
    3. Run their LLM calls in parallel
    4. Update mood, save world, broadcast each message
    """
    if user_message:
        world.conversation.append(user_message)
        await broadcast(user_message.model_dump())

    speakers = _pick_speakers(world)
    runners = [AgentRunner(agent, world.scene_description) for agent in speakers]

    # All selected agents think in parallel
    responses = await asyncio.gather(
        *[r.respond(world.conversation) for r in runners],
        return_exceptions=True
    )

    for runner, response in zip(runners, responses):
        if isinstance(response, Exception) or response is None:
            continue

        world.conversation.append(response)

        # Update this agent's mood based on what was just said
        runner.update_mood(response)

        await broadcast(response.model_dump())
        await asyncio.sleep(config.simulation_tick_ms / 1000)

    # Update atmosphere meters based on average mood
    if world.agents:
        avg_anger = sum(a.mood.anger for a in world.agents) / len(world.agents)
        avg_happiness = sum(a.mood.happiness for a in world.agents) / len(world.agents)
        world.tension = int(avg_anger * 0.8)
        world.warmth = int(avg_happiness * 0.7)

    save_world(world)
    return world
