from __future__ import annotations

from datetime import datetime, timezone

import discord

from .database import ChubbieRepository, PollRecord
from .service import can_reset
from .voting import VotingService


def poll_text(poll: PollRecord, counts: tuple[int, ...] | None = None) -> str:
    counts = counts or tuple(0 for _ in poll.choices)
    lines = [f"🚨 **{poll.title}**", poll.prompt, ""]
    lines.extend(f"{index + 1}. {choice} — {counts[index]} vote(s)" for index, choice in enumerate(poll.choices))
    lines.append("One vote per person. Ties go to the first listed option.")
    return "\n".join(lines)


class VoteButton(discord.ui.Button["DecisionView"]):
    def __init__(self, poll_id: str, index: int, label: str) -> None:
        super().__init__(
            label=label[:80],
            style=(discord.ButtonStyle.primary if index == 0 else discord.ButtonStyle.secondary),
            custom_id=f"chubbie:vote:{poll_id}:{index}",
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        result = self.view.voting.vote(self.view.poll_id, str(interaction.user.id), self.index)
        if result.accepted:
            poll = self.view.repository.get_poll(self.view.poll_id)
            if poll:
                await interaction.response.edit_message(content=poll_text(poll, result.counts), view=self.view)
                return
        await interaction.response.send_message(result.message, ephemeral=True)


class DecisionView(discord.ui.View):
    def __init__(
        self,
        poll: PollRecord,
        repository: ChubbieRepository,
        voting: VotingService,
        *,
        timeout: float | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.poll_id = poll.id
        self.repository = repository
        self.voting = voting
        for index, choice in enumerate(poll.choices):
            self.add_item(VoteButton(poll.id, index, choice))

    async def on_timeout(self) -> None:
        try:
            self.voting.close(self.poll_id)
        except ValueError:
            return
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class ResetConfirmView(discord.ui.View):
    def __init__(self, repository: ChubbieRepository, guild_id: int, channel_id: int, requester_id: int) -> None:
        super().__init__(timeout=30)
        self.repository = repository
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.requester_id = requester_id

    @discord.ui.button(label="Reset forever", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        permissions = getattr(interaction.user, "guild_permissions", None)
        allowed = interaction.user.id == self.requester_id and can_reset(
            is_administrator=bool(permissions and permissions.administrator)
        )
        if not allowed:
            await interaction.response.send_message("Only the administrator who requested this reset can confirm it.", ephemeral=True)
            return
        removed = self.repository.delete_nursery(self.guild_id, self.channel_id)
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(
            content=("Nursery reset. A fresh egg can now be hatched." if removed else "There was no nursery left to reset."),
            view=self,
        )

    @discord.ui.button(label="Keep Chubbie", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the requester can close this confirmation.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Reset cancelled. Chubbie pretends it was never worried.", view=None)

