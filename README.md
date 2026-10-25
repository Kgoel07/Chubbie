# CHUBBIE — Child of Cubbie

> **Your group chat made a baby. Now you have to raise it.**

CHUBBIE is a fictional creature with persistent stats, memories, learned expressions, group decisions, and a
personality that evolves from what its players actually do. An individual student can raise one through a standard
Cubbie Agent Skill; a Discord friend group can collectively raise a separate shared creature in each nursery
channel.

This is a working local prototype for Cubbie Hackathon Tracks 1 and 3. The Cubbie Skill needs no external AI key;
the Discord version uses an OpenAI key for generated character speech. It reads ordinary messages only in channels
where a moderator explicitly runs `/chubbie enable`, and it does not claim unsupported WhatsApp access.

## What works

- Deterministic `EGG → BABY → TODDLER → TEENAGER → ADULT` progression with configurable thresholds.
- Four behavior-selected archetypes: Procrastisaurus Rex, Brainrot Goblin, Emotional Support Dragon, and
  Existential Philosopher.
- Feed, play, care, teach, talk, status, memories, evolution, stories, adoption, export, and admin-confirmed reset.
- Per-user cooldowns; duplicate/late vote rejection; deterministic tie handling; durable SQLite state.
- Privacy-safe, schema-validated JSON transfer from the personal Cubbie Skill to Discord.
- OpenAI Responses API character dialogue, bounded in-memory context, opt-in direct conversation, and rate-limited
  opt-in ambient participation. The only hardcoded character line is a clearly labeled outage fallback.
- A one-time AI-generated nursery entrance, 90-second welcome interaction, reply-to-Chubbie continuity, original
  `/chubbie surprise` events, and administrator-controlled temporary demo mode.
- Development-only accelerated mode and WhatsApp event simulator, both visibly labeled.

## Architecture

```text
Cubbie/iMessage ── host model + structured CLI ────────┐
                                                       ├─ shared deterministic game engine
Discord messages ── participation gates ── character AI│
Discord commands ── NurseryService ── SQLite ──────────┤
WhatsApp simulator ── GroupPlatformAdapter ────────────┘
```

The LLM returns dialogue only. It cannot update stats, approve progression, select a random archetype, or write the
database. See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for data flow and trust boundaries.

## Screenshots

Live screenshots are intentionally not fabricated. Capture these after connecting your own credentials:

1. **Placeholder — Cubbie hatch:** the iMessage response after “Cubbie, hatch Chubbie.”
2. **Placeholder — Discord nursery:** `/chubbie status` followed by a three-button emergency meeting.
3. **Placeholder — persisted evolution:** the same status after restarting the bot.

