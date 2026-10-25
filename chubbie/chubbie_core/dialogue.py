from __future__ import annotations

import json
import difflib
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

from .engine import sanitize_display_text
from .models import CreatureState, LifeStage, Memory


logger = logging.getLogger(__name__)
PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


@dataclass(frozen=True)
class ConversationLine:
    author: str
    text: str
    timestamp: datetime
    is_chubbie: bool = False
    user_id: str | None = None


@dataclass(frozen=True)
class DialogueResult:
    text: str
    used_ai: bool
    emotion: str = "unknown"
    topic: str = ""


@dataclass(frozen=True)
class ParticipationEvaluation:
    should_speak: bool
    reason: str
    topic: str
    response_intent: str


class CharacterProvider(Protocol):
    def generate(
        self,
        state: CreatureState,
        conversation: Sequence[ConversationLine],
        current_message: str,
        interaction_type: str,
        relevant_memories: Sequence[Memory],
        response_intent: str = "",
        demo_mode: bool = False,
        recent_responses: Sequence[str] = (),
    ) -> DialogueResult: ...

    def evaluate_participation(
        self,
        state: CreatureState,
        conversation: Sequence[ConversationLine],
        seconds_since_spoke: int | None,
    ) -> ParticipationEvaluation: ...


class DialogueDiagnostics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_success_at: datetime | None = None
        self.last_failure: str | None = None
        self.recent_decisions: list[str] = []

    def success(self) -> None:
        with self._lock:
            self.last_success_at = datetime.now(timezone.utc)
            self.last_failure = None

    def failure(self, text: str) -> None:
        with self._lock:
            self.last_failure = text[:200]

    def decision(self, text: str) -> None:
        with self._lock:
            self.recent_decisions.append(text[:240])
            self.recent_decisions[:] = self.recent_decisions[-8:]

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
                "last_failure": self.last_failure,
                "recent_decisions": list(self.recent_decisions),
            }


DIAGNOSTICS = DialogueDiagnostics()


def _read_prompt(name: str) -> str:
    override = os.getenv("CHUBBIE_CHARACTER_PROMPT") if name == "character.md" else None
    if override:
        return override
    return (PROMPT_ROOT / name).read_text(encoding="utf-8")


def fallback_dialogue(state: CreatureState, interaction_type: str = "talk") -> str:
    # Explicit outage path only; normal dialogue comes from the host model.
    return {
        LifeStage.EGG: "...tap tap? 🥚",
        LifeStage.BABY: "AAAA... egg gone?! 😭🥚" if interaction_type.upper() == "HATCH" else "baba? papa? 🐣",
        LifeStage.TODDLER: "my words got stuck... tell me again? 🧸",
        LifeStage.TEENAGER: "the cloud ate my comeback. tragic. 😭",
        LifeStage.ADULT: "My improv department is temporarily offline. ✨",
    }[state.stage]


def select_relevant_memories(state: CreatureState, query: str, limit: int = 4) -> list[Memory]:
    words = set(re.findall(r"[a-z0-9]+", query.casefold()))
    scored: list[tuple[int, int, Memory]] = []
    for index, memory in enumerate(state.memories):
        memory_words = set(re.findall(r"[a-z0-9]+", memory.text.casefold()))
        overlap = len(words & memory_words)
        score = overlap * 5 + (2 if memory.important and overlap else 0)
        if overlap or memory.kind in {"evolution", "hatching"}:
            scored.append((score, index, memory))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def _context_payload(
    state: CreatureState,
    conversation: Sequence[ConversationLine],
    current_message: str,
    interaction_type: str,
    relevant_memories: Sequence[Memory],
    response_intent: str,
    demo_mode: bool,
    recent_responses: Sequence[str],
) -> str:
    payload = {
        "identity": {
            "name": state.name,
            "developmental_stage": state.stage.value,
            "archetype": state.archetype.value,
            "mood": state.mood,
            "energy_band": "low" if state.energy < 30 else "high" if state.energy > 70 else "steady",
            "traits": state.traits.model_dump(),
            "strongest_interests": sorted(state.topic_affinities.items(), key=lambda item: item[1], reverse=True)[:5],
            "learned_expressions": state.learned_expressions[-4:],
        },
        "relevant_memories": [memory.text for memory in relevant_memories[:4]],
        "recent_conversation": [
            {"speaker": line.author[:40], "message": line.text[:400]} for line in conversation[-12:]
        ],
        "recent_responses": list(recent_responses[-10:]) or [
            line.text[:300] for line in conversation if line.is_chubbie
        ][-10:],
        "current_message": current_message[:500],
        "interaction_type": interaction_type[:40],
        "event_type": interaction_type[:40].upper(),
        "demo_mode": demo_mode,
        "response_intent": response_intent[:160],
    }
    return json.dumps(payload, ensure_ascii=False)


