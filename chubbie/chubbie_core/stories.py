from __future__ import annotations

from dataclasses import dataclass

from .models import Archetype, CreatureState


@dataclass(frozen=True)
class StoryPrompt:
    title: str
    prompt: str
    choices: tuple[str, str, str]


STORIES = {
    Archetype.PROCRASTISAURUS_REX: (
        StoryPrompt("Startup Emergency", "Chubbie founded a startup but forgot the product. What should it build?", ("Homework debugger", "Nap-as-a-service", "AI for finding free pizza")),
        StoryPrompt("University Decision", "Three schools offered Chubbie a suspicious scholarship. Where should it go?", ("MIT for Applied Procrastination", "ASU for Professional Chaos", "Harvard for Advanced Memes")),
    ),
    Archetype.BRAINROT_GOBLIN: (
        StoryPrompt("Career Pivot", "Chubbie quit being a pet to pursue an imaginary career. Pick the job.", ("Meme archaeologist", "Campus cryptid", "Vibes compliance officer")),
        StoryPrompt("Ridiculous Hobby", "Chubbie needs a harmless new hobby before it reorganizes the ceiling tiles.", ("Competitive spoon collecting", "Extreme origami", "Interpretive debugging")),
    ),
    Archetype.EMOTIONAL_SUPPORT_DRAGON: (
        StoryPrompt("Family Challenge", "Chubbie wants the group to do one tiny nice thing today.", ("Compliment a friend", "Share a campus event", "Hydration roll call")),
        StoryPrompt("Club Application", "Chubbie can join one campus club as its extremely eager mascot.", ("Robotics club", "Volunteer club", "Board game club")),
    ),
    Archetype.EXISTENTIAL_PHILOSOPHER: (
        StoryPrompt("Existential Crisis", "Chubbie discovered calendars. What is time, family?", ("A deadline with branding", "Soup for clocks", "A group project nobody leads")),
        StoryPrompt("Important Research", "Chubbie received funding for one philosophical study.", ("Do pigeons have office hours?", "Can a burrito be a syllabus?", "Is free pizza ever truly free?")),
    ),
}


def choose_story(state: CreatureState) -> StoryPrompt:
    archetype = state.archetype
    if archetype == Archetype.FORMING:
        archetype = (
            Archetype.BRAINROT_GOBLIN
            if state.traits.chaos >= state.traits.affection
            else Archetype.EMOTIONAL_SUPPORT_DRAGON
        )
    options = STORIES[archetype]
    return options[(state.total_interactions + len(state.memories)) % len(options)]

