#!/usr/bin/env python3
"""Read-only local simulation of Discord participation gates plus live character AI."""

from __future__ import annotations

import sys
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from chubbie.chubbie_core.dialogue import OpenAICharacterProvider
from chubbie.chubbie_core.engine import CreatureEngine
from discord_bot.social import SocialChannelConfig, SocialConfig, SocialParticipationEngine


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(ROOT / ".env")
    provider = OpenAICharacterProvider()
    if not provider.api_key:
        raise SystemExit("OPENAI_API_KEY is required for the optional live simulation.")
    game = CreatureEngine()
    state = game.new_egg("Chubbie")
    game.hatch(state)
    social = SocialParticipationEngine(provider, rng=random.Random(1), game_engine=game)
    start = datetime.now(timezone.utc)
    config = SocialChannelConfig(
        enabled=True,
        ambient_enabled=True,
        welcome_until=start + timedelta(seconds=90),
        demo_expires_at=start + timedelta(seconds=90),
    )
    social.start_demo(("demo-guild", "nursery"))
    entrance = social.generate_event(
        key=("demo-guild", "nursery"),
        state=state,
        event_type="HATCH",
        current_message="Chubbie just entered the nursery.",
        demo_mode=True,
        now=start,
    )
    print(f"Chubbie: {entrance.text}")
    transcript = [
        ("Mina", "WHO IS THIS", False, True, 2),
        ("Mina", "I finally understand regular expressions", False, False, 30),
        ("Dev", "regex still looks like wizard punctuation to me", False, False, 32),
        ("Dev", "my private medical diagnosis is scary", False, False, 50),
    ]
    for index, (author, text, mentioned, replied, offset) in enumerate(transcript):
        outcome = social.process_message(
            key=("demo-guild", "nursery"),
            state=state,
            channel_config=config,
            text=text,
            author_name=author,
            author_id=str(index % 2),
            mentioned=mentioned,
            replied_to_bot=replied,
            now=start + timedelta(seconds=offset),
        )
        print(f"{author}: {text}")
        print(f"  decision: {outcome.kind} ({outcome.reason})")
        if outcome.response:
            print(f"Chubbie: {outcome.response.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

