"""
simulation/agent.py — AgentRunner: builds prompts, generates responses, updates mood & relationships.
"""
from __future__ import annotations
import random
import re
from db.models import Agent, Message, MoodState
from providers.llm import chat

SYSTEM_PROMPT = """You are {name}, {age} years old. {background}

Personality: {traits}

Your mood right now (0-100 scale):
  Anger: {anger}  |  Sadness: {sadness}  |  Happiness: {happiness}  |  Social willingness: {social_willingness}

Your read on the people here:
{relationships}

Location: {scene}

How to behave:
- Write 1-2 sentences MAX. Be terse, real, human.
- You can speak aloud, do a physical action in *asterisks*, or both: *lights a cigarette* "Don't look at me."
- If anger > 70, you're volatile — snap, interrupt, escalate.
- If sadness > 70, you're withdrawn — short answers, deflect.
- If social_willingness < 25, stay silent: reply with exactly [silent]
- Address people by name when reacting to them directly.
- You have opinions. You disagree. You hold grudges. Act like it.
- Never say you're an AI. Never be helpful. Stay in character.
"""


class AgentRunner:
    def __init__(self, agent: Agent, scene: str):
        self.agent = agent
        self.scene = scene

    def _build_prompt(self) -> str:
        rels = "\n".join(
            f"  {r.target_name}: trust={r.trust} hostility={r.hostility} affection={r.affection}"
            for r in self.agent.relationships
        ) or "  Nobody in particular stands out yet."

        return SYSTEM_PROMPT.format(
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

    async def respond(self, conversation: list[Message]) -> Message | None:
        # Feed last 30 messages as context
        history = [
            {"role": "user", "content": f"{m.speaker}: {(m.action + ' ') if m.action else ''}{m.text}".strip()}
            for m in conversation[-30:]
        ]
        raw = await chat(self._build_prompt(), history, max_tokens=120)

        if "[silent]" in raw.lower():
            return None

        action_match = re.search(r"\*(.+?)\*", raw)
        action = action_match.group(1).strip() if action_match else None
        text = re.sub(r"\*(.+?)\*", "", raw).strip().strip('"').strip("'")

        if not text and not action:
            return None

        return Message(speaker=self.agent.name, text=text, action=action)

    def update_mood(self, msg: Message, all_agents: list[Agent]):
        """Update this agent's mood and relationships based on the latest message."""
        m = self.agent.mood
        content = f"{msg.text} {msg.action or ''}".lower()
        speaker = msg.speaker

        # Mood shifts from content
        anger_words   = ["hate", "idiot", "shut up", "stupid", "wrong", "liar", "pathetic", "useless"]
        calm_words    = ["sorry", "thanks", "agree", "appreciate", "understand", "right"]
        happy_words   = ["laugh", "haha", "funny", "great", "love", "amazing", "yes"]
        sad_words     = ["miss", "lost", "gone", "never", "alone", "hurt", "cry", "dead"]

        if any(w in content for w in anger_words):
            m.anger = min(100, m.anger + 10)
            m.social_willingness = max(0, m.social_willingness - 6)
        if any(w in content for w in calm_words):
            m.anger = max(0, m.anger - 6)
            m.social_willingness = min(100, m.social_willingness + 5)
        if any(w in content for w in happy_words):
            m.happiness = min(100, m.happiness + 7)
            m.anger = max(0, m.anger - 3)
        if any(w in content for w in sad_words):
            m.sadness = min(100, m.sadness + 8)
            m.happiness = max(0, m.happiness - 5)

        # Anger is contagious — if someone nearby is very angry, it raises yours
        for other in all_agents:
            if other.name != self.agent.name and other.mood.anger > 65:
                m.anger = min(100, m.anger + 3)

        # Update relationship with the speaker
        if speaker != self.agent.name and speaker != "You":
            rel = next((r for r in self.agent.relationships if r.target_name == speaker), None)
            if rel:
                if any(w in content for w in anger_words):
                    rel.hostility = min(100, rel.hostility + 8)
                    rel.trust = max(0, rel.trust - 5)
                if any(w in content for w in calm_words):
                    rel.trust = min(100, rel.trust + 5)
                    rel.affection = min(100, rel.affection + 3)

        # Slow natural decay
        m.anger   = max(0, m.anger - 1)
        m.sadness = max(0, m.sadness - 1)
        m.happiness = max(10, m.happiness - 1)
