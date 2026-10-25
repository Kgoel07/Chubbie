from __future__ import annotations

import asyncio
import io
import os
from datetime import datetime, timezone

import discord
from discord import app_commands

from chubbie.chubbie_core.dialogue import generate_dialogue
from chubbie.chubbie_core.serialization import SnapshotError, export_snapshot
from chubbie.chubbie_core.stories import choose_story

from .database import ChubbieRepository
from .interactions import DecisionView, ResetConfirmView, poll_text
from .service import NurseryService, can_reset
from .voting import VotingService


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


class ChubbieCommands(app_commands.Group):
    def __init__(
        self,
        repository: ChubbieRepository,
        nursery: NurseryService,
        voting: VotingService,
    ) -> None:
        super().__init__(name="chubbie", description="Raise this channel's shared fictional creature")
        self.repository = repository
        self.nursery = nursery
        self.voting = voting

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
        result = self.nursery.interact(*location, _user_key(interaction), action, expression)
        if result is None:
            await interaction.response.send_message("No Chubbie lives here yet. Try `/chubbie hatch`.", ephemeral=True)
            return
        await interaction.response.send_message(result.message, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(description="Hatch a new shared Chubbie in this channel")
    @app_commands.describe(name="A short name for the creature")
    async def hatch(self, interaction: discord.Interaction, name: str = "Chubbie") -> None:
        location = _location(interaction)
        if not location:
            await interaction.response.send_message("Use this in a server channel.", ephemeral=True)
            return
        result = self.nursery.hatch(*location, _user_key(interaction), name[:32])
        await interaction.response.send_message(result.message, allowed_mentions=discord.AllowedMentions.none())

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
        result = await asyncio.to_thread(generate_dialogue, state, topic[:120])
        label = "" if result.used_ai else "\n-# Template fallback (no AI request was used)."
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

