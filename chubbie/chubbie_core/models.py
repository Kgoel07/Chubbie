from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LifeStage(StrEnum):
    EGG = "EGG"
    BABY = "BABY"
    TODDLER = "TODDLER"
    TEENAGER = "TEENAGER"
    ADULT = "ADULT"


class Archetype(StrEnum):
    FORMING = "FORMING"
    PROCRASTISAURUS_REX = "PROCRASTISAURUS REX"
    BRAINROT_GOBLIN = "BRAINROT GOBLIN"
    EMOTIONAL_SUPPORT_DRAGON = "EMOTIONAL SUPPORT DRAGON"
    EXISTENTIAL_PHILOSOPHER = "EXISTENTIAL PHILOSOPHER"


class Traits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affection: int = Field(default=50, ge=0, le=100)
    chaos: int = Field(default=30, ge=0, le=100)
    curiosity: int = Field(default=50, ge=0, le=100)
    nerdiness: int = Field(default=50, ge=0, le=100)


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=240)
    created_at: datetime = Field(default_factory=utc_now)
    important: bool = False


class EvolutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_stage: LifeStage
    to_stage: LifeStage
    archetype: Archetype
    reason: str = Field(min_length=1, max_length=240)
    evolved_at: datetime = Field(default_factory=utc_now)


class CreatureState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    name: str = Field(default="Chubbie", min_length=1, max_length=32)
    stage: LifeStage = LifeStage.EGG
    archetype: Archetype = Archetype.FORMING
    mood: str = Field(default="Curious", min_length=1, max_length=32)
    energy: int = Field(default=80, ge=0, le=100)
    traits: Traits = Field(default_factory=Traits)
    created_at: datetime = Field(default_factory=utc_now)
    hatched_at: datetime | None = None
    last_interaction_at: datetime | None = None
    total_interactions: int = Field(default=0, ge=0)
    participant_count: int = Field(default=0, ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    learned_expressions: list[str] = Field(default_factory=list, max_length=12)
    memories: list[Memory] = Field(default_factory=list, max_length=30)
    evolution_history: list[EvolutionRecord] = Field(default_factory=list, max_length=10)
    personality_notes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("action_counts")
    @classmethod
    def validate_action_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 20 or any(v < 0 for v in value.values()):
            raise ValueError("invalid action counts")
        return value

    @field_validator("learned_expressions")
    @classmethod
    def validate_expressions(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 60 for item in value):
            raise ValueError("invalid learned expression")
        return value


class PortableSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    format: Literal["chubbie-portable"] = "chubbie-portable"
    exported_at: datetime = Field(default_factory=utc_now)
    creature: CreatureState
    privacy: Literal["No chat logs, credentials, or user identifiers."] = (
        "No chat logs, credentials, or user identifiers."
    )

