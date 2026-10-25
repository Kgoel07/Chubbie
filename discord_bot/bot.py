from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig

from .commands import ChubbieCommands
from .database import ChubbieRepository
from .interactions import DecisionView, poll_text
from .service import NurseryService
from .voting import VotingService


class ChubbieBot(commands.Bot):
    def __init__(self, repository: ChubbieRepository, engine: CreatureEngine) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.repository = repository
        self.engine = engine
        self.nursery = NurseryService(repository, engine)
        self.voting = VotingService(repository, engine)

    async def setup_hook(self) -> None:
        self.tree.add_command(ChubbieCommands(self.repository, self.nursery, self.voting))
        for poll in self.repository.list_open_polls():
            if poll.message_id is not None:
                self.add_view(
                    DecisionView(poll, self.repository, self.voting, timeout=None),
                    message_id=poll.message_id,
                )
        self.poll_reaper.start()
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info("Synced %d commands to development guild %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logging.info("Synced %d global commands", len(synced))

    async def close(self) -> None:
        self.poll_reaper.cancel()
        await super().close()

    @tasks.loop(seconds=5)
    async def poll_reaper(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for poll in self.repository.list_open_polls():
            if poll.expires_at > now:
                continue
            outcome = self.voting.close(poll.id, now=now)
            if poll.message_id is None:
                continue
            channel = self.get_channel(poll.channel_id)
            if channel is None or not hasattr(channel, "fetch_message"):
                continue
            try:
                message = await channel.fetch_message(poll.message_id)
                final = poll_text(poll, outcome.counts) + f'\n\n**Family decision:** {outcome.winning_choice}'
                await message.edit(content=final, view=None, allowed_mentions=discord.AllowedMentions.none())
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logging.warning("Could not update closed poll message %s", poll.message_id)

    @poll_reaper.before_loop
    async def before_poll_reaper(self) -> None:
        await self.wait_until_ready()


def create_bot(database_path: str | Path | None = None, *, demo_mode: bool | None = None) -> ChubbieBot:
    if demo_mode is None:
        demo_mode = os.getenv("CHUBBIE_DEMO_MODE", "0").lower() in {"1", "true", "yes"}
    config = ProgressionConfig.demo() if demo_mode else ProgressionConfig()
    path = database_path or os.getenv("CHUBBIE_DATABASE_PATH", "data/chubbie.sqlite3")
    return ChubbieBot(ChubbieRepository(path), CreatureEngine(config))


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "DISCORD_BOT_TOKEN is missing. Copy .env.example to .env and add the bot token from the Discord Developer Portal."
        )
    if os.getenv("CHUBBIE_DEMO_MODE", "0").lower() in {"1", "true", "yes"}:
        logging.warning("CHUBBIE DEMO MODE is ON: thresholds are reduced and cooldowns are disabled.")
    create_bot().run(token, log_handler=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

