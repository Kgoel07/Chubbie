# Limitations and verification status

## Verified locally

- Python 3.13 import/compilation and the pinned dependency set.
- Deterministic actions, clamping, cooldown rejection, progression, multi-parent gates, and archetype selection.
- SQLite restart persistence and channel isolation.
- Unique votes, closed-poll rejection, deterministic ties, and lasting vote memories.
- Portable round-trip, malformed/oversized import rejection, and privacy field checks.
- Missing OpenAI key fallback, missing Discord token error, and Cubbie CLI isolation from Discord.
- Official Cubbie Skill structure validation and local `--sample` execution.

## Requires live credentials or platform access

- A real Discord gateway connection, application-command registration, invite, button rendering, attachment transfer,
  and actual multi-user interaction require the user's Discord application/token.
- OpenAI dialogue requires a funded/authorized `OPENAI_API_KEY` and a model available to that account. Network/API
  failure intentionally falls back to templates.
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

