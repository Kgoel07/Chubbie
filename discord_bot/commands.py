from __future__ import annotations

import asyncio
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import discord
from discord import app_commands

from chubbie.chubbie_core.dialogue import DIAGNOSTICS, OpenAICharacterProvider, generate_dialogue
from chubbie.chubbie_core.serialization import SnapshotError, export_snapshot
from chubbie.chubbie_core.stories import choose_story

from .database import ChubbieRepository
from .interactions import DecisionView, ResetConfirmView, poll_text
from .mentions import SafeMentionManager
from .service import NurseryService, can_reset
from .social import SocialChannelConfig, SocialParticipationEngine
from .voting import VotingService


def _mechanics_text(event: dict[str, object] | None) -> str:
    if not event:
        return ""
    changes = event.get("changes")
    if not isinstance(changes, dict):
        return ""
    labels = []
    for key, value in changes.items():
        if isinstance(value, int) and value:
            labels.append(f"{key.title()} {value:+d}")
    return " · ".join(labels)


def _location(interaction: discord.Interaction) -> tuple[int, int] | None:
    if interaction.guild_id is None or interaction.channel_id is None:
        return None
    return interaction.guild_id, interaction.channel_id


def _user_key(interaction: discord.Interaction) -> str:
    return str(interaction.user.id)


def _age_text(state) -> str:
    started = state.hatched_at or state.created_at
    seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60}m old"
    if seconds < 86400:
        return f"{seconds // 3600}h old"
    return f"{seconds // 86400}d old"


