#!/usr/bin/env python3
"""Deterministic local interface used by the Cubbie Agent Skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SKILL_ROOT.parent
for candidate in (str(SKILL_ROOT), str(PROJECT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from chubbie_core.engine import CreatureEngine, ProgressionConfig, sanitize_display_text
from chubbie_core.models import CreatureState
from chubbie_core.serialization import export_snapshot, load_state, save_state
from chubbie_core.stories import choose_story


def default_state_path() -> Path:
    return Path(os.path.expanduser("~")) / ".config" / "chubbie" / "state.json"


def sample_path() -> Path:
    return SKILL_ROOT / "assets" / "sample_state.json"


def age_text(state: CreatureState, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    start = state.hatched_at or state.created_at
    seconds = max(0, int((now - start).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def status_text(state: CreatureState, engine: CreatureEngine) -> str:
    t = state.traits
    return (
        f"{state.name} — {state.stage.value.title()} ({state.archetype.value.title()})\n"
        f"Mood: {state.mood} | Energy: {state.energy}\n"
        f"Affection {t.affection} · Chaos {t.chaos} · Curiosity {t.curiosity} · Nerdiness {t.nerdiness}\n"
        f"Age: {age_text(state)} | {engine.progress_text(state)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raise a persistent fictional Chubbie.")
    parser.add_argument("--sample", action="store_true", help="Use bundled demo state without saving changes.")
    parser.add_argument("--state", type=Path, help="Override the saved state path.")
    parser.add_argument("--demo", action="store_true", help="Use clearly marked accelerated thresholds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    commands = parser.add_subparsers(dest="command", required=True)
    hatch = commands.add_parser("hatch")
    hatch.add_argument("--name", default="Chubbie")
    for name in ("feed", "play", "care", "status", "memories", "evolution", "story"):
        commands.add_parser(name)
    talk = commands.add_parser("talk")
    talk.add_argument("--message", default="")
    teach = commands.add_parser("teach")
    teach.add_argument("expression")
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    reset = commands.add_parser("reset")
    reset.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ProgressionConfig.demo() if args.demo else ProgressionConfig()
    engine = CreatureEngine(config)
    state_path = args.state or default_state_path()
    state = load_state(sample_path() if args.sample else state_path)
    message = ""
    event: dict[str, object] | None = None
    changed = False
    ok = True

    if args.command == "hatch":
        if state.stage.value == "EGG":
            state.name = sanitize_display_text(" ".join(args.name.strip().split())[:32]) or "Chubbie"
        result = engine.hatch(state)
        message, changed = result.message, result.accepted
        event = result.event
        ok = result.accepted
    elif args.command in {"feed", "play", "care", "teach"}:
        result = engine.apply(
            state,
            args.command,
            actor_last_action_at=state.last_interaction_at,
            expression=getattr(args, "expression", None),
        )
        message, changed = result.message, result.accepted
        event = result.event
        ok = result.accepted
    elif args.command == "talk":
        message = "talk context ready."
        state.action_counts["talk"] = state.action_counts.get("talk", 0) + 1
        engine.note_topics(state, args.message, amount=3)
        event = {"action": "talk", "success": True, "stage": state.stage.value, "mood": state.mood}
        changed = True
    elif args.command == "status":
        message = status_text(state, engine)
    elif args.command == "memories":
        memories = state.memories[-8:]
        message = "No major memories yet." if not memories else "\n".join(f"- {item.text}" for item in memories)
    elif args.command == "evolution":
        history = "\n".join(
            f"- {item.from_stage.value.title()} → {item.to_stage.value.title()}: {item.archetype.value.title()}"
            for item in state.evolution_history
        )
        message = f"Current archetype: {state.archetype.value.title()}\n{history or engine.progress_text(state)}"
    elif args.command == "story":
        story = choose_story(state)
        message = f"{story.title}\n{story.prompt}\n" + "\n".join(
            f"{index}. {choice}" for index, choice in enumerate(story.choices, 1)
        )
    elif args.command == "export":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(export_snapshot(state), encoding="utf-8")
        message = f"Portable snapshot written to {args.output}"
    elif args.command == "reset":
        if not args.confirm:
            message = "Reset refused. Run again with --confirm if you truly want a fresh egg."
            changed = False
        else:
            state = engine.new_egg()
            message = "Chubbie reset to a fresh egg. This cannot be undone from this file."
            changed = True

    if changed and not args.sample:
        save_state(state_path, state)
    if args.json:
        dialogue_context = {
            "name": state.name,
            "developmental_stage": state.stage.value,
            "archetype": state.archetype.value,
            "mood": state.mood,
            "energy_band": "low" if state.energy < 30 else "high" if state.energy > 70 else "steady",
            "strongest_interests": sorted(state.topic_affinities.items(), key=lambda item: item[1], reverse=True)[:5],
            "learned_expressions": state.learned_expressions[-4:],
            "relevant_memories": [memory.text for memory in state.memories[-4:]],
            "user_message": getattr(args, "message", "")[:500],
        }
        print(json.dumps({
            "ok": ok,
            "system_message": message,
            "event": event,
            "dialogue_context": dialogue_context,
            "state": state.model_dump(mode="json"),
        }, ensure_ascii=False))
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

