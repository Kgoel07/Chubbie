from __future__ import annotations

from dataclasses import dataclass

from .models import Archetype, CreatureState, EvolutionRecord, LifeStage, utc_now


TIE_ORDER = (
    Archetype.PROCRASTISAURUS_REX,
    Archetype.BRAINROT_GOBLIN,
    Archetype.EMOTIONAL_SUPPORT_DRAGON,
    Archetype.EXISTENTIAL_PHILOSOPHER,
)


PROGRAMMING_WORDS = {
    "code",
    "coding",
    "python",
    "bug",
    "debug",
    "git",
    "javascript",
    "compiler",
    "algorithm",
}


def archetype_scores(state: CreatureState) -> dict[Archetype, int]:
    actions = state.action_counts
    expression_text = " ".join(state.learned_expressions).lower()
    programming_hits = sum(word in expression_text for word in PROGRAMMING_WORDS)
    return {
        Archetype.PROCRASTISAURUS_REX: (
            state.traits.nerdiness * 2
            + state.traits.curiosity
            + actions.get("teach", 0) * 5
            + programming_hits * 18
        ),
        Archetype.BRAINROT_GOBLIN: (
            state.traits.chaos * 2
            + actions.get("play", 0) * 7
            + len(state.learned_expressions) * 4
        ),
        Archetype.EMOTIONAL_SUPPORT_DRAGON: (
            state.traits.affection * 2
            + actions.get("care", 0) * 9
            + actions.get("feed", 0) * 4
        ),
        Archetype.EXISTENTIAL_PHILOSOPHER: (
            state.traits.curiosity * 2
            + actions.get("talk", 0) * 4
            + actions.get("care", 0) * 2
        ),
    }


def select_archetype(state: CreatureState) -> Archetype:
    scores = archetype_scores(state)
    return max(TIE_ORDER, key=lambda item: (scores[item], -TIE_ORDER.index(item)))


@dataclass(frozen=True)
class Thresholds:
    toddler: int = 8
    teenager: int = 20
    adult: int = 40


def eligible_next_stage(state: CreatureState, thresholds: Thresholds) -> LifeStage | None:
    if state.stage == LifeStage.BABY and state.total_interactions >= thresholds.toddler:
        return LifeStage.TODDLER
    if (
        state.stage == LifeStage.TODDLER
        and state.total_interactions >= thresholds.teenager
        and state.participant_count >= 2
    ):
        return LifeStage.TEENAGER
    if (
        state.stage == LifeStage.TEENAGER
        and state.total_interactions >= thresholds.adult
        and state.participant_count >= 2
    ):
        return LifeStage.ADULT
    return None


def evolve_once(state: CreatureState, thresholds: Thresholds) -> EvolutionRecord | None:
    next_stage = eligible_next_stage(state, thresholds)
    if next_stage is None:
        return None
    previous = state.stage
    state.stage = next_stage
    state.archetype = select_archetype(state)
    record = EvolutionRecord(
        from_stage=previous,
        to_stage=next_stage,
        archetype=state.archetype,
        reason=(
            f"{state.total_interactions} valid interactions from "
            f"{state.participant_count} participant(s) shaped this form."
        ),
        evolved_at=utc_now(),
    )
    state.evolution_history.append(record)
    return record