class OpenAICharacterProvider:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.api_key, timeout=15.0, max_retries=1)

    def generate(
        self,
        state: CreatureState,
        conversation: Sequence[ConversationLine],
        current_message: str,
        interaction_type: str,
        relevant_memories: Sequence[Memory],
        response_intent: str = "",
        demo_mode: bool = False,
        recent_responses: Sequence[str] = (),
    ) -> DialogueResult:
        if not self.api_key:
            return DialogueResult(fallback_dialogue(state, interaction_type), False)
        try:
            data: dict[str, object] = {}
            text = ""
            intent = response_intent
            for attempt in range(2):
                response = self._client().responses.create(
                    model=self.model,
                    instructions=_read_prompt("character.md"),
                    input=_context_payload(
                        state,
                        conversation,
                        current_message,
                        interaction_type,
                        relevant_memories,
                        intent,
                        demo_mode,
                        recent_responses,
                    ),
                    reasoning={"effort": "minimal"},
                    max_output_tokens=300,
                    store=False,
                )
                raw_output = response.output_text.strip()
                if raw_output.startswith("```"):
                    raw_output = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_output, flags=re.IGNORECASE)
                try:
                    parsed = json.loads(raw_output)
                    data = parsed if isinstance(parsed, dict) else {"text": response.output_text}
                except json.JSONDecodeError:
                    data = {"text": response.output_text, "emotion": "unknown", "topic": ""}
                text = sanitize_display_text(str(data.get("text", "")).strip())[:500]
                if not text:
                    raise ValueError("empty character text")
                baby_problems = _baby_violations(text) if state.stage == LifeStage.BABY else []
                repetition_problem = _repeats_recent_response(text, conversation, recent_responses)
                if _has_emoji(text) and not baby_problems and not repetition_problem:
                    break
                requirements = []
                if not _has_emoji(text):
                    requirements.append("Include at least one personality-appropriate emoji.")
                if baby_problems:
                    requirements.append(
                        "Rewrite as barely verbal BABY dialogue: 2-10 simple words, no mature jokes, narration, stats, or formatting."
                    )
                if repetition_problem:
                    requirements.append(
                        "Use a different expression, joke, question, wording, and emoji combination from recent_responses."
                    )
                intent = (response_intent + " " + " ".join(requirements)).strip()
            if state.stage == LifeStage.BABY and _baby_violations(text):
                DIAGNOSTICS.failure("BABY stage validation failed twice; safe fallback used.")
                logger.warning("OpenAI BABY dialogue failed stage validation twice; using fallback.")
                return DialogueResult(fallback_dialogue(state, interaction_type), False, "confused", "")
            if _repeats_recent_response(text, conversation, recent_responses):
                DIAGNOSTICS.failure("Dialogue repeated a recent response twice; safe fallback used.")
                logger.warning("OpenAI dialogue repeated recent output twice; using fallback.")
                return DialogueResult(fallback_dialogue(state, interaction_type), False)
            if not _has_emoji(text):
                text = f"{text} {_emoji_fallback(state)}"
            DIAGNOSTICS.success()
            return DialogueResult(text, True, str(data.get("emotion", "unknown"))[:32], str(data.get("topic", ""))[:80])
        except Exception as exc:
            failure = f"{type(exc).__name__} status={getattr(exc, 'status_code', None)} code={getattr(exc, 'code', None)}"
            DIAGNOSTICS.failure(failure)
            logger.warning("OpenAI character generation failed (%s); using fallback.", failure)
            return DialogueResult(fallback_dialogue(state, interaction_type), False)

    def evaluate_participation(
        self,
        state: CreatureState,
        conversation: Sequence[ConversationLine],
        seconds_since_spoke: int | None,
    ) -> ParticipationEvaluation:
        if not self.api_key:
            return ParticipationEvaluation(False, "OpenAI is not configured.", "", "")
        payload = {
            "stage": state.stage.value,
            "archetype": state.archetype.value,
            "mood": state.mood,
            "traits": state.traits.model_dump(),
            "interests": sorted(state.topic_affinities.items(), key=lambda item: item[1], reverse=True)[:5],
            "relevant_memories": [
                memory.text
                for memory in select_relevant_memories(
                    state, " ".join(line.text for line in conversation[-8:]), limit=3
                )
            ],
            "seconds_since_chubbie_spoke": seconds_since_spoke,
            "recent_conversation": [
                {"speaker": line.author[:40], "message": line.text[:400]} for line in conversation[-12:]
            ],
        }
        try:
            response = self._client().responses.create(
                model=self.model,
                instructions=_read_prompt("participation.md"),
                input=json.dumps(payload, ensure_ascii=False),
                reasoning={"effort": "minimal"},
                max_output_tokens=240,
                store=False,
            )
            data = json.loads(response.output_text)
            evaluation = ParticipationEvaluation(
                bool(data.get("should_speak", False)),
                str(data.get("reason", ""))[:240],
                str(data.get("topic", ""))[:80],
                str(data.get("response_intent", ""))[:160],
            )
            DIAGNOSTICS.success()
            return evaluation
        except Exception as exc:
            failure = f"participation {type(exc).__name__} status={getattr(exc, 'status_code', None)}"
            DIAGNOSTICS.failure(failure)
            logger.warning("OpenAI participation evaluation failed (%s); staying silent.", failure)
            return ParticipationEvaluation(False, "Evaluation unavailable.", "", "")


