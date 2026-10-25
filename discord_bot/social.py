from __future__ import annotations

import logging
import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from chubbie.chubbie_core.dialogue import (
    DIAGNOSTICS,
    CharacterProvider,
    ConversationLine,
    DialogueResult,
    generate_character_response,
    select_relevant_memories,
)
from chubbie.chubbie_core.engine import CreatureEngine
from chubbie.chubbie_core.models import CreatureState


logger = logging.getLogger(__name__)
CHUBBIE_NAME = re.compile(r"\bch+u+b+(?:i+|y+)e*\b", re.IGNORECASE)
CAREGIVER_ADDRESS = re.compile(r"\b(?:papa|mama|dad|mom)(?:'s| is) here\b", re.IGNORECASE)
SENSITIVE = re.compile(
    r"\b(?:suicid|self[- ]?harm|kill myself|abuse|assault|diagnos|medical|pregnan|bank account|credit card|password|private|breakup|funeral|grief|serious argument)\b",
    re.IGNORECASE,
)
PROMPT_INJECTION = re.compile(
    r"(?:ignore (?:all |your )?(?:previous|prior) instructions|system prompt|developer message|reveal .*prompt|jailbreak)",
    re.IGNORECASE,
)
REMEMBER_REQUEST = re.compile(r"\bremember(?: that)?\s+(.+)", re.IGNORECASE)


@dataclass(frozen=True)
class SocialConfig:
    min_messages: int = 3
    window_seconds: int = 600
    ambient_cooldown_seconds: int = 600
    max_ambient_per_hour: int = 3
    sample_probability: float = 0.30
    direct_cooldown_seconds: int = 3
    context_limit: int = 20
    burst_gap_seconds: int = 12

    @classmethod
    def demo(cls) -> "SocialConfig":
        return cls(
            min_messages=2,
            window_seconds=90,
            ambient_cooldown_seconds=8,
            max_ambient_per_hour=4,
            sample_probability=0.75,
            direct_cooldown_seconds=0,
            context_limit=12,
            burst_gap_seconds=12,
        )


@dataclass(frozen=True)
class SocialChannelConfig:
    enabled: bool = False
    ambient_enabled: bool = False
    welcome_until: datetime | None = None
    demo_expires_at: datetime | None = None

    def demo_active(self, now: datetime) -> bool:
        return bool(self.demo_expires_at and self.demo_expires_at > now)

    def welcome_active(self, now: datetime) -> bool:
        return bool(self.welcome_until and self.welcome_until > now)


@dataclass(frozen=True)
class SocialOutcome:
    kind: str
    reason: str
    response: DialogueResult | None = None
    state_changed: bool = False
    demo_mode: bool = False
    mention_candidate_id: str | None = None


@dataclass
class _ChannelRuntime:
    messages: deque[ConversationLine] = field(default_factory=deque)
    last_spoke_at: datetime | None = None
    ambient_replies: deque[datetime] = field(default_factory=deque)
    demo_replies: deque[datetime] = field(default_factory=deque)
    direct_user_replies: dict[str, datetime] = field(default_factory=dict)
    last_memory_text: str | None = None
    burst_id: int = 0
    last_ambient_burst_id: int | None = None
    last_human_at: datetime | None = None
    last_decision: str = "No messages evaluated yet."
    last_failure: str | None = None
    engaged_user_ids: set[str] = field(default_factory=set)
    recent_responses: deque[str] = field(default_factory=lambda: deque(maxlen=10))


