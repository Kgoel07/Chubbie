from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from chubbie.chubbie_core.dialogue import OpenAICharacterProvider

from .commands import ChubbieCommands
from .database import ChubbieRepository
from .interactions import DecisionView, poll_text
from .mentions import SafeMentionManager
from .service import NurseryService
from .social import SocialChannelConfig, SocialConfig, SocialParticipationEngine
from .voting import VotingService


class ChubbieBot(commands.Bot):
    def __init__(
        self,
        repository: ChubbieRepository,
        engine: CreatureEngine,
        social_config: SocialConfig,
        demo_social_config: SocialConfig | None = None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.repository = repository
        self.engine = engine
        self.nursery = NurseryService(repository, engine)
        self.voting = VotingService(repository, engine)
        self.character_provider = OpenAICharacterProvider()
        self.mention_manager = SafeMentionManager(
            cooldown_seconds=int(os.getenv("CHUBBIE_MENTION_COOLDOWN_SECONDS", "300"))
        )
        self.social = SocialParticipationEngine(
            self.character_provider,
            config=social_config,
            demo_config=demo_social_config,
            game_engine=engine,
        )
        self.channel_locks: dict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)
        self.sent_message_ids: dict[tuple[int, int], deque[int]] = defaultdict(lambda: deque(maxlen=30))
        self.demo_end_tasks: dict[tuple[int, int], asyncio.Task] = {}

    async def setup_hook(self) -> None:
        self.tree.add_command(
            ChubbieCommands(
                self.repository,
                self.nursery,
                self.voting,
                self.social,
                self.character_provider,
                self.mention_manager,
            )
        )
        for poll in self.repository.list_open_polls():
            if poll.message_id is not None:
                self.add_view(
                    DecisionView(poll, self.repository, self.voting, timeout=None),
                    message_id=poll.message_id,
                )
        for guild_id, channel_id, expires_at in self.repository.list_active_demos():
            self.schedule_demo_end(guild_id, channel_id, expires_at)
        self.poll_reaper.start()
        logging.info(
            "Discord intents ready: guilds=%s message_content=%s",
            self.intents.guilds,
            self.intents.message_content,
        )
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info("Synced %d commands to development guild %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logging.info("Synced %d global commands", len(synced))

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        location = (message.guild.id, message.channel.id)
        stored = self.repository.get_channel_config(*location)
        if not stored.enabled:
            return
        if not message.content.strip():
            logging.info("CHUBBIE social channel=%s ignored empty/unavailable message content", message.channel.id)
            return
        key = (str(location[0]), str(location[1]))
        async with self.channel_locks[location]:
            # Re-read after waiting so disable/demo-expiry cancels delayed work safely.
            stored = self.repository.get_channel_config(*location)
            if not stored.enabled:
                logging.info("CHUBBIE social channel=%s cancelled because channel was disabled", message.channel.id)
                return
            now = datetime.now(timezone.utc)
            if stored.demo_expires_at and stored.demo_expires_at <= now:
                stored = self.repository.stop_demo(*location)
                self.social.stop_demo(key)
            state = self.repository.get_creature(*location)
            if not state:
                logging.info("CHUBBIE social channel=%s ignored because no creature exists", message.channel.id)
                return
            mentioned = bool(self.user and self.user in message.mentions)
            replied_to_bot = self._reply_targets_bot(message, location)
            outcome = await asyncio.to_thread(
                self.social.process_message,
                key=key,
                state=state,
                channel_config=SocialChannelConfig(
                    stored.enabled,
                    stored.ambient_enabled,
                    stored.welcome_until,
                    stored.demo_expires_at,
                ),
                text=message.content,
                author_name=getattr(message.author, "display_name", message.author.name),
                author_id=str(message.author.id),
                mentioned=mentioned,
                replied_to_bot=replied_to_bot,
                mentionable_user_ids=self.repository.get_mentionable_users(*location),
            )
            if outcome.state_changed:
                self.repository.save_creature(*location, state)
            if outcome.response:
                latest = self.repository.get_channel_config(*location)
                current_time = datetime.now(timezone.utc)
                demo_expired = bool(
                    outcome.kind == "ambient"
                    and outcome.demo_mode
                    and (not latest.demo_expires_at or latest.demo_expires_at <= current_time)
                )
                if not latest.enabled or (outcome.kind == "ambient" and not latest.ambient_enabled) or demo_expired:
                    logging.info("CHUBBIE social channel=%s cancelled pending %s response", message.channel.id, outcome.kind)
                    return
                try:
                    candidate = (
                        int(outcome.mention_candidate_id)
                        if outcome.mention_candidate_id and outcome.mention_candidate_id.isdigit()
                        else None
                    )
                    rendered = self.mention_manager.render(
                        outcome.response.text,
                        guild_id=location[0],
                        channel_id=location[1],
                        candidate_user_ids=[candidate] if candidate else [],
                        probability=0.35 if outcome.kind == "direct" else 0.25,
                    )
                    allowed_mentions = (
                        discord.AllowedMentions(
                            everyone=False,
                            roles=False,
                            users=[discord.Object(id=rendered.mentioned_user_id)],
                            replied_user=False,
                        )
                        if rendered.mentioned_user_id
                        else discord.AllowedMentions.none()
                    )
                    sent = await message.reply(
                        rendered.text,
                        mention_author=False,
                        allowed_mentions=allowed_mentions,
                    )
                    self.register_bot_message(*location, sent.id)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logging.warning(
                        "Could not send natural Chubbie response in channel %s: %s",
                        message.channel.id,
                        type(exc).__name__,
                    )

    def _reply_targets_bot(self, message: discord.Message, location: tuple[int, int]) -> bool:
        reference = message.reference
        if reference is None:
            return False
        resolved = reference.resolved
        if isinstance(resolved, discord.Message) and self.user and resolved.author.id == self.user.id:
            return True
        return bool(reference.message_id and reference.message_id in self.sent_message_ids[location])

    def register_bot_message(self, guild_id: int, channel_id: int, message_id: int) -> None:
        self.sent_message_ids[(guild_id, channel_id)].append(message_id)

    def schedule_demo_end(self, guild_id: int, channel_id: int, expires_at: datetime) -> None:
        self.cancel_demo_end(guild_id, channel_id)
        self.demo_end_tasks[(guild_id, channel_id)] = asyncio.create_task(
            self._finish_demo(guild_id, channel_id, expires_at)
        )

    def cancel_demo_end(self, guild_id: int, channel_id: int) -> None:
        task = self.demo_end_tasks.pop((guild_id, channel_id), None)
        if task and task is not asyncio.current_task():
            task.cancel()

    async def _finish_demo(self, guild_id: int, channel_id: int, expires_at: datetime) -> None:
        delay = max(0.0, (expires_at - datetime.now(timezone.utc)).total_seconds())
        try:
            await asyncio.sleep(delay)
            config = self.repository.get_channel_config(guild_id, channel_id)
            if config.demo_expires_at != expires_at:
                return
            self.repository.stop_demo(guild_id, channel_id)
            self.social.stop_demo((str(guild_id), str(channel_id)))
            channel = self.get_channel(channel_id)
            if channel is not None and hasattr(channel, "send"):
                await channel.send(
                    "🎬 Demo mode ended. Production participation limits are restored.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except asyncio.CancelledError:
            return
        finally:
            self.demo_end_tasks.pop((guild_id, channel_id), None)

    async def close(self) -> None:
        self.poll_reaper.cancel()
        for task in list(self.demo_end_tasks.values()):
            task.cancel()
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
    social_defaults = SocialConfig()
    social_config = SocialConfig(
        min_messages=int(os.getenv("CHUBBIE_AMBIENT_MIN_MESSAGES", str(social_defaults.min_messages))),
        window_seconds=int(os.getenv("CHUBBIE_AMBIENT_WINDOW_SECONDS", str(social_defaults.window_seconds))),
        ambient_cooldown_seconds=int(os.getenv("CHUBBIE_AMBIENT_COOLDOWN_SECONDS", str(social_defaults.ambient_cooldown_seconds))),
        max_ambient_per_hour=int(os.getenv("CHUBBIE_AMBIENT_MAX_PER_HOUR", str(social_defaults.max_ambient_per_hour))),
        sample_probability=float(os.getenv("CHUBBIE_AMBIENT_SAMPLE_PROBABILITY", str(social_defaults.sample_probability))),
        direct_cooldown_seconds=int(os.getenv("CHUBBIE_DIRECT_COOLDOWN_SECONDS", str(social_defaults.direct_cooldown_seconds))),
    )
    demo_defaults = SocialConfig.demo()
    demo_social_config = SocialConfig(
        min_messages=int(os.getenv("CHUBBIE_DEMO_MIN_MESSAGES", str(demo_defaults.min_messages))),
        window_seconds=int(os.getenv("CHUBBIE_DEMO_WINDOW_SECONDS", str(demo_defaults.window_seconds))),
        ambient_cooldown_seconds=int(os.getenv("CHUBBIE_DEMO_COOLDOWN_SECONDS", str(demo_defaults.ambient_cooldown_seconds))),
        max_ambient_per_hour=int(os.getenv("CHUBBIE_DEMO_MAX_MESSAGES", str(demo_defaults.max_ambient_per_hour))),
        sample_probability=float(os.getenv("CHUBBIE_DEMO_SAMPLE_PROBABILITY", str(demo_defaults.sample_probability))),
        direct_cooldown_seconds=0,
        context_limit=int(os.getenv("CHUBBIE_DEMO_CONTEXT_LIMIT", str(demo_defaults.context_limit))),
    )
    path = database_path or os.getenv("CHUBBIE_DATABASE_PATH", "data/chubbie.sqlite3")
    return ChubbieBot(
        ChubbieRepository(path), CreatureEngine(config), social_config, demo_social_config
    )


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
    try:
        create_bot().run(token, log_handler=None)
    except discord.LoginFailure:
        raise SystemExit(
            "Discord rejected DISCORD_BOT_TOKEN (401 Unauthorized). Reset and copy the token from "
            "Developer Portal > Applications > your app > Bot > Reset Token. Put the raw token in .env "
            "without a 'Bot ' prefix; do not place it in .env.example."
        ) from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

