from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from discord_bot.database import ChubbieRepository
from discord_bot.service import NurseryService


@dataclass(frozen=True)
class GroupEvent:
    group_id: str
    actor_id: str
    action: str
    text: str | None = None


@dataclass(frozen=True)
class OutboundMessage:
    group_id: str
    text: str


class GroupPlatformAdapter(Protocol):
    """Boundary a future official WhatsApp Cloud API adapter would implement."""

    def handle_event(self, event: GroupEvent) -> OutboundMessage: ...


class DevelopmentWhatsAppSimulator:
    """Local event simulator. It does not connect to WhatsApp or impersonate a client."""

    def __init__(self, database_path: str | Path, *, demo: bool = False) -> None:
        self.repository = ChubbieRepository(database_path)
        engine = CreatureEngine(ProgressionConfig.demo() if demo else ProgressionConfig())
        self.nursery = NurseryService(self.repository, engine)

    @staticmethod
    def _ids(group_id: str) -> tuple[int, int]:
        # Stable non-secret local namespaces for simulation only.
        value = sum((index + 1) * ord(char) for index, char in enumerate(group_id))
        return 0, value

    def handle_event(self, event: GroupEvent) -> OutboundMessage:
        guild_id, channel_id = self._ids(event.group_id)
        if event.action == "hatch":
            result = self.nursery.hatch(guild_id, channel_id, event.actor_id, event.text or "Chubbie")
        elif event.action in {"feed", "play", "care", "teach"}:
            result = self.nursery.interact(
                guild_id,
                channel_id,
                event.actor_id,
                event.action,
                event.text if event.action == "teach" else None,
            )
            if result is None:
                return OutboundMessage(event.group_id, "No simulated Chubbie yet. Run hatch first.")
        else:
            return OutboundMessage(event.group_id, "Simulator actions: hatch, feed, play, care, teach.")
        return OutboundMessage(event.group_id, result.message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Development-only WhatsApp group event simulator.")
    parser.add_argument("action", choices=("hatch", "feed", "play", "care", "teach"))
    parser.add_argument("--group", default="demo-group")
    parser.add_argument("--actor", default="student-1")
    parser.add_argument("--text")
    parser.add_argument("--database", type=Path, default=Path("data/whatsapp-simulator.sqlite3"))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    simulator = DevelopmentWhatsAppSimulator(args.database, demo=args.demo)
    output = simulator.handle_event(GroupEvent(args.group, args.actor, args.action, args.text))
    print(f"[SIMULATED {output.group_id}] {output.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

