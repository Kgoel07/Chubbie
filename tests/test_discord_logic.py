from __future__ import annotations

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from discord_bot.database import ChubbieRepository
from discord_bot.service import NurseryService, can_reset


def service(tmp_path):
    repository = ChubbieRepository(tmp_path / "chubbie.sqlite3")
    engine = CreatureEngine(ProgressionConfig(toddler=2, teenager=4, adult=6, cooldown_seconds=0))
    return repository, NurseryService(repository, engine)


def test_separate_channels_have_independent_creatures(tmp_path) -> None:
    repository, nursery = service(tmp_path)
    nursery.hatch(1, 10, "a", "Byte")
    nursery.hatch(1, 20, "b", "Mochi")
    nursery.interact(1, 10, "a", "play")
    left = repository.get_creature(1, 10)
    right = repository.get_creature(1, 20)
    assert left and right
    assert left.name == "Byte" and right.name == "Mochi"
    assert left.total_interactions == 1 and right.total_interactions == 0


def test_database_state_survives_repository_restart(tmp_path) -> None:
    path = tmp_path / "chubbie.sqlite3"
    first = ChubbieRepository(path)
    nursery = NurseryService(first, CreatureEngine(ProgressionConfig(cooldown_seconds=0)))
    nursery.hatch(5, 6, "parent", "Persisto")
    nursery.interact(5, 6, "parent", "care")
    second = ChubbieRepository(path)
    loaded = second.get_creature(5, 6)
    assert loaded and loaded.name == "Persisto" and loaded.total_interactions == 1


def test_distinct_users_are_counted_for_group_evolution(tmp_path) -> None:
    repository, nursery = service(tmp_path)
    nursery.hatch(1, 1, "alex")
    nursery.interact(1, 1, "alex", "play")
    nursery.interact(1, 1, "alex", "play")
    nursery.interact(1, 1, "alex", "play")
    nursery.interact(1, 1, "sam", "care")
    state = repository.get_creature(1, 1)
    assert state and state.participant_count == 2
    assert state.stage.value == "TEENAGER"


def test_reset_authorization_is_explicit() -> None:
    assert can_reset(is_administrator=True)
    assert not can_reset(is_administrator=False)

