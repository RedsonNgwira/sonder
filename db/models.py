"""
db/models.py — Pydantic models for worlds, agents, and messages.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import time


class MoodState(BaseModel):
    anger: int = 20          # 0-100
    sadness: int = 20
    happiness: int = 60
    social_willingness: int = 70


class RelationshipEntry(BaseModel):
    target_name: str
    trust: int = 50          # 0-100
    hostility: int = 20
    affection: int = 30


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    age: int
    background: str
    personality_traits: list[str]
    mood: MoodState = Field(default_factory=MoodState)
    relationships: list[RelationshipEntry] = []
    memory: list[str] = []   # last N exchanges as strings


class World(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    scene_description: str
    location: str
    atmosphere: str
    agents: list[Agent] = []
    conversation: list[Message] = []
    created_at: float = Field(default_factory=time.time)
    tension: int = 30        # 0-100 atmosphere meters
    noise: int = 40
    warmth: int = 60


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    speaker: str             # agent name or "You"
    text: str
    action: Optional[str] = None   # italicised physical action
    timestamp: float = Field(default_factory=time.time)
