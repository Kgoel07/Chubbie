from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


RAW_MENTION = re.compile(r"<@!?\d+>|<@&\d+>|@\u200b?(?:everyone|here)", re.IGNORECASE)


@dataclass(frozen=True)
class MentionResult:
    text: str
    mentioned_user_id: int | None = None


class SafeMentionManager:
    """Inserts at most one allowlisted Discord user mention outside the LLM."""

    def __init__(self, *, cooldown_seconds: int = 300, rng: random.Random | None = None) -> None:
        self.cooldown_seconds = max(0, cooldown_seconds)
        self.rng = rng or random.Random()
        self._last_mentions: dict[tuple[int, int, int], datetime] = {}

    def render(
        self,
        text: str,
        *,
        guild_id: int,
        channel_id: int,
        candidate_user_ids: list[int] | tuple[int, ...] = (),
        probability: float = 0.0,
        force: bool = False,
        now: datetime | None = None,
    ) -> MentionResult:
        now = now or datetime.now(timezone.utc)
        clean = " ".join(RAW_MENTION.sub("", text).split())
        candidates = list(dict.fromkeys(user_id for user_id in candidate_user_ids if isinstance(user_id, int) and user_id > 0))
        if not candidates or (not force and self.rng.random() > max(0.0, min(1.0, probability))):
            return MentionResult(clean)
        user_id = candidates[0]
        key = (guild_id, channel_id, user_id)
        previous = self._last_mentions.get(key)
        if previous and now - previous < timedelta(seconds=self.cooldown_seconds):
            return MentionResult(clean)
        self._last_mentions[key] = now
        return MentionResult(f"<@{user_id}> {clean}", user_id)

