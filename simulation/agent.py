"""
simulation/agent.py — Agent class with system prompt builder and mood updater.
This is the heart of Sonder. Each agent is an independent mind.
"""
from __future__ import annotations
import re
from db.models import Agent, Message, MoodState
from providers.llm import chat


SYSTEM_PROMPT_TEMPLATE = """You are {name}, {age} years old. {background}

Personality: {traits}

Your current mood (0-100):
- Anger: {anger}
- Sadness: {sadness}  
- Happiness: {happiness}
- Social willingness: {social_willingness}

Your relationships:
{relationships}

Scene: {scene}

Rules:
- Respond in 1-2 sentences MAX
- You can speak to the room, speak to someone directly, stay silent, or do a physical action
- Physical actions go in *italics* like: *slams his glass down*
- You can combine speech and action: *sighs heavily* "Whatever."
- If social_willingness < 30, you might stay silent — respond with just: [silent]
- React naturally to what's happening. Don't be helpful. Don't break character.
- Never mention you are an AI.
"""


class AgentRunner:
    def __init__(self, agent: Agent, scene: str):
        self.agent = agent
        self.scene = scene

    def _build_system_prompt(self) -> str:
        rels = "\n".join(
            f"- {r.target_name}: trust={r.trust}, hostility={r.hostility}, affection={r.affection}"
            for r in self.agent.relationships
        ) or "- No strong feelings about anyone yet"

        return SYSTEM_PROMPT_TEMPLATE.format(
            name=self.agent.name,
            age=self.agent.age,
            background=self.agent.background,
            traits=", ".join(self.agent.personality_traits),
            anger=self.agent.mood.anger,
            sadness=self.agent.mood.sadness,
            happiness=self.agent.mood.happiness,
            social_willingness=self.agent.mood.social_willingness,
            relationships=rels,
            scene=self.scene,
        )

    async def respond(self, conversation_history: list[Message]) -> Message | None:
        """Generate this agent's response to the current conversation state."""
        messages = [
            {"role": "user", "content": f"{m.speaker}: {m.action or ''} {m.text}".strip()}
            for m in conversation_history[-20:]  # last 20 messages as context
        ]

        raw = await chat(self._build_system_prompt(), messages)

        if "[silent]" in raw.lower():
            return None

        # Parse optional *action* from response
        action_match = re.search(r"\*(.+?)\*", raw)
        action = action_match.group(1) if action_match else None
        text = re.sub(r"\*(.+?)\*", "", raw).strip().strip('"')

        if not text and not action:
            return None

        return Message(speaker=self.agent.name, text=text, action=action)

    def update_mood(self, last_message: Message):
        """Nudge mood based on what just happened."""
        m = self.agent.mood
        text = (last_message.text + " " + (last_message.action or "")).lower()

        # Simple heuristic mood shifts — good enough for v1
        if any(w in text for w in ["angry", "furious", "hate", "idiot", "shut up"]):
            m.anger = min(100, m.anger + 8)
            m.social_willingness = max(0, m.social_willingness - 5)
        if any(w in text for w in ["laugh", "haha", "funny", "joke"]):
            m.happiness = min(100, m.happiness + 6)
            m.anger = max(0, m.anger - 4)
        if any(w in text for w in ["sorry", "thanks", "appreciate", "agree"]):
            m.social_willingness = min(100, m.social_willingness + 5)
            m.anger = max(0, m.anger - 3)

        # Slow natural decay toward baseline
        m.anger = max(0, m.anger - 1)
        m.sadness = max(0, m.sadness - 1)
        m.happiness = max(20, m.happiness - 1)
