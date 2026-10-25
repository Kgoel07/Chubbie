from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .evolution import Thresholds, evolve_once, select_archetype
from .models import Archetype, CreatureState, EvolutionRecord, LifeStage, Memory


ACTION_EFFECTS: dict[str, dict[str, int | str]] = {
    "feed": {"energy": 15, "affection": 4, "mood": "Content"},
    "play": {"energy": -8, "affection": 8, "chaos": 7, "mood": "Zoomy"},
    "care": {"energy": 5, "affection": 10, "chaos": -2, "mood": "Safe"},
}
VALID_PROGRESS_ACTIONS = frozenset({"feed", "play", "care", "teach"})
BLOCKED_EXPRESSION_PATTERNS = (
    re.compile(r"https?://", re.I),
    re.compile(r"(?:password|api[_ -]?key|token|secret)\s*[:=]", re.I),
    re.compile(r"\b(?:kill|bomb|suicide|self[- ]?harm)\b", re.I),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I),
    re.compile(r"(?:\+?\d[\d ().-]{7,}\d)"),
)


@dataclass(frozen=True)
class ProgressionConfig:
    toddler: int = 8
    teenager: int = 20
    adult: int = 40
    cooldown_seconds: int = 20

    @classmethod
    def demo(cls) -> "ProgressionConfig":
        return cls(toddler=3, teenager=6, adult=10, cooldown_seconds=0)

    def thresholds(self) -> Thresholds:
        return Thresholds(self.toddler, self.teenager, self.adult)


@dataclass
class ActionResult:
    accepted: bool
    message: str
    state: CreatureState
    evolution: EvolutionRecord | None = None
    event: dict[str, object] | None = None


def clamp(value: int) -> int:
    return max(0, min(100, value))


def sanitize_display_text(text: str) -> str:
    return text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")


def validate_expression(expression: str) -> str:
    clean = " ".join(expression.strip().split())
    if not 1 <= len(clean) <= 60:
        raise ValueError("Teach a short expression between 1 and 60 characters.")
    if any(pattern.search(clean) for pattern in BLOCKED_EXPRESSION_PATTERNS):
        raise ValueError("That looks private, unsafe, or link-like, so Chubbie won't memorize it.")
    return sanitize_display_text(clean)