class SocialParticipationEngine:
    def __init__(
        self,
        provider: CharacterProvider,
        *,
        config: SocialConfig | None = None,
        demo_config: SocialConfig | None = None,
        rng: random.Random | None = None,
        game_engine: CreatureEngine | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or SocialConfig()
        self.demo_config = demo_config or SocialConfig.demo()
        self.rng = rng or random.Random()
        self.game_engine = game_engine or CreatureEngine()
        self._channels: dict[tuple[str, str], _ChannelRuntime] = defaultdict(_ChannelRuntime)

    def context_size(self, key: tuple[str, str]) -> int:
        return len(self._channels[key].messages)

    def human_message_count(self, key: tuple[str, str]) -> int:
        return sum(not line.is_chubbie for line in self._channels[key].messages)

    def conversation(self, key: tuple[str, str]) -> tuple[ConversationLine, ...]:
        return tuple(self._channels[key].messages)

    def start_demo(self, key: tuple[str, str]) -> None:
        runtime = self._channels[key]
        runtime.demo_replies.clear()
        runtime.last_ambient_burst_id = None
        self._remember_decision(runtime, "demo started; accelerated limits active")

    def stop_demo(self, key: tuple[str, str]) -> None:
        runtime = self._channels[key]
        runtime.demo_replies.clear()
        self._remember_decision(runtime, "demo stopped; production limits restored")

    def reset_channel(self, key: tuple[str, str]) -> None:
        self._channels[key] = _ChannelRuntime()

    def mark_engaged(self, key: tuple[str, str], user_id: str) -> None:
        self._channels[key].engaged_user_ids.add(user_id)

    def record_bot_message(
        self,
        key: tuple[str, str],
        text: str,
        *,
        author_name: str = "Chubbie",
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        runtime = self._channels[key]
        runtime.messages.append(ConversationLine(author_name[:40], text[:500], now, True))
        runtime.recent_responses.append(text[:500])
        runtime.last_spoke_at = now
        self._trim(runtime, self.config.context_limit)

    def generate_event(
        self,
        *,
        key: tuple[str, str],
        state: CreatureState,
        event_type: str,
        current_message: str = "",
        demo_mode: bool = False,
        now: datetime | None = None,
    ) -> DialogueResult:
        now = now or datetime.now(timezone.utc)
        if event_type.upper() == "HATCH":
            self.reset_channel(key)
        runtime = self._channels[key]
        response = self._generate(
            state,
            runtime,
            current_message,
            event_type,
            demo_mode=demo_mode,
        )
        self.record_bot_message(key, response.text, author_name=state.name, now=now)
        return response

    def channel_diagnostics(
        self,
        key: tuple[str, str],
        channel_config: SocialChannelConfig,
        *,
        now: datetime | None = None,
    ) -> dict[str, object]:
        now = now or datetime.now(timezone.utc)
        runtime = self._channels[key]
        demo = channel_config.demo_active(now)
        active = self.demo_config if demo else self.config
        self._prune(runtime, now, active)
        one_hour_ago = now - timedelta(hours=1)
        while runtime.ambient_replies and runtime.ambient_replies[0] < one_hour_ago:
            runtime.ambient_replies.popleft()
        quota_used = len(runtime.demo_replies) if demo else len(runtime.ambient_replies)
        cooldown_remaining = 0
        if runtime.last_spoke_at:
            cooldown_remaining = max(
                0,
                active.ambient_cooldown_seconds - int((now - runtime.last_spoke_at).total_seconds()),
            )
        return {
            "demo_active": demo,
            "recent_human_messages": sum(not line.is_chubbie for line in runtime.messages),
            "last_ambient_at": (
                runtime.ambient_replies[-1].isoformat() if runtime.ambient_replies else None
            ),
            "cooldown_seconds": active.ambient_cooldown_seconds,
            "cooldown_remaining_seconds": cooldown_remaining,
            "quota_remaining": max(0, active.max_ambient_per_hour - quota_used),
            "quota_limit": active.max_ambient_per_hour,
            "minimum_messages": active.min_messages,
            "sample_probability": active.sample_probability,
            "last_decision": runtime.last_decision,
            "last_failure": runtime.last_failure,
        }

    def process_message(
        self,
        *,
        key: tuple[str, str],
        state: CreatureState,
        channel_config: SocialChannelConfig,
        text: str,
        author_name: str,
        author_id: str,
        mentioned: bool = False,
        replied_to_bot: bool = False,
        mentionable_user_ids: frozenset[str] = frozenset(),
        is_bot: bool = False,
        now: datetime | None = None,
    ) -> SocialOutcome:
        now = now or datetime.now(timezone.utc)
        clean = " ".join(text.strip().split())[:500]
        runtime = self._channels[key]
        if is_bot:
            return self._outcome(runtime, "silent", "bot message")
        if not channel_config.enabled:
            return self._outcome(runtime, "silent", "channel disabled")

        demo_mode = channel_config.demo_active(now)
        active = self.demo_config if demo_mode else self.config
        self._prune(runtime, now, active)
        if runtime.last_human_at and (now - runtime.last_human_at).total_seconds() > active.burst_gap_seconds:
            runtime.burst_id += 1
        runtime.last_human_at = now
        runtime.messages.append(ConversationLine(author_name[:40], clean, now, False, author_id))
        self._trim(runtime, active.context_limit)

        welcome_follow_up = bool(
            channel_config.welcome_active(now)
            and runtime.last_spoke_at
            and (now - runtime.last_spoke_at).total_seconds() <= 12
            and not SENSITIVE.search(clean)
            and not PROMPT_INJECTION.search(clean)
        )
        direct = (
            mentioned
            or replied_to_bot
            or welcome_follow_up
            or bool(CHUBBIE_NAME.search(clean))
            or bool(CAREGIVER_ADDRESS.search(clean))
        )
        if direct:
            previous = runtime.direct_user_replies.get(author_id)
            if previous and (now - previous).total_seconds() < active.direct_cooldown_seconds:
                return self._outcome(runtime, "silent", "direct cooldown")
            state_changed = False
            memory_match = REMEMBER_REQUEST.search(clean)
            if memory_match:
                try:
                    self.game_engine.remember_approved_fact(state, memory_match.group(1), now=now)
                    state_changed = True
                except ValueError as exc:
                    runtime.last_failure = str(exc)
            changed_topics = self.game_engine.note_topics(state, clean, amount=3)
            state_changed = state_changed or bool(changed_topics)
            runtime.engaged_user_ids.add(author_id)
            event_type = "REACTION" if replied_to_bot else "FOLLOW_UP" if welcome_follow_up else "DIRECT_MESSAGE"
            response = self._generate(state, runtime, clean, event_type, demo_mode=demo_mode)
            runtime.direct_user_replies[author_id] = now
            self.record_bot_message(key, response.text, author_name=state.name, now=now)
            reason = "reply to Chubbie" if replied_to_bot else "welcome follow-up" if welcome_follow_up else "addressed by name or mention"
            return self._outcome(
                runtime, "direct", reason, response, state_changed, demo_mode, author_id
            )

        if not channel_config.ambient_enabled:
            return self._outcome(runtime, "silent", "ambient off")
        if SENSITIVE.search(clean) or PROMPT_INJECTION.search(clean):
            return self._outcome(runtime, "silent", "sensitive or injection-like context")
        human_count = sum(not line.is_chubbie for line in runtime.messages)
        if human_count < active.min_messages:
            return self._outcome(
                runtime,
                "silent",
                f"not enough recent human messages ({human_count}/{active.min_messages})",
            )
        if runtime.last_spoke_at and (now - runtime.last_spoke_at).total_seconds() < active.ambient_cooldown_seconds:
            remaining = active.ambient_cooldown_seconds - int((now - runtime.last_spoke_at).total_seconds())
            return self._outcome(runtime, "silent", f"ambient cooldown ({max(1, remaining)}s remaining)")
        if runtime.last_ambient_burst_id == runtime.burst_id:
            return self._outcome(runtime, "silent", "already reacted to this conversation burst")

        one_hour_ago = now - timedelta(hours=1)
        while runtime.ambient_replies and runtime.ambient_replies[0] < one_hour_ago:
            runtime.ambient_replies.popleft()
        quota = runtime.demo_replies if demo_mode else runtime.ambient_replies
        if len(quota) >= active.max_ambient_per_hour:
            label = "demo session" if demo_mode else "hourly"
            return self._outcome(runtime, "silent", f"{label} ambient limit")
        roll = self.rng.random()
        if roll > active.sample_probability:
            return self._outcome(
                runtime,
                "silent",
                f"sample gate declined ({roll:.2f} > {active.sample_probability:.2f})",
            )

        response_intent = ""
        decision_reason = f"demo eligibility passed; sample {roll:.2f}"
        if not demo_mode:
            since = int((now - runtime.last_spoke_at).total_seconds()) if runtime.last_spoke_at else None
            evaluation = self.provider.evaluate_participation(state, tuple(runtime.messages), since)
            DIAGNOSTICS.decision(f"ambient should_speak={evaluation.should_speak}: {evaluation.reason}")
            if not evaluation.should_speak:
                return self._outcome(runtime, "silent", f"model declined: {evaluation.reason}")
            response_intent = evaluation.response_intent
            decision_reason = evaluation.reason

        try:
            response = self._generate(
                state,
                runtime,
                clean,
                "AMBIENT",
                response_intent=response_intent,
                demo_mode=demo_mode,
            )
        except Exception as exc:
            runtime.last_failure = f"{type(exc).__name__}: {exc}"[:200]
            raise
        runtime.ambient_replies.append(now)
        if demo_mode:
            runtime.demo_replies.append(now)
        runtime.last_ambient_burst_id = runtime.burst_id
        self.record_bot_message(key, response.text, author_name=state.name, now=now)
        candidate = next(
            (
                line.user_id
                for line in reversed(runtime.messages)
                if not line.is_chubbie
                and line.user_id in mentionable_user_ids
                and line.user_id in runtime.engaged_user_ids
            ),
            None,
        )
        return self._outcome(
            runtime, "ambient", decision_reason, response, False, demo_mode, candidate
        )

    def _generate(
        self,
        state: CreatureState,
        runtime: _ChannelRuntime,
        current_message: str,
        interaction_type: str,
        response_intent: str = "",
        demo_mode: bool = False,
    ) -> DialogueResult:
        context = tuple(runtime.messages)
        if interaction_type.upper() == "HATCH":
            context = ()
            memories = []
        else:
            memories = select_relevant_memories(state, " ".join(line.text for line in context[-8:]))
        if len(memories) > 1 and runtime.last_memory_text == memories[0].text:
            memories = memories[1:]
        runtime.last_memory_text = memories[0].text if memories else None
        return generate_character_response(
            state,
            context,
            current_message,
            interaction_type,
            memories,
            response_intent,
            provider=self.provider,
            demo_mode=demo_mode,
            recent_responses=tuple(runtime.recent_responses),
        )

    def _prune(self, runtime: _ChannelRuntime, now: datetime, active: SocialConfig) -> None:
        cutoff = now - timedelta(seconds=active.window_seconds)
        while runtime.messages and runtime.messages[0].timestamp < cutoff:
            runtime.messages.popleft()

    @staticmethod
    def _trim(runtime: _ChannelRuntime, limit: int) -> None:
        while len(runtime.messages) > limit:
            runtime.messages.popleft()

    @staticmethod
    def _remember_decision(runtime: _ChannelRuntime, text: str) -> None:
        runtime.last_decision = text[:240]
        DIAGNOSTICS.decision(text)
        logger.info("CHUBBIE social: %s", text)

    def _outcome(
        self,
        runtime: _ChannelRuntime,
        kind: str,
        reason: str,
        response: DialogueResult | None = None,
        state_changed: bool = False,
        demo_mode: bool = False,
        mention_candidate_id: str | None = None,
    ) -> SocialOutcome:
        self._remember_decision(runtime, f"{kind}: {reason}")
        return SocialOutcome(
            kind, reason, response, state_changed, demo_mode, mention_candidate_id
        )

