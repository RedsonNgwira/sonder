"""
db/models.py — Core data models for Sonder.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import time


class MoodState(BaseModel):
    anger: int = 20
    sadness: int = 20
    happiness: int = 60
    social_willingness: int = 70


class RelationshipEntry(BaseModel):
    target_name: str
    trust: int = 50
    hostility: int = 20
    affection: int = 30


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    age: int
    background: str
    personality_traits: list[str]
    speaking_style: str = ""
    current_grievance: str = ""
    mood: MoodState = Field(default_factory=MoodState)
    relationships: list[RelationshipEntry] = []
    memory: list[str] = []  # [0] = behavioral notes from .md; rest = recent exchanges


class World(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slug: str = ""          # filesystem slug for .md files
    name: str
    scene_description: str
    location: str
    atmosphere: str
    agents: list[Agent] = []
    conversation: list[Message] = []
    created_at: float = Field(default_factory=time.time)
    tension: int = 30
    noise: int = 40
    warmth: int = 60


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    speaker: str
    text: str
    action: Optional[str] = None
    target: Optional[str] = None   # set for whispers — only that agent responds
    timestamp: float = Field(default_factory=time.time)
