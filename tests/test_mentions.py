from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from discord_bot.mentions import SafeMentionManager


def test_only_allowlisted_user_id_can_be_inserted() -> None:
    manager = SafeMentionManager(cooldown_seconds=60, rng=random.Random(1))
    result = manager.render(
        "<@999999> hi @everyone <@&4444> 😭",
        guild_id=1,
        channel_id=2,
        candidate_user_ids=[12345],
        force=True,
    )
    assert result.text.startswith("<@12345>")
    assert "999999" not in result.text
    assert "@everyone" not in result.text
    assert "<@&" not in result.text
    assert result.mentioned_user_id == 12345


def test_nonparticipant_mentions_are_removed_without_ping() -> None:
    result = SafeMentionManager().render(
        "hello <@777> 🐣",
        guild_id=1,
        channel_id=2,
        candidate_user_ids=[],
        force=True,
    )
    assert result.mentioned_user_id is None
    assert "<@" not in result.text


def test_per_user_mention_cooldown_prevents_repeat_ping() -> None:
    manager = SafeMentionManager(cooldown_seconds=300)
    now = datetime.now(timezone.utc)
    first = manager.render(
        "hi 🐣", guild_id=1, channel_id=2, candidate_user_ids=[123], force=True, now=now
    )
    second = manager.render(
        "again 🥺",
        guild_id=1,
        channel_id=2,
        candidate_user_ids=[123],
        force=True,
        now=now + timedelta(seconds=10),
    )
    later = manager.render(
        "later 🍼",
        guild_id=1,
        channel_id=2,
        candidate_user_ids=[123],
        force=True,
        now=now + timedelta(seconds=301),
    )
    assert first.mentioned_user_id == 123
    assert second.mentioned_user_id is None
    assert later.mentioned_user_id == 123