## Quick start on Windows PowerShell

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`. `DISCORD_BOT_TOKEN` is required for the bot. `DISCORD_GUILD_ID` is optional but recommended during
development because guild commands register immediately. `OPENAI_API_KEY` is required for full Discord character
dialogue; without it CHUBBIE uses a tiny, labeled outage response. `CHUBBIE_DATABASE_PATH` is optional.

Run tests:

```powershell
python -m pytest --basetemp .pytest-tmp
```

Run the local personal CLI:

```powershell
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json --json hatch --name Byte
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json --json play
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json --json talk --message "what do you think?"
```

Run Discord:

```powershell
python -m discord_bot.bot
```

Missing `DISCORD_BOT_TOKEN` stops immediately with a setup message instead of silently running offline. Complete
portal and invite steps are in [DISCORD_SETUP.md](docs/DISCORD_SETUP.md).

For a live demonstration, enable the nursery and ambient mode, then start temporary acceleration:

```text
/chubbie hatch name:Chubbie ambient:true
/chubbie demo start duration_seconds:90
```

`/chubbie hatch` is now one-step onboarding: it requires Manage Channels, creates a fresh BABY, enables natural
conversation only in the current channel, sends the AI-generated birth entrance immediately, and opens the 90-second
welcome window. It never overwrites an existing creature. The optional `ambient:true` flag enables spontaneous
participation at birth; otherwise ambient remains separately controlled.

Students who want occasional individual pings during ambient conversation can opt in per nursery with
`/chubbie mentions on`. Direct speakers and the hatching moderator may be mentioned contextually. All mention IDs are
selected from real Discord interaction metadata outside the model; role, mass, invented, and nonparticipant mentions
are blocked.

Demo mode expires automatically and restores production limits. `/chubbie demo stop` ends it immediately.
`/chubbie debug` shows the exact active threshold, recent human-message count, cooldown, quota, latest decision, and
provider status without showing message text or credentials. `/chubbie surprise` is an AI-generated manual backup.

### Tune Chubbie's voice

- Edit [`chubbie/prompts/character.md`](chubbie/prompts/character.md) for stage, archetype, humor, and speaking style.
- Edit [`chubbie/prompts/participation.md`](chubbie/prompts/participation.md) for when ambient Chubbie should speak.
- Edit [`chubbie/SKILL.md`](chubbie/SKILL.md) for the Cubbie/iMessage host-model behavior.

Restart the Discord bot after prompt edits. `CHUBBIE_CHARACTER_PROMPT` can temporarily replace the character prompt
with a one-line environment value, but the versioned Markdown file is easier to review and tune.

## Install the Cubbie Skill

After pushing this repository publicly, text Cubbie the GitHub folder link:

```text
https://github.com/<owner>/<repo>/tree/main/chubbie
```

Reply “yes” when Cubbie describes the third-party Skill and asks to install it. Then send a **new** message such as
“Cubbie, hatch Chubbie.” Cubbie reads `chubbie/SKILL.md`, installs one pinned Python dependency into a persistent
HOME virtual environment, and runs the bundled CLI. No external CHUBBIE server or Discord bot is required.

Use a branch link while testing. Once verified on a real Cubbie account, use the repository link for the hackathon
submission or a commit-pinned folder link for a fixed demo. See [CUBBIE_SETUP.md](docs/CUBBIE_SETUP.md).

## Adopt from Cubbie into Discord

1. Text Cubbie: “Export my Chubbie so my Discord group can adopt it.”
2. Save the returned `chubbie-export.json` file.
3. In the intended nursery channel, run `/chubbie adopt` and attach that file.

This is a deliberate one-time copy. The two creatures do not synchronize afterward. Snapshots exclude Discord user
IDs, credentials, chat logs, and unrelated conversations.

## GapQuest compatibility

[GapQuest](https://github.com/HarshaKoushikTeja/GapQuest) remains untouched. CHUBBIE's Skill contains an optional,
opt-in post-brief hook: after GapQuest has already found a real public campus event, Cubbie may ask whether the
student wants a tiny Chubbie adventure inspired by it. The hook skips cleanly when GapQuest is unavailable and never
exports Canvas deadlines, grades, calendar data, or other private academic information to Discord.

## WhatsApp status

The official Groups API is not realistically accessible to a typical student team without Meta business
eligibility and approvals. No unofficial WhatsApp Web automation is included. The reusable interface, actual
requirements, and clearly labeled local simulator are in [FEASIBILITY.md](whatsapp/FEASIBILITY.md).

## Demo and limitations

- Follow the judge-ready [60–90 second demo script](docs/DEMO_SCRIPT.md).
- Read [LIMITATIONS.md](docs/LIMITATIONS.md) before claiming external integrations.
- `CHUBBIE_DEMO_MODE=1` accelerates deterministic evolution for local development. Conversational acceleration is
  separate and must be started by an administrator with `/chubbie demo start`; it expires automatically.

## Safety and privacy

CHUBBIE requests Discord's Message Content intent but ignores DMs, bots, and every channel until a moderator runs
`/chubbie enable`. Ambient participation is separately off by default and requires `/chubbie ambient on`. Recent context is held only
in memory (maximum 20 messages / 10 minutes) and is not written to SQLite. Persistent text is limited to deliberate
teaching, approved “remember that…” requests, and fictional milestones. Outgoing mass mentions are neutralized.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Cubbie Skill setup and phone checklist](docs/CUBBIE_SETUP.md)
- [Discord Developer Portal setup](docs/DISCORD_SETUP.md)
- [Judge demo script](docs/DEMO_SCRIPT.md)
- [Known limitations and live-test status](docs/LIMITATIONS.md)
