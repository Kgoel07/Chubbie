# Limitations and verification status

## Verified locally

- Python 3.13 import/compilation and the pinned dependency set.
- Deterministic actions, clamping, cooldown rejection, progression, multi-parent gates, and archetype selection.
- SQLite restart persistence and channel isolation.
- Unique votes, closed-poll rejection, deterministic ties, and lasting vote memories.
- Portable round-trip, malformed/oversized import rejection, and privacy field checks.
- Missing OpenAI key outage path, missing Discord token error, and Cubbie CLI isolation from Discord and OpenAI.
- Direct-address parsing, channel/ambient opt-ins, bounded context, sensitive-context silence, model participation
  approval, direct and ambient rate limits, and AI/state separation using deterministic provider doubles.
- Official Cubbie Skill structure validation and local `--sample` execution.
- A repeatable realistic transcript simulation is available at `chubbie/scripts/simulate_discord_chat.py`. It uses
  live OpenAI dialogue but does not connect to Discord or write creature state.
- Mocked tests verify entrance claiming, welcome/reply continuity, demo bypass and expiry, burst protection, event
  generation, strict BABY retry/fallback, response similarity, relevance-gated memories, safe mention insertion and
  cooldowns, emoji retry, and diagnostic state. They do not prove live-model comedic quality.

## Requires live credentials or platform access

- A real Discord gateway connection, application-command registration, invite, button rendering, attachment transfer,
  reply-reference resolution, channel permissions, timed demo announcement, and actual multi-user interaction require
  the user's Discord application/token.
- OpenAI dialogue requires a funded/authorized `OPENAI_API_KEY` and a model available to that account. Network/API
  failure intentionally falls back to one minimal stage-specific outage line; rich dialogue is never hardcoded.
- Cubbie installation and actual iMessage rendering require a Cubbie account. Local tooling cannot call Cubbie's
  built-in abilities or pretend to be its installer.
- WhatsApp Groups API is not live-tested or shipped because this team has not established Meta Official Business
  Account eligibility. Only the local simulator is implemented.

## Product boundaries

- Cubbie-to-Discord adoption is a one-time snapshot, not synchronization.
- Poll closure is persisted when the bot handles the timeout or the next decision; an offline bot cannot edit a
  Discord message at the exact expiry instant.
- SQLite plus one process is appropriate for a hackathon prototype, not horizontally scaled production.
- The content filter is deliberately conservative but is not a substitute for Discord moderation or a full safety
  classification service.
- Screenshot and deployment placeholders stay labeled until the user performs live credentialed testing.
- Discord's Message Content intent must be enabled in the Developer Portal. A connected bot without it cannot receive
  natural message text even though slash commands continue to work.

