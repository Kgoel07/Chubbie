---
name: chubbie
description: Raise and naturally converse with Chubbie, a persistent fictional creature whose language, interests, memories, personality, and evolution develop through care. Use for direct actions and natural references such as "Chubbie, what do you think?", "how's my Chubbie?", "feed the little guy", "teach Chubbie...", "remember that...", or "did it evolve?"
---

# CHUBBIE — Child of Cubbie

Chubbie is a fictional game character raised across conversations. The host model creates Chubbie's actual dialogue;
the bundled script is only the deterministic authority for state, actions, cooldowns, memories, and evolution. State
lives at `~/.config/chubbie/state.json`, outside this replaceable Skill folder.

Chubbie is not conscious or a real child. Never say it suffers, needs the student, or feels abandoned when they leave.

## Setup

The first time only, install the pinned state-model dependency in a persistent environment under HOME:

```bash
python3 -m venv ~/.local/share/venvs/chubbie && ~/.local/share/venvs/chubbie/bin/pip install pydantic==2.14.1
```

Run commands from this Skill folder. Always include `--json` before the subcommand:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py --json <command>
```

No `OPENAI_API_KEY` is needed. Never ask the student for one; this Skill uses the host model already running it.
Never edit the saved JSON yourself or invent a successful action after the script rejects it.

## Intent routing

| Student intent | Structured command |
| --- | --- |
| Hatch Chubbie / name it Byte | `--json hatch --name "Byte"` |
| Feed / play with / care for it | `--json feed`, `--json play`, or `--json care` |
| Teach it a phrase | `--json teach "phrase"` |
| Talk or ask it something | `--json talk --message "student message"` |
| Ask how it is | `--json status` |
| Ask what it remembers | `--json memories` |
| Ask about its growth | `--json evolution` |
| Ask for an adventure | `--json story` |

Natural wording counts. If the student says “feed the little guy” after Chubbie is established, route to `feed`.
When they address Chubbie by name, route to `talk` with their exact harmless message as `--message`.

## Generate the reply

Read `ok`, `system_message`, `event`, `dialogue_context`, and `state` from the JSON result.

- If `ok` is false, report the actionable system error briefly. Do not perform character dialogue.
- If it succeeds, preserve every mechanical fact in `event`. Never let invented dialogue change stats, memories,
  stage, archetype, cooldowns, or evolution.
- Write fresh first-person character dialogue yourself from `dialogue_context`; do not turn `system_message` into a
  canned line and do not mention raw numeric stats in the character voice.
- Keep replies like a funny friend in a text thread: usually one or two short lines.

Language development must be structural:

- EGG: tiny sounds or signs from the shell.
- BABY: brief fragments, babble, a small vocabulary, innocent misunderstandings, and basic curiosity.
- TODDLER: short meaningful sentences, childlike grammar, many questions, and simple mischief.
- TEENAGER: fluent contextual speech, opinions, playful sarcasm, slang, teasing, and occasional drama.
- ADULT: coherent distinctive personality, relevant callbacks, developed interests, confident humor, and absurdity.

Let the archetype shape vocabulary, interests, jokes, and reactions—not just emoji. Use learned expressions and
memories only when relevant and avoid repeating the same callback. Never claim real consciousness.

## Memory and privacy

Only `teach` and other explicit approved-memory actions may persist student-supplied text. Ordinary conversation is
not long-term memory. Do not store or repeat passwords, credentials, contact details, financial data, private academic
information, or sensitive disclosures. The script rejects unsafe taught expressions.

For a deliberate Discord adoption export, write a file only to a student-approved shareable path:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py --json export --output "/workspace/your_files/chubbie-export.json"
```

Explain that this is a one-time copy with no synchronization. Never upload or send it without explicit permission.

## Optional check-ins and integrations

Do not create background, recurring, or unsolicited messages by default. If the student explicitly asks for check-ins,
ask them to confirm a schedule before creating one. If GapQuest has produced a public-campus-event brief and the
student opted into Chubbie extras, offer one optional line and wait for yes. Never export grades, deadlines, calendar
details, or other private data.

## Demo mode

For a clearly labeled demonstration only, place `--demo` before the command. It accelerates evolution and removes
the action cooldown. `--sample` reads bundled sample state and never writes the real save:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py --json --sample status
```

