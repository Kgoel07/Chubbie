from __future__ import annotations

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from chubbie.chubbie_core.evolution import select_archetype
from chubbie.chubbie_core.models import Archetype, CreatureState, LifeStage


def test_evolves_at_configured_thresholds_and_group_gate() -> None:
    engine = CreatureEngine(ProgressionConfig(toddler=2, teenager=4, adult=6, cooldown_seconds=0))
    state = engine.new_egg()
    engine.hatch(state)
    engine.apply(state, "play", participant_count=1)
    engine.apply(state, "play", participant_count=1)
    assert state.stage == LifeStage.TODDLER
    engine.apply(state, "play", participant_count=1)
    engine.apply(state, "play", participant_count=1)
    assert state.stage == LifeStage.TODDLER
    engine.apply(state, "care", participant_count=2)
    assert state.stage == LifeStage.TEENAGER
    engine.apply(state, "care", participant_count=2)
    assert state.stage == LifeStage.ADULT
    assert len(state.evolution_history) == 3


def test_archetype_selection_is_deterministic() -> None:
    state = CreatureState(stage=LifeStage.TEENAGER, total_interactions=20, participant_count=2)
    winners = {select_archetype(state.model_copy(deep=True)) for _ in range(20)}
    assert len(winners) == 1


def test_interaction_history_changes_archetype() -> None:
    engine = CreatureEngine(ProgressionConfig(toddler=999, cooldown_seconds=0))
    state = CreatureState(stage=LifeStage.BABY)
    for phrase in ("python bug", "git code", "algorithm compiler"):
        engine.apply(state, "teach", expression=phrase)
    assert select_archetype(state) == Archetype.PROCRASTISAURUS_REX

