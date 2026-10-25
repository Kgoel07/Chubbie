# Architecture

## Shared domain core

`chubbie/chubbie_core` is platform-neutral:

- `models.py` defines strict Pydantic state and snapshot schemas. Numeric traits are constrained to 0–100.
- `engine.py` owns every state transition, clamping, cooldown decision, memory rule, and interaction count.
- `evolution.py` applies configured thresholds and scores all four archetypes from traits and explicit action history.
  Fixed archetype order breaks exact score ties, so evolution is repeatable.
- `dialogue.py` builds bounded character context, retrieves relevant approved memories, calls the OpenAI Responses
  API for original dialogue, enforces BABY-stage output constraints, checks recent-response similarity, and contains
  only a minimal outage line per stage.
- `serialization.py` validates a 64 KB maximum portable format and performs atomic personal-state writes.
- `stories.py` chooses a deterministic personality-shaped scenario.

An LLM receives only a compact copy of stage, archetype, traits, mood, selected fictional memories, the explicit
action, and current fictional scenario. Submitted text is delimited as untrusted JSON. Model output is length-limited,
mention-sanitized dialogue; no model response is treated as a database instruction.

## Cubbie Skill

`chubbie/SKILL.md` is a standard Agent Skill with only `name` and `description` frontmatter. Cubbie runs
`scripts/chubbie_cli.py` inside its private sandbox. Real state is saved at `~/.config/chubbie/state.json`, so Skill
updates do not erase it. `--sample` reads the bundled asset and performs no write. Scripts do not call Cubbie tools.

The optional GapQuest bridge is instruction-level and opt-in. Cubbie may reuse a public campus event GapQuest has
already returned as story flavor, but the two Skills have no shared database and CHUBBIE never receives private
Canvas/calendar material.

## Discord

`discord_bot` uses application commands, interaction components, and opt-in natural messages:

1. `commands.py` validates the guild/channel context and explicit input.
2. `NurseryService` serializes state-changing operations and calls the shared engine.
3. `ChubbieRepository` stores one creature per `(guild_id, channel_id)` in SQLite.
4. Participants and cooldowns are separate internal tables. Portable exports contain no identifiers.
5. `VotingService` inserts one vote per `(poll_id, user_id)`, closes polls once, and resolves ties by the first listed
   option. The winning decision becomes a selected fictional memory and deterministically nudges a trait.
6. `SocialParticipationEngine` holds at most 20 recent messages per channel for at most 10 minutes. Direct addressing
   has a per-user cooldown. Ambient participation passes disabled/sensitive/rate/sample gates first, then asks the
   model for a structured `should_speak` decision before generating any dialogue.
7. A persisted one-time entrance flag and 90-second welcome deadline create a connected first interaction. Bot message
   IDs and Discord reply references route human replies into the same bounded context.
8. `/chubbie demo start` persists an expiration timestamp and swaps in 2-message/8-second/4-response/75% limits. It
   bypasses only the conservative production participation veto—not safety, activity, cooldown, quota, or burst gates.
9. `SafeMentionManager` strips all model-authored Discord mention syntax and may insert one actual allowlisted user ID
   from interaction metadata. Hatching may mention its moderator; direct replies may mention their speaker; ambient
   mentions require a per-nursery `/chubbie mentions on` preference and prior direct engagement.

The bot enables Guilds and privileged Message Content. It ignores DMs, bots, and all channels not explicitly enabled
by a moderator. Ambient mode is separately disabled by default. Conversation buffers never enter SQLite.

## Persistence schema

SQLite tables are `creatures`, `participants`, `cooldowns`, `polls`, `votes`, and `channel_config`. The last stores
channel opt-ins, one-time entrance state, welcome expiration, and temporary demo expiration. Foreign keys are enabled
and `mention_preferences` stores per-user ambient mention consent. WAL mode supports a small multi-server prototype.
Creature JSON uses the same Pydantic model as personal state. New
schema versions must use an explicit migration instead of silently accepting unknown fields.

## Trust boundaries

- `.env` credentials never enter SQLite or exports.
- Discord attachment imports are limited to 64 KB and validated with `extra="forbid"` at every model level.
- A server administrator must invoke and confirm reset; both checks occur at runtime.
- Stored memories are only hatching, explicitly taught expressions, approved “remember that…” facts, evolution, and
  group-vote outcomes. Ordinary chat and ambient context are never persisted.
- WhatsApp simulation is local and never opens a WhatsApp session.

