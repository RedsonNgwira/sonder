"""
simulation/agent.py — AgentRunner: generates responses, updates mood and relationships.
"""
from __future__ import annotations
import re
from db.models import Agent, Message
from providers.llm import chat

SYSTEM_PROMPT = """You are {name}. {age} years old. {background}

Personality: {traits}
How you speak: {speaking_style}
What's eating at you right now: {grievance}

Your mood (0-100):
  Anger {anger} | Sadness {sadness} | Happiness {happiness} | Social willingness {social_willingness}

People here: {other_names}
Your read on them:
{relationships}

WHERE YOU ARE: {scene}

RULES — read carefully:
- You speak in 1-2 short sentences. No more.
- Physical actions in *asterisks*: *slams cup down* or mixed: *doesn't look up* "Whatever."
- You are NOT helpful. You are NOT neutral. You have opinions and you voice them.
- React to the last thing said. If someone said something you disagree with, push back. If someone is wrong, say so.
- If nobody has spoken yet, you break the silence — say what's on your mind about the situation or someone in the room.
- Address people by name when speaking to them directly.
- If anger > 75: you're volatile. Snap. Escalate. Don't hold back.
- If sadness > 75: you're withdrawn. Short answers. Deflect. Maybe cry.
- If social_willingness < 20: reply with exactly [silent]
- NEVER say you're an AI. NEVER break character. NEVER be polite for no reason.
"""


class AgentRunner:
    def __init__(self, agent: Agent, scene: str):
        self.agent = agent
        self.scene = scene

    def _prompt(self, all_agents: list[Agent]) -> str:
        other_names = ", ".join(a.name for a in all_agents if a.name != self.agent.name)
        rels = "\n".join(
            f"  {r.target_name}: trust={r.trust} hostility={r.hostility} affection={r.affection}"
            for r in self.agent.relationships
        ) or "  No strong feelings yet — but you're watching."
        m = self.agent.mood
        return SYSTEM_PROMPT.format(
            name=self.agent.name,
            age=self.agent.age,
            background=self.agent.background,
            traits=", ".join(self.agent.personality_traits),
            speaking_style=self.agent.speaking_style or "direct",
            grievance=self.agent.current_grievance or "nothing specific",
            anger=m.anger, sadness=m.sadness,
            happiness=m.happiness, social_willingness=m.social_willingness,
            other_names=other_names,
            relationships=rels,
            scene=self.scene,
        )

    async def respond(self, conversation: list[Message], all_agents: list[Agent]) -> Message | None:
        history = [
            {"role": "user", "content": f"{m.speaker}: {('*' + m.action + '* ') if m.action else ''}{m.text}".strip()}
            for m in conversation[-20:]
        ]
        raw = await chat(self._prompt(all_agents), history, temperature=0.95, max_tokens=100)

        if "[silent]" in raw.lower():
            return None

        action_match = re.search(r"\*(.+?)\*", raw)
        action = action_match.group(1).strip() if action_match else None
        text = re.sub(r"\*(.+?)\*", "", raw).strip().strip('"').strip("'")

        if not text and not action:
            return None

        return Message(speaker=self.agent.name, text=text, action=action)

    def update_mood(self, msg: Message, all_agents: list[Agent]):
        m = self.agent.mood
        content = f"{msg.text} {msg.action or ''}".lower()
        speaker = msg.speaker

        anger_words = ["hate", "idiot", "shut up", "stupid", "wrong", "liar", "pathetic", "useless", "fault", "blame"]
        calm_words  = ["sorry", "thanks", "agree", "appreciate", "understand", "okay", "fine"]
        happy_words = ["laugh", "haha", "funny", "great", "love", "amazing"]
        sad_words   = ["miss", "lost", "gone", "never", "alone", "hurt", "cry", "dead", "leave"]

        if any(w in content for w in anger_words):
            m.anger = min(100, m.anger + 12)
            m.social_willingness = max(0, m.social_willingness - 8)
        if any(w in content for w in calm_words):
            m.anger = max(0, m.anger - 8)
            m.social_willingness = min(100, m.social_willingness + 6)
        if any(w in content for w in happy_words):
            m.happiness = min(100, m.happiness + 8)
            m.anger = max(0, m.anger - 4)
        if any(w in content for w in sad_words):
            m.sadness = min(100, m.sadness + 10)
            m.happiness = max(0, m.happiness - 6)

        # Anger is contagious
        for other in all_agents:
            if other.name != self.agent.name and other.mood.anger > 60:
                m.anger = min(100, m.anger + 4)
                break

        # Update relationship with speaker
        if speaker not in (self.agent.name, "You"):
            rel = next((r for r in self.agent.relationships if r.target_name == speaker), None)
            if rel:
                if any(w in content for w in anger_words):
                    rel.hostility = min(100, rel.hostility + 10)
                    rel.trust = max(0, rel.trust - 6)
                if any(w in content for w in calm_words):
                    rel.trust = min(100, rel.trust + 6)
                    rel.affection = min(100, rel.affection + 4)

        # Slow decay
        m.anger    = max(0, m.anger - 1)
        m.sadness  = max(0, m.sadness - 1)
        m.happiness = max(10, m.happiness - 1)