class CreatureEngine:
    def __init__(self, config: ProgressionConfig | None = None) -> None:
        self.config = config or ProgressionConfig()

    def new_egg(self, name: str = "Chubbie") -> CreatureState:
        clean_name = sanitize_display_text(" ".join(name.strip().split())[:32]) or "Chubbie"
        return CreatureState(name=clean_name)

    def hatch(self, state: CreatureState, *, now: datetime | None = None) -> ActionResult:
        if state.stage != LifeStage.EGG:
            return ActionResult(False, f"{state.name} is already hatched.", state)
        now = now or datetime.now(timezone.utc)
        state.stage = LifeStage.BABY
        state.hatched_at = now
        state.last_interaction_at = now
        state.participant_count = max(1, state.participant_count)
        self._remember(state, "hatching", f"{state.name} hatched and immediately demanded snacks.", True, now)
        return ActionResult(
            True,
            f"Hatched {state.name}.",
            state,
            event={"action": "hatch", "success": True, "stage": state.stage.value, "mood": state.mood},
        )

    def apply(
        self,
        state: CreatureState,
        action: str,
        *,
        actor_last_action_at: datetime | None = None,
        participant_count: int | None = None,
        expression: str | None = None,
        now: datetime | None = None,
    ) -> ActionResult:
        action = action.lower().strip()
        now = now or datetime.now(timezone.utc)
        if state.stage == LifeStage.EGG:
            return ActionResult(False, "The egg is judging you silently. Hatch it first.", state)
        if action not in VALID_PROGRESS_ACTIONS:
            return ActionResult(False, f"Unknown care action: {action}", state)
        if actor_last_action_at and now - actor_last_action_at < timedelta(seconds=self.config.cooldown_seconds):
            seconds = self.config.cooldown_seconds - int((now - actor_last_action_at).total_seconds())
            return ActionResult(False, f"Tiny creature, tiny cooldown. Try again in {max(1, seconds)}s.", state)

        state.participant_count = max(state.participant_count, participant_count or 1)
        before = {
            "energy": state.energy,
            "affection": state.traits.affection,
            "chaos": state.traits.chaos,
            "curiosity": state.traits.curiosity,
            "nerdiness": state.traits.nerdiness,
        }
        if action == "teach":
            try:
                clean = validate_expression(expression or "")
            except ValueError as exc:
                return ActionResult(False, str(exc), state)
            if clean.casefold() in {item.casefold() for item in state.learned_expressions}:
                return ActionResult(False, f"{state.name} already knows that one. The bit has limits.", state)
            state.learned_expressions.append(clean)
            state.traits.curiosity = clamp(state.traits.curiosity + 5)
            state.traits.chaos = clamp(state.traits.chaos + 2)
            if any(word in clean.casefold() for word in ("code", "python", "bug", "git", "algorithm")):
                state.traits.nerdiness = clamp(state.traits.nerdiness + 8)
            state.mood = "Impressionable"
            message = "teach accepted."
            self._remember(state, "expression", f'The family taught {state.name} to say "{clean}".', True, now)
            self.note_topics(state, clean, amount=8)
        else:
            effect = ACTION_EFFECTS[action]
            state.energy = clamp(state.energy + int(effect.get("energy", 0)))
            state.traits.affection = clamp(state.traits.affection + int(effect.get("affection", 0)))
            state.traits.chaos = clamp(state.traits.chaos + int(effect.get("chaos", 0)))
            state.mood = str(effect["mood"])
            message = f"{action} accepted."

        state.total_interactions += 1
        state.action_counts[action] = state.action_counts.get(action, 0) + 1
        state.last_interaction_at = now
        evolution = evolve_once(state, self.config.thresholds())
        if evolution:
            self._remember(
                state,
                "evolution",
                f"{state.name} evolved into a {state.stage.value.lower()} shaped by the {state.archetype.value} archetype.",
                True,
                now,
            )
            message += f"\nEVOLUTION! {state.name} became a {state.stage.value.lower()} — {state.archetype.value}."
        elif state.stage in {LifeStage.TEENAGER, LifeStage.ADULT}:
            state.archetype = select_archetype(state)
        after = {
            "energy": state.energy,
            "affection": state.traits.affection,
            "chaos": state.traits.chaos,
            "curiosity": state.traits.curiosity,
            "nerdiness": state.traits.nerdiness,
        }
        event: dict[str, object] = {
            "action": action,
            "success": True,
            "changes": {key: after[key] - before[key] for key in before},
            "stage": state.stage.value,
            "mood": state.mood,
            "evolved": evolution is not None,
        }
        if action == "teach":
            event["learned_expression"] = state.learned_expressions[-1]
        if evolution:
            event["new_archetype"] = state.archetype.value
        return ActionResult(True, message, state, evolution, event)

    def remember_approved_fact(
        self, state: CreatureState, fact: str, *, now: datetime | None = None
    ) -> Memory:
        clean = sanitize_display_text(" ".join(fact.strip().split()))[:180]
        if not clean or any(pattern.search(clean) for pattern in BLOCKED_EXPRESSION_PATTERNS):
            raise ValueError("That memory looks private, unsafe, or empty, so it was not saved.")
        memory = Memory(
            kind="approved_memory",
            text=f"The family deliberately asked {state.name} to remember: {clean}",
            important=True,
            created_at=now or datetime.now(timezone.utc),
        )
        state.memories.append(memory)
        state.memories[:] = state.memories[-30:]
        self.note_topics(state, clean, amount=12)
        return memory

    def note_topics(self, state: CreatureState, text: str, *, amount: int = 3) -> list[str]:
        lowered = text.casefold()
        topic_words = {
            "programming": ("code", "coding", "python", "java", "regex", "regular expression", "compiler", "algorithm", "computer"),
            "video games": ("game", "gaming", "minecraft", "valorant", "fortnite"),
            "music": ("music", "song", "album", "concert", "guitar"),
            "food": ("food", "pizza", "burger", "taco", "snack"),
            "philosophy": ("philosophy", "existential", "meaning of life", "consciousness"),
            "college life": ("class", "exam", "professor", "campus", "assignment", "internship"),
            "memes": ("meme", "brainrot", "rizz", "sigma"),
            "sports": ("football", "basketball", "soccer", "baseball", "sports"),
        }
        changed: list[str] = []
        for topic, words in topic_words.items():
            if any(word in lowered for word in words):
                state.topic_affinities[topic] = clamp(state.topic_affinities.get(topic, 0) + amount)
                changed.append(topic)
        return changed

    def record_group_decision(
        self, state: CreatureState, prompt: str, winning_choice: str, voter_count: int, *, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(timezone.utc)
        choice = sanitize_display_text(winning_choice)[:80]
        self._remember(
            state,
            "group_vote",
            f'The family chose "{choice}" in a {voter_count}-vote emergency meeting.',
            True,
            now,
        )
        lowered = (prompt + " " + choice).lower()
        if any(word in lowered for word in ("code", "mit", "startup", "robot")):
            state.traits.nerdiness = clamp(state.traits.nerdiness + 6)
        elif any(word in lowered for word in ("meme", "chaos", "goblin", "feral")):
            state.traits.chaos = clamp(state.traits.chaos + 6)
        elif any(word in lowered for word in ("kind", "help", "friend", "support")):
            state.traits.affection = clamp(state.traits.affection + 6)
        else:
            state.traits.curiosity = clamp(state.traits.curiosity + 6)
        state.archetype = select_archetype(state)

    def progress_text(self, state: CreatureState) -> str:
        if state.stage == LifeStage.EGG:
            return "Ready to hatch."
        thresholds = self.config.thresholds()
        if state.stage == LifeStage.BABY:
            return f"{state.total_interactions}/{thresholds.toddler} valid interactions to toddler."
        if state.stage == LifeStage.TODDLER:
            extra = " Two distinct parents required." if state.participant_count < 2 else ""
            return f"{state.total_interactions}/{thresholds.teenager} to teenager.{extra}"
        if state.stage == LifeStage.TEENAGER:
            return f"{state.total_interactions}/{thresholds.adult} to adult."
        return "Final form reached. The consequences are permanent-ish."

    @staticmethod
    def _remember(
        state: CreatureState, kind: str, text: str, important: bool, created_at: datetime
    ) -> None:
        state.memories.append(Memory(kind=kind, text=text, important=important, created_at=created_at))
        if len(state.memories) > 30:
            state.memories[:] = state.memories[-30:]

