# CHUBBIE — Child of Cubbie

> **Your group chat made a baby. Now you have to raise it.**

CHUBBIE is a fictional creature with persistent stats, memories, learned expressions, group decisions, and a
personality that evolves from what its players actually do. An individual student can raise one through a standard
Cubbie Agent Skill; a Discord friend group can collectively raise a separate shared creature in each nursery
channel.

This is a working local prototype for Cubbie Hackathon Tracks 1 and 3. It remains playable without an OpenAI key,
does not read ordinary Discord messages, and does not claim unsupported WhatsApp access.

## What works

- Deterministic `EGG → BABY → TODDLER → TEENAGER → ADULT` progression with configurable thresholds.
- Four behavior-selected archetypes: Procrastisaurus Rex, Brainrot Goblin, Emotional Support Dragon, and
  Existential Philosopher.
- Feed, play, care, teach, talk, status, memories, evolution, stories, adoption, export, and admin-confirmed reset.
- Per-user cooldowns; duplicate/late vote rejection; deterministic tie handling; durable SQLite state.
- Privacy-safe, schema-validated JSON transfer from the personal Cubbie Skill to Discord.
- Optional OpenAI Responses API dialogue with bounded context and a deterministic fallback.
- Development-only accelerated mode and WhatsApp event simulator, both visibly labeled.

## Architecture

```text
Cubbie/iMessage ── chubbie/SKILL.md ── chubbie_cli.py ─┐
                                                       ├─ shared chubbie_core engine
Discord slash commands ── NurseryService ── SQLite ────┤
                                                       └─ optional dialogue generator
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
development because guild commands register immediately. `OPENAI_API_KEY` and `OPENAI_MODEL` are optional; without
them, CHUBBIE labels and uses its built-in fallback dialogue. `CHUBBIE_DATABASE_PATH` is optional.

Run tests:

```powershell
python -m pytest --basetemp .pytest-tmp
```

Run the local personal CLI:

```powershell
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json hatch --name Byte
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json play
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json teach "ship it"
python .\chubbie\scripts\chubbie_cli.py --state .\data\personal.json status
```

Run Discord:

```powershell
python -m discord_bot.bot
```

Missing `DISCORD_BOT_TOKEN` stops immediately with a setup message instead of silently running offline. Complete
portal and invite steps are in [DISCORD_SETUP.md](docs/DISCORD_SETUP.md).

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
- `CHUBBIE_DEMO_MODE=1` reduces thresholds to 3/6/10 and removes cooldowns. The bot logs a warning; production
  defaults remain 8/20/40 with a 20-second per-user cooldown.

## Safety and privacy

CHUBBIE processes only explicit slash commands in the channel where they are invoked. The bot requests no Message
Content intent and never silently monitors a server. It stores only creature state, opaque platform user IDs needed
for cooldown/vote uniqueness, and selected fictional milestones. Teaching rejects likely secrets, contact details,
links, and dangerous text; outgoing mass mentions are neutralized. CHUBBIE is explicitly a fictional game character
and never guilt-trips students for leaving.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Cubbie Skill setup and phone checklist](docs/CUBBIE_SETUP.md)
- [Discord Developer Portal setup](docs/DISCORD_SETUP.md)
- [Judge demo script](docs/DEMO_SCRIPT.md)
- [Known limitations and live-test status](docs/LIMITATIONS.md)