class DemoCommands(app_commands.Group):
    def __init__(self, owner: "ChubbieCommands") -> None:
        super().__init__(name="demo", description="Temporary accelerated hackathon interaction mode")
        self.owner = owner

    @staticmethod
    def _administrator(interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        return bool(permissions and permissions.administrator)

    @app_commands.command(description="Start temporary accelerated participation")
    @app_commands.default_permissions(administrator=True)
    async def start(
        self,
        interaction: discord.Interaction,
        duration_seconds: app_commands.Range[int, 60, 180] = 90,
    ) -> None:
        location = _location(interaction)
        if not location or not self._administrator(interaction):
            await interaction.response.send_message("Only an administrator can start demo mode.", ephemeral=True)
            return
        if not self.owner.repository.get_creature(*location):
            await interaction.response.send_message("Hatch or adopt Chubbie before starting demo mode.", ephemeral=True)
            return
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        try:
            self.owner.repository.start_demo(*location, expires_at)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        key = (str(location[0]), str(location[1]))
        self.owner.social.start_demo(key)
        scheduler = getattr(interaction.client, "schedule_demo_end", None)
        if scheduler:
            scheduler(*location, expires_at)
        await interaction.response.send_message(
            f"🎬 **CHUBBIE DEMO MODE ACTIVE** for {duration_seconds} seconds. "
            "Accelerated ambient limits are temporary; keep the conversation moving!"
        )

    @app_commands.command(description="Stop accelerated participation now")
    @app_commands.default_permissions(administrator=True)
    async def stop(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        if not location or not self._administrator(interaction):
            await interaction.response.send_message("Only an administrator can stop demo mode.", ephemeral=True)
            return
        self.owner.repository.stop_demo(*location)
        key = (str(location[0]), str(location[1]))
        self.owner.social.stop_demo(key)
        cancel = getattr(interaction.client, "cancel_demo_end", None)
        if cancel:
            cancel(*location)
        await interaction.response.send_message("🎬 Demo mode ended. Production participation limits are restored.")


class ChubbieCommands(app_commands.Group):
    def __init__(
        self,
        repository: ChubbieRepository,
        nursery: NurseryService,
        voting: VotingService,
        social: SocialParticipationEngine,
        character_provider: OpenAICharacterProvider,
        mention_manager: SafeMentionManager,
    ) -> None:
        super().__init__(name="chubbie", description="Raise this channel's shared fictional creature")
        self.repository = repository
        self.nursery = nursery
        self.voting = voting
        self.social = social
        self.character_provider = character_provider
        self.mention_manager = mention_manager
        self.add_command(DemoCommands(self))

    @staticmethod
    def _moderator(interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        return bool(permissions and (permissions.manage_channels or permissions.administrator))

    async def _state_or_reply(self, interaction: discord.Interaction):
        location = _location(interaction)
        if not location:
            await interaction.response.send_message("CHUBBIE nurseries live in server channels, not DMs.", ephemeral=True)
            return None
        state = self.repository.get_creature(*location)
        if state is None:
            await interaction.response.send_message("No nursery here yet. Use `/chubbie hatch` or `/chubbie adopt`.", ephemeral=True)
        return state

    async def _care_action(self, interaction: discord.Interaction, action: str, expression: str | None = None) -> None:
        location = _location(interaction)
        if not location:
            await interaction.response.send_message("Use this in a server channel.", ephemeral=True)
            return
        await interaction.response.defer()
        result = self.nursery.interact(*location, _user_key(interaction), action, expression)
        if result is None:
            await interaction.followup.send("No Chubbie lives here yet. Try `/chubbie hatch`.", ephemeral=True)
            return
        message = result.message
        if result.accepted:
            dialogue = await asyncio.to_thread(
                generate_dialogue,
                result.state,
                action,
                expression[:60] if expression else None,
            )
            mechanics = _mechanics_text(result.event)
            label = "" if dialogue.used_ai else "\n-# AI unavailable; minimal outage response shown."
            message = f"{dialogue.text}{label}" + (f"\n-# {mechanics}" if mechanics else "")
        await interaction.followup.send(message, allowed_mentions=discord.AllowedMentions.none())

    def _social_channel_config(self, location: tuple[int, int]) -> SocialChannelConfig:
        config = self.repository.get_channel_config(*location)
        return SocialChannelConfig(
            config.enabled,
            config.ambient_enabled,
            config.welcome_until,
            config.demo_expires_at,
        )

    async def _maybe_send_entrance(
        self,
        interaction: discord.Interaction,
        state,
        *,
        event_type: str = "GROUP_EVENT",
        hatcher_id: int | None = None,
        show_hatch_announcement: bool = False,
    ) -> bool:
        location = _location(interaction)
        if not location:
            return False
        welcome_until = datetime.now(timezone.utc) + timedelta(seconds=90)
        if not self.repository.claim_entrance(*location, welcome_until):
            return False
        key = (str(location[0]), str(location[1]))
        config = self._social_channel_config(location)
        try:
            if event_type == "HATCH":
                self.social.reset_channel(key)
            response = await asyncio.to_thread(
                self.social.generate_event,
                key=key,
                state=state,
                event_type=event_type,
                current_message=(
                    "A participant labeled parent just hatched Chubbie. This is Chubbie's first message."
                    if event_type == "HATCH"
                    else "Chubbie has just entered this enabled nursery for the first time."
                ),
                demo_mode=config.demo_active(datetime.now(timezone.utc)),
            )
            if hatcher_id:
                self.social.mark_engaged(key, str(hatcher_id))
            channel = interaction.channel
            if channel is None or not hasattr(channel, "send"):
                raise RuntimeError("Discord channel is unavailable")
            rendered = self.mention_manager.render(
                response.text,
                guild_id=location[0],
                channel_id=location[1],
                candidate_user_ids=[hatcher_id] if hatcher_id else [],
                force=bool(hatcher_id and event_type == "HATCH"),
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
            embed = (
                discord.Embed(
                    title="🥚⚠️ SOMETHING HAS HATCHED.",
                    description="The nursery is active. This appears to be everyone's problem now.",
                    color=discord.Color.gold(),
                )
                if show_hatch_announcement
                else None
            )
            sent = await channel.send(
                rendered.text,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
        except Exception as exc:
            self.repository.release_entrance(*location)
            logging.warning("Could not deliver Chubbie entrance in channel %s: %s", location[1], type(exc).__name__)
            return False
        register = getattr(interaction.client, "register_bot_message", None)
        if register:
            register(*location, sent.id)
        return True

    @app_commands.command(description="Enable natural Chubbie chat in this channel")
    @app_commands.default_permissions(manage_channels=True)
    async def enable(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        if not location or not self._moderator(interaction):
            await interaction.response.send_message("A moderator with Manage Channels can enable Chubbie here.", ephemeral=True)
            return
        updated = self.repository.set_channel_enabled(*location, True)
        ambient_note = "Ambient participation remains on." if updated.ambient_enabled else "Ambient participation is still off."
        await interaction.response.send_message(
            f"Chubbie can now answer direct mentions and name variants here. {ambient_note}",
            ephemeral=True,
        )
        state = self.repository.get_creature(*location)
        if state:
            await self._maybe_send_entrance(interaction, state)

    @app_commands.command(description="Disable monitoring and natural Chubbie replies in this channel")
    @app_commands.default_permissions(manage_channels=True)
    async def disable(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        if not location or not self._moderator(interaction):
            await interaction.response.send_message("A moderator with Manage Channels can disable Chubbie here.", ephemeral=True)
            return
        self.repository.set_channel_enabled(*location, False)
        self.social.stop_demo((str(location[0]), str(location[1])))
        cancel = getattr(interaction.client, "cancel_demo_end", None)
        if cancel:
            cancel(*location)
        await interaction.response.send_message("Natural Chubbie chat is disabled in this channel.", ephemeral=True)

    @app_commands.command(description="Turn spontaneous Chubbie participation on or off")
    @app_commands.default_permissions(manage_channels=True)
    async def ambient(self, interaction: discord.Interaction, mode: Literal["on", "off"]) -> None:
        location = _location(interaction)
        if not location or not self._moderator(interaction):
            await interaction.response.send_message("A moderator with Manage Channels can change ambient mode.", ephemeral=True)
            return
        try:
            self.repository.set_channel_ambient(*location, mode == "on")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(
            f"Ambient Chubbie participation is {mode} in this channel.", ephemeral=True
        )

    @app_commands.command(description="Opt in or out of occasional individual Chubbie mentions here")
    async def mentions(self, interaction: discord.Interaction, mode: Literal["on", "off"]) -> None:
        location = _location(interaction)
        if not location:
            await interaction.response.send_message("Use this in a server channel.", ephemeral=True)
            return
        self.repository.set_mention_preference(*location, str(interaction.user.id), mode == "on")
        await interaction.response.send_message(
            f"Your ambient Chubbie mention preference is {mode} for this nursery.", ephemeral=True
        )

    @app_commands.command(description="Show Chubbie's development, personality, and interests")
    async def personality(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        interests = sorted(state.topic_affinities.items(), key=lambda item: item[1], reverse=True)[:5]
        interest_text = ", ".join(name for name, _ in interests) or "still developing"
        await interaction.response.send_message(
            f"**{state.name}** is a {state.stage.value.lower()} with a **{state.archetype.value.lower()}** archetype.\n"
            f"Mood: {state.mood} · Emerging interests: {interest_text}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(description="Show privacy-safe character and participation diagnostics")
    @app_commands.default_permissions(manage_channels=True)
    async def debug(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        if not location or not self._moderator(interaction):
            await interaction.response.send_message("Moderator-only diagnostic.", ephemeral=True)
            return
        config = self.repository.get_channel_config(*location)
        diagnostics = DIAGNOSTICS.snapshot()
        social = self.social.channel_diagnostics(
            (str(location[0]), str(location[1])), self._social_channel_config(location)
        )
        permission_text = "unavailable"
        if interaction.guild and interaction.channel and interaction.guild.me:
            permissions = interaction.channel.permissions_for(interaction.guild.me)
            permission_text = (
                f"view={permissions.view_channel}, send={permissions.send_messages}, "
                f"history={permissions.read_message_history}"
            )
        text = (
            f"**CHUBBIE diagnostics (no secrets)**\n"
            f"Channel enabled: `{config.enabled}` · Ambient: `{config.ambient_enabled}` · Demo: `{social['demo_active']}`\n"
            f"Recent human messages: `{social['recent_human_messages']}` (minimum `{social['minimum_messages']}`)\n"
            f"Last ambient message: `{social['last_ambient_at']}`\n"
            f"Cooldown: `{social['cooldown_remaining_seconds']}s` remaining of `{social['cooldown_seconds']}s`\n"
            f"Ambient quota: `{social['quota_remaining']}/{social['quota_limit']}` remaining · Sample probability: `{social['sample_probability']}`\n"
            f"LLM provider available: `{bool(self.character_provider.api_key)}` · Model: `{self.character_provider.model}`\n"
            f"Message Content intent requested: `{interaction.client.intents.message_content}`\n"
            f"Discord permissions: `{permission_text}`\n"
            f"Last participation decision: `{social['last_decision']}`\n"
            f"Most recent failure: `{social['last_failure'] or diagnostics['last_failure']}`\n"
            f"Last successful LLM call: `{diagnostics['last_success_at']}`"
        )
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @app_commands.command(description="Create, enable, and immediately hatch this channel's Chubbie nursery")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(
        name="A short name for the creature",
        ambient="Also enable spontaneous participation in this nursery",
    )
    async def hatch(
        self, interaction: discord.Interaction, name: str = "Chubbie", ambient: bool = False
    ) -> None:
        location = _location(interaction)
        if not location or not self._moderator(interaction):
            await interaction.response.send_message(
                "A moderator with Manage Channels can create and enable a nursery.", ephemeral=True
            )
            return
        if self.repository.get_creature(*location):
            await interaction.response.send_message(
                "This channel already has a Chubbie. Existing state was preserved; the birth sequence was not replayed.",
                ephemeral=True,
            )
            return
        result = self.nursery.hatch_and_enable(
            *location, _user_key(interaction), name[:32], ambient=ambient
        )
        if not result.accepted:
            await interaction.response.send_message(result.message, allowed_mentions=discord.AllowedMentions.none())
            return
        await interaction.response.send_message(
            "Nursery created and natural conversation enabled in this channel.", ephemeral=True
        )
        sent = await self._maybe_send_entrance(
            interaction,
            result.state,
            event_type="HATCH",
            hatcher_id=interaction.user.id,
            show_hatch_announcement=True,
        )
        if not sent:
            await interaction.followup.send(
                "Chubbie hatched, but the entrance could not be delivered. Check `/chubbie debug` and channel permissions.",
                ephemeral=True,
            )

    @app_commands.command(description="Feed this channel's Chubbie")
    async def feed(self, interaction: discord.Interaction) -> None:
        await self._care_action(interaction, "feed")

    @app_commands.command(description="Play with this channel's Chubbie")
    async def play(self, interaction: discord.Interaction) -> None:
        await self._care_action(interaction, "play")

    @app_commands.command(description="Give Chubbie some care and encouragement")
    async def care(self, interaction: discord.Interaction) -> None:
        await self._care_action(interaction, "care")

    @app_commands.command(description="Deliberately teach Chubbie one short harmless expression")
    @app_commands.describe(expression="1–60 characters; no links, secrets, or contact details")
    async def teach(self, interaction: discord.Interaction, expression: str) -> None:
        await self._care_action(interaction, "teach", expression)

    @app_commands.command(description="Talk to Chubbie in its current personality")
    @app_commands.describe(topic="Optional short topic; it is not saved as chat history")
    async def talk(self, interaction: discord.Interaction, topic: str = "family check-in") -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        await interaction.response.defer()
        result = await asyncio.to_thread(generate_dialogue, state, "talk", topic[:120])
        label = "" if result.used_ai else "\n-# AI unavailable; minimal outage response shown."
        await interaction.followup.send(result.text + label, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(description="Show Chubbie's stats, age, personality, and progress")
    async def status(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        t = state.traits
        text = (
            f"**{state.name} — {state.stage.value.title()}**\n"
            f"Archetype: {state.archetype.value.title()}\n"
            f"Mood: {state.mood} · Energy: {state.energy}\n"
            f"Affection {t.affection} · Chaos {t.chaos} · Curiosity {t.curiosity} · Nerdiness {t.nerdiness}\n"
            f"Age: {_age_text(state)} · {self.nursery.engine.progress_text(state)}"
        )
        await interaction.response.send_message(text)

    @app_commands.command(description="Recall selected fictional family milestones")
    async def memories(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        items = state.memories[-8:]
        text = "No major memories yet." if not items else "**Tiny family archive**\n" + "\n".join(f"• {m.text}" for m in items)
        await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(description="Show evolution history and the current archetype")
    async def evolution(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        history = "\n".join(
            f"• {item.from_stage.value.title()} → {item.to_stage.value.title()}: {item.archetype.value.title()}"
            for item in state.evolution_history
        )
        await interaction.response.send_message(
            f"**Current:** {state.archetype.value.title()}\n{history or self.nursery.engine.progress_text(state)}"
        )

    @app_commands.command(description="Start a personality-shaped group decision")
    async def story(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        location = _location(interaction)
        if not state or not location:
            return
        story = choose_story(state)
        duration = int(os.getenv("CHUBBIE_POLL_SECONDS", "60"))
        try:
            poll = self.voting.start(*location, story.title, story.prompt, story.choices, duration_seconds=duration)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        # Persistent view: the bot restores it by poll/message ID after a restart.
        view = DecisionView(poll, self.repository, self.voting, timeout=None)
        await interaction.response.send_message(poll_text(poll), view=view)
        message = await interaction.original_response()
        self.repository.set_poll_message(poll.id, message.id)

    @app_commands.command(description="Trigger an original AI-generated absurd group interaction")
    async def surprise(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        state = await self._state_or_reply(interaction)
        if not location or not state:
            return
        config = self._social_channel_config(location)
        if not config.enabled:
            await interaction.response.send_message("Enable this nursery first with `/chubbie enable`.", ephemeral=True)
            return
        await interaction.response.defer()
        response = await asyncio.to_thread(
            self.social.generate_event,
            key=(str(location[0]), str(location[1])),
            state=state,
            event_type="GROUP_EVENT",
            current_message="Initiate one original absurd group interaction that is easy for the humans to answer.",
            demo_mode=config.demo_active(datetime.now(timezone.utc)),
        )
        sent = await interaction.followup.send(
            response.text,
            allowed_mentions=discord.AllowedMentions.none(),
            wait=True,
        )
        register = getattr(interaction.client, "register_bot_message", None)
        if register and sent:
            register(*location, sent.id)

    @app_commands.command(description="Adopt a deliberately exported portable CHUBBIE JSON file")
    async def adopt(self, interaction: discord.Interaction, snapshot: discord.Attachment) -> None:
        location = _location(interaction)
        if not location:
            await interaction.response.send_message("Use this in a server channel.", ephemeral=True)
            return
        if snapshot.size > 64 * 1024:
            await interaction.response.send_message("That snapshot is larger than 64 KB.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            state = self.nursery.adopt(*location, _user_key(interaction), await snapshot.read())
        except (SnapshotError, ValueError) as exc:
            await interaction.followup.send(f"Adoption refused safely: {exc}", ephemeral=True)
            return
        await interaction.followup.send(
            f"Adopted {state.name}, a {state.stage.value.lower()}. This is a one-time copy; it will not sync back to Cubbie.",
            ephemeral=False,
        )
        await self._maybe_send_entrance(interaction, state, event_type="ADOPTION")

    @app_commands.command(description="Export a portable privacy-safe creature snapshot")
    async def export(self, interaction: discord.Interaction) -> None:
        state = await self._state_or_reply(interaction)
        if not state:
            return
        payload = export_snapshot(state).encode("utf-8")
        file = discord.File(io.BytesIO(payload), filename="chubbie-export.json")
        await interaction.response.send_message(
            "One-time portable copy. It contains no chat logs, credentials, or user IDs and does not stay synchronized.",
            file=file,
            ephemeral=True,
        )

    @app_commands.command(description="Administrator-only reset with confirmation")
    @app_commands.default_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction) -> None:
        location = _location(interaction)
        permissions = getattr(interaction.user, "guild_permissions", None)
        if not location or not can_reset(is_administrator=bool(permissions and permissions.administrator)):
            await interaction.response.send_message("Only a server administrator can reset a nursery.", ephemeral=True)
            return
        if not self.repository.get_creature(*location):
            await interaction.response.send_message("There is no nursery in this channel.", ephemeral=True)
            return
        view = ResetConfirmView(self.repository, *location, interaction.user.id)
        await interaction.response.send_message(
            "Reset this channel's Chubbie, memories, votes, and progress? This cannot be undone.",
            view=view,
            ephemeral=True,
        )