def generate_character_response(
    creature_state: CreatureState,
    conversation_context: Sequence[ConversationLine] = (),
    current_message: str = "",
    interaction_type: str = "talk",
    relevant_memories: Sequence[Memory] | None = None,
    response_intent: str = "",
    provider: CharacterProvider | None = None,
    demo_mode: bool = False,
    recent_responses: Sequence[str] = (),
) -> DialogueResult:
    provider = provider or OpenAICharacterProvider()
    memories = list(relevant_memories) if relevant_memories is not None else select_relevant_memories(
        creature_state, current_message + " " + " ".join(line.text for line in conversation_context[-5:])
    )
    return provider.generate(
        creature_state,
        conversation_context,
        current_message,
        interaction_type,
        memories,
        response_intent,
        demo_mode=demo_mode,
        recent_responses=recent_responses,
    )


def generate_dialogue(state: CreatureState, action: str = "talk", scenario: str | None = None) -> DialogueResult:
    """Compatibility wrapper for command callers."""
    return generate_character_response(state, current_message=scenario or "", interaction_type=action)


def _has_emoji(text: str) -> bool:
    return any(
        0x1F1E6 <= ord(char) <= 0x1FAFF or 0x2600 <= ord(char) <= 0x27BF
        for char in text
    )


def _emoji_fallback(state: CreatureState) -> str:
    return {
        LifeStage.EGG: "🥚",
        LifeStage.BABY: "🐣",
        LifeStage.TODDLER: "🧸",
        LifeStage.TEENAGER: "😭",
        LifeStage.ADULT: "✨",
    }[state.stage]


def _baby_violations(text: str) -> list[str]:
    problems: list[str] = []
    words = re.findall(r"[A-Za-z0-9']+", text)
    if len(words) > 12:
        problems.append("too many words")
    if "\n" in text or any(marker in text for marker in ("**", "```", "# ")):
        problems.append("formatted or multi-paragraph")
    if re.search(r"\bChubbie\s+(?:is|feels|looks|says|wants|thinks)\b", text, re.IGNORECASE):
        problems.append("third-person narration")
    if re.search(r"\b(?:energy|affection|chaos|curiosity|nerdiness)\s*[:=]?\s*\d+\b", text, re.IGNORECASE):
        problems.append("raw stats")
    if len(re.findall(r"[.!?]+", text)) > 4:
        problems.append("too many clauses")
    if words and sum(len(word) for word in words) / len(words) > 6.5 and len(words) > 6:
        problems.append("overly complex vocabulary")
    return problems


def _repeats_recent_response(
    text: str,
    conversation: Sequence[ConversationLine],
    recent_responses: Sequence[str] = (),
) -> bool:
    current = _normalize_response(text)
    if not current:
        return False
    current_emojis = _emoji_signature(text)
    recent = list(recent_responses[-10:]) or [line.text for line in conversation if line.is_chubbie][-10:]
    for previous in recent:
        normalized = _normalize_response(previous)
        if current == normalized:
            return True
        if min(len(current), len(normalized)) >= 12 and difflib.SequenceMatcher(None, current, normalized).ratio() >= 0.82:
            return True
        if len(current_emojis) >= 2 and current_emojis == _emoji_signature(previous):
            return True
    return False


def _normalize_response(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.casefold()))


def _emoji_signature(text: str) -> tuple[str, ...]:
    return tuple(
        char
        for char in text
        if 0x1F1E6 <= ord(char) <= 0x1FAFF or 0x2600 <= ord(char) <= 0x27BF
    )

