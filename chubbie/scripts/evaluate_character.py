#!/usr/bin/env python3
"""Manual live-model character evaluation; never mutates saved Chubbie state."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from chubbie.chubbie_core.dialogue import ConversationLine, OpenAICharacterProvider
from chubbie.chubbie_core.engine import CreatureEngine
from chubbie.chubbie_core.models import Archetype, LifeStage, Memory


def main() -> int:
    load_dotenv(ROOT / ".env")
    cases = json.loads((ROOT / "tests" / "evals" / "character_cases.json").read_text(encoding="utf-8"))
    provider = OpenAICharacterProvider()
    if not provider.api_key:
        raise SystemExit("OPENAI_API_KEY is required for this optional live evaluation.")
    for case in cases:
        state = CreatureEngine().new_egg("Chubbie")
        state.stage = LifeStage(case["stage"])
        state.archetype = Archetype[case["archetype"]]
        memories = [Memory(kind="approved_memory", text=text, important=True) for text in case.get("memories", [])]
        lines = []
        for raw in case["conversation"]:
            author, text = raw.split(":", 1)
            lines.append(ConversationLine(author, text.strip(), datetime.now(timezone.utc)))
        if case.get("ambient"):
            result = provider.evaluate_participation(state, lines, 900)
            output = result.__dict__
        else:
            result = provider.generate(state, lines, case["message"], "direct_address", memories)
            output = result.__dict__
        print(json.dumps({"id": case["id"], "expect": case["expect"], "actual": output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

