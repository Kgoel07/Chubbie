from __future__ import annotations

from datetime import datetime, timedelta, timezone

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from discord_bot.database import ChubbieRepository
from discord_bot.service import NurseryService
from discord_bot.voting import VotingService


NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def setup_services(tmp_path):
    repository = ChubbieRepository(tmp_path / "polls.sqlite3")
    engine = CreatureEngine(ProgressionConfig(cooldown_seconds=0))
    nursery = NurseryService(repository, engine)
    nursery.hatch(1, 2, "parent")
    return repository, VotingService(repository, engine)


def test_each_user_votes_once_and_ties_are_deterministic(tmp_path) -> None:
    repository, voting = setup_services(tmp_path)
    poll = voting.start(1, 2, "Emergency", "Pick one", ("First", "Second", "Third"), now=NOW)
    assert voting.vote(poll.id, "alex", 1, now=NOW).accepted
    duplicate = voting.vote(poll.id, "alex", 0, now=NOW)
    assert not duplicate.accepted
    assert voting.vote(poll.id, "sam", 0, now=NOW).accepted
    outcome = voting.close(poll.id, now=NOW + timedelta(seconds=61))
    assert outcome.winning_index == 0
    assert repository.get_creature(1, 2).memories[-1].kind == "group_vote"


def test_votes_cannot_change_after_poll_closes(tmp_path) -> None:
    _, voting = setup_services(tmp_path)
    poll = voting.start(1, 2, "Emergency", "Pick one", ("A", "B"), now=NOW)
    voting.close(poll.id, now=NOW + timedelta(seconds=1))
    assert not voting.vote(poll.id, "late", 1, now=NOW + timedelta(seconds=2)).accepted

