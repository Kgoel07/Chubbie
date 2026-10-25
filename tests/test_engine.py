from __future__ import annotations

from datetime import datetime, timedelta, timezone

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from chubbie.chubbie_core.models import LifeStage


NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def hatched(engine: CreatureEngine | None = None):
    engine = engine or CreatureEngine()
    state = engine.new_egg()
    result = engine.hatch(state, now=NOW)
    assert result.accepted
    return engine, state


def test_new_creature_has_required_initial_state() -> None:
    state = CreatureEngine().new_egg()
    assert state.name == "Chubbie"
    assert state.stage == LifeStage.EGG
    assert state.mood == "Curious"
    assert state.energy == 80
    assert state.traits.model_dump() == {
        "affection": 50,
        "chaos": 30,
        "curiosity": 50,
        "nerdiness": 50,
    }


def test_hatching_moves_egg_to_baby_once() -> None:
    engine = CreatureEngine()
    state = engine.new_egg("Byte")
    assert engine.hatch(state, now=NOW).accepted
    assert state.stage == LifeStage.BABY
    assert state.hatched_at == NOW
    assert not engine.hatch(state, now=NOW).accepted


def test_feeding_and_playing_update_stats() -> None:
    engine, state = hatched(CreatureEngine(ProgressionConfig(cooldown_seconds=0)))
    feed = engine.apply(state, "feed", now=NOW)
    assert feed.accepted
    assert state.energy == 95
    assert state.traits.affection == 54
    play = engine.apply(state, "play", now=NOW)
    assert play.accepted
    assert state.energy == 87
    assert state.traits.affection == 62
    assert state.traits.chaos == 37


def test_stats_are_clamped_to_zero_and_one_hundred() -> None:
    engine, state = hatched(CreatureEngine(ProgressionConfig(cooldown_seconds=0, toddler=999)))
    state.energy = 99
    state.traits.affection = 99
    for _ in range(30):
        engine.apply(state, "feed", now=NOW)
    assert state.energy == 100
    assert state.traits.affection == 100
    for _ in range(30):
        engine.apply(state, "play", now=NOW)
    assert state.energy == 0
    assert 0 <= state.traits.chaos <= 100


def test_cooldown_rejects_spam_without_progress() -> None:
    engine, state = hatched()
    first = engine.apply(state, "feed", actor_last_action_at=None, now=NOW)
    before = state.total_interactions
    second = engine.apply(state, "feed", actor_last_action_at=NOW, now=NOW + timedelta(seconds=2))
    assert first.accepted
    assert not second.accepted
    assert state.total_interactions == before


def test_teach_rejects_private_or_unsafe_text() -> None:
    engine, state = hatched()
    result = engine.apply(state, "teach", expression="api_key=definitely-secret", now=NOW)
    assert not result.accepted
    assert state.learned_expressions == []

