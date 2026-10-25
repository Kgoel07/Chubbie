from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from chubbie.chubbie_core.engine import CreatureEngine

from .database import ChubbieRepository, PollRecord


@dataclass(frozen=True)
class VoteResult:
    accepted: bool
    message: str
    counts: tuple[int, ...]


@dataclass(frozen=True)
class PollOutcome:
    poll: PollRecord
    winning_index: int
    winning_choice: str
    counts: tuple[int, ...]


class VotingService:
    def __init__(self, repository: ChubbieRepository, engine: CreatureEngine) -> None:
        self.repository = repository
        self.engine = engine

    def start(
        self,
        guild_id: int,
        channel_id: int,
        title: str,
        prompt: str,
        choices: tuple[str, ...],
        *,
        duration_seconds: int = 60,
        now: datetime | None = None,
    ) -> PollRecord:
        now = now or datetime.now(timezone.utc)
        current = self.repository.get_open_poll(guild_id, channel_id)
        if current and current.expires_at > now:
            raise ValueError("This nursery already has an emergency meeting in progress.")
        if current:
            self.close(current.id, now=now)
        if not 2 <= len(choices) <= 5:
            raise ValueError("A group decision needs 2 to 5 choices.")
        return self.repository.create_poll(
            guild_id, channel_id, title, prompt, choices, now + timedelta(seconds=duration_seconds)
        )

    def vote(
        self, poll_id: str, user_key: str, choice_index: int, *, now: datetime | None = None
    ) -> VoteResult:
        now = now or datetime.now(timezone.utc)
        poll = self.repository.get_poll(poll_id)
        if poll is None:
            return VoteResult(False, "That meeting no longer exists.", ())
        if poll.closed_at is not None or now >= poll.expires_at:
            return VoteResult(False, "Voting is closed. Democracy has logged off.", tuple(self.repository.vote_counts(poll_id, len(poll.choices))))
        if not 0 <= choice_index < len(poll.choices):
            return VoteResult(False, "That choice escaped the ballot.", ())
        try:
            self.repository.add_vote(poll_id, user_key, choice_index, now)
        except sqlite3.IntegrityError:
            return VoteResult(False, "One vote each. Chubbie respects democracy and primary keys.", tuple(self.repository.vote_counts(poll_id, len(poll.choices))))
        counts = tuple(self.repository.vote_counts(poll_id, len(poll.choices)))
        return VoteResult(True, f'Vote recorded for "{poll.choices[choice_index]}".', counts)

    def close(self, poll_id: str, *, now: datetime | None = None) -> PollOutcome:
        now = now or datetime.now(timezone.utc)
        poll = self.repository.get_poll(poll_id)
        if poll is None:
            raise ValueError("Poll not found.")
        counts = tuple(self.repository.vote_counts(poll.id, len(poll.choices)))
        # Deterministic tie handling: the earliest listed choice wins.
        winner = max(range(len(poll.choices)), key=lambda index: (counts[index], -index))
        closed = self.repository.close_poll(poll.id, winner, now)
        if closed:
            state = self.repository.get_creature(poll.guild_id, poll.channel_id)
            if state:
                self.engine.record_group_decision(state, poll.prompt, poll.choices[winner], sum(counts), now=now)
                self.repository.save_creature(poll.guild_id, poll.channel_id, state)
        updated = self.repository.get_poll(poll.id) or poll
        final_winner = updated.winning_index if updated.winning_index is not None else winner
        return PollOutcome(updated, final_winner, poll.choices[final_winner], counts)

