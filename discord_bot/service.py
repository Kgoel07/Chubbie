from __future__ import annotations

import threading
from datetime import datetime, timezone

from chubbie.chubbie_core.engine import ActionResult, CreatureEngine
from chubbie.chubbie_core.models import CreatureState
from chubbie.chubbie_core.serialization import import_snapshot

from .database import ChubbieRepository


class NurseryService:
    def __init__(self, repository: ChubbieRepository, engine: CreatureEngine) -> None:
        self.repository = repository
        self.engine = engine
        self._lock = threading.RLock()

    def hatch(self, guild_id: int, channel_id: int, user_key: str, name: str = "Chubbie") -> ActionResult:
        with self._lock:
            existing = self.repository.get_creature(guild_id, channel_id)
            if existing:
                return ActionResult(False, "This channel already has a Chubbie nursery.", existing)
            state = self.engine.new_egg(name)
            now = datetime.now(timezone.utc)
            state.participant_count = self.repository.register_participant(guild_id, channel_id, user_key, now)
            result = self.engine.hatch(state, now=now)
            self.repository.save_creature(guild_id, channel_id, state)
            return result

    def interact(
        self,
        guild_id: int,
        channel_id: int,
        user_key: str,
        action: str,
        expression: str | None = None,
        *,
        now: datetime | None = None,
    ) -> ActionResult | None:
        with self._lock:
            state = self.repository.get_creature(guild_id, channel_id)
            if state is None:
                return None
            now = now or datetime.now(timezone.utc)
            count = self.repository.register_participant(guild_id, channel_id, user_key, now)
            last = self.repository.get_last_action(guild_id, channel_id, user_key)
            result = self.engine.apply(
                state,
                action,
                actor_last_action_at=last,
                participant_count=count,
                expression=expression,
                now=now,
            )
            if result.accepted:
                self.repository.record_action(guild_id, channel_id, user_key, now)
                self.repository.save_creature(guild_id, channel_id, state)
            return result

    def adopt(self, guild_id: int, channel_id: int, user_key: str, payload: bytes) -> CreatureState:
        with self._lock:
            if self.repository.get_creature(guild_id, channel_id):
                raise ValueError("This channel already has a Chubbie. Reset it before adopting another.")
            state = import_snapshot(payload)
            now = datetime.now(timezone.utc)
            actual = self.repository.register_participant(guild_id, channel_id, user_key, now)
            state.participant_count = max(state.participant_count, actual)
            self.repository.save_creature(guild_id, channel_id, state)
            return state


def can_reset(*, is_administrator: bool) -> bool:
    return bool(is_administrator)

