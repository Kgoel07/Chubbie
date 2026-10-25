from __future__ import annotations

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from chubbie.chubbie_core.dialogue import OpenAICharacterProvider
from discord_bot.commands import ChubbieCommands
from discord_bot.database import ChubbieRepository
from discord_bot.mentions import SafeMentionManager
from discord_bot.service import NurseryService, can_reset
from discord_bot.social import SocialParticipationEngine
from discord_bot.voting import VotingService


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


def test_hatch_single_step_enables_only_current_nursery_and_starts_fresh(tmp_path) -> None:
    repository, nursery = service(tmp_path)
    result = nursery.hatch_and_enable(1, 10, "hatcher", "Nova", ambient=True)
    assert result.accepted
    assert result.state.stage.value == "BABY"
    assert repository.get_channel_config(1, 10).enabled
    assert repository.get_channel_config(1, 10).ambient_enabled
    assert not repository.get_channel_config(1, 20).enabled
    assert all(memory.kind == "hatching" for memory in result.state.memories)


def test_repeated_single_step_hatch_preserves_existing_creature(tmp_path) -> None:
    repository, nursery = service(tmp_path)
    first = nursery.hatch_and_enable(1, 10, "hatcher", "Nova")
    nursery.interact(1, 10, "hatcher", "care")
    before = repository.get_creature(1, 10).model_dump_json()
    second = nursery.hatch_and_enable(1, 10, "other", "Replacement")
    assert first.accepted and not second.accepted
    assert repository.get_creature(1, 10).model_dump_json() == before


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


def test_channel_chat_and_ambient_opt_ins_persist(tmp_path) -> None:
    path = tmp_path / "chubbie.sqlite3"
    first = ChubbieRepository(path)
    assert not first.get_channel_config(1, 2).enabled
    first.set_channel_enabled(1, 2, True)
    first.set_channel_ambient(1, 2, True)
    saved = ChubbieRepository(path).get_channel_config(1, 2)
    assert saved.enabled and saved.ambient_enabled
    disabled = first.set_channel_enabled(1, 2, False)
    assert not disabled.enabled and not disabled.ambient_enabled


def test_required_configuration_commands_are_chubbie_subcommands(tmp_path) -> None:
    repository = ChubbieRepository(tmp_path / "chubbie.sqlite3")
    engine = CreatureEngine()
    provider = OpenAICharacterProvider(api_key="test-only")
    group = ChubbieCommands(
        repository,
        NurseryService(repository, engine),
        VotingService(repository, engine),
        SocialParticipationEngine(provider),
        provider,
        SafeMentionManager(),
    )
    names = {command.name for command in group.commands}
    assert {"enable", "disable", "ambient", "mentions", "personality", "debug", "demo", "surprise"} <= names


def test_demo_expiration_is_persisted_and_cleared(tmp_path) -> None:
    from datetime import datetime, timedelta, timezone

    repository = ChubbieRepository(tmp_path / "chubbie.sqlite3")
    repository.set_channel_enabled(1, 2, True)
    repository.set_channel_ambient(1, 2, True)
    expires = datetime.now(timezone.utc) + timedelta(seconds=90)
    repository.start_demo(1, 2, expires)
    assert ChubbieRepository(repository.path).get_channel_config(1, 2).demo_expires_at == expires
    repository.list_active_demos(now=expires + timedelta(seconds=1))
    assert repository.get_channel_config(1, 2).demo_expires_at is None


def test_per_nursery_mention_opt_in_is_persisted(tmp_path) -> None:
    repository = ChubbieRepository(tmp_path / "chubbie.sqlite3")
    repository.set_mention_preference(1, 2, "123", True)
    repository.set_mention_preference(1, 2, "999", False)
    reloaded = ChubbieRepository(repository.path)
    assert reloaded.get_mentionable_users(1, 2) == frozenset({"123"})
    assert not reloaded.get_mentionable_users(1, 3)

