# Architecture

## Shared domain core

`chubbie/chubbie_core` is platform-neutral:

- `models.py` defines strict Pydantic state and snapshot schemas. Numeric traits are constrained to 0–100.
- `engine.py` owns every state transition, clamping, cooldown decision, memory rule, and interaction count.
- `evolution.py` applies configured thresholds and scores all four archetypes from traits and explicit action history.
  Fixed archetype order breaks exact score ties, so evolution is repeatable.
- `dialogue.py` supplies stage/archetype-specific templates and an optional OpenAI Responses API call.
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

`discord_bot` uses application commands and interaction components only:

1. `commands.py` validates the guild/channel context and explicit input.
2. `NurseryService` serializes state-changing operations and calls the shared engine.
3. `ChubbieRepository` stores one creature per `(guild_id, channel_id)` in SQLite.
4. Participants and cooldowns are separate internal tables. Portable exports contain no identifiers.
5. `VotingService` inserts one vote per `(poll_id, user_id)`, closes polls once, and resolves ties by the first listed
   option. The winning decision becomes a selected fictional memory and deterministically nudges a trait.

The bot enables only the Guilds intent. It does not request Message Content, inspect ordinary posts, or use DMs.

## Persistence schema

SQLite tables are `creatures`, `participants`, `cooldowns`, `polls`, and `votes`. Foreign keys are enabled and WAL
mode supports a small multi-server prototype. Creature JSON uses the same Pydantic model as personal state. New
schema versions must use an explicit migration instead of silently accepting unknown fields.

## Trust boundaries

- `.env` credentials never enter SQLite or exports.
- Discord attachment imports are limited to 64 KB and validated with `extra="forbid"` at every model level.
- A server administrator must invoke and confirm reset; both checks occur at runtime.
- Stored memories are only hatching, explicitly taught expressions, evolution, and group-vote outcomes.
- WhatsApp simulation is local and never opens a WhatsApp session.

