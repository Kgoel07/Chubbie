---
name: chubbie
description: Hatch and raise Chubbie, a persistent funny fictional creature whose mood, memories, learned expressions, personality and evolution change through care. Use whenever a student asks to hatch, feed, play with, care for, talk to, teach, check, evolve, remember with, or export their Chubbie, including "How's my Chubbie?", "teach Chubbie to say...", or "did Chubbie evolve?"
---

# CHUBBIE — Child of Cubbie

The student's chats made a fictional baby. Now they have to raise it. Use the bundled deterministic script for
every state change so its stats, memories, and evolution remain consistent across conversations. The script saves
real state under `~/.config/chubbie/state.json`, outside this replaceable Skill folder.

Chubbie is a game character, not a real child or conscious being. Keep the joke playful: never claim it suffers,
needs the student, or feels abandoned when they leave.

## Setup (first time only)

Install the one pinned dependency in a persistent virtual environment under HOME:

```bash
python3 -m venv ~/.local/share/venvs/chubbie && ~/.local/share/venvs/chubbie/bin/pip install pydantic==2.14.1
```

If `~/.local/share/venvs/chubbie/bin/python` is missing later, run Setup again.

Run every command from this Skill's folder with:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py <command>
```

The script is the authority on whether an action counts, which traits change, and whether evolution happens. Do
not edit the JSON state yourself or invent a successful action after the script rejects it.

## Requests and commands

| Student asks | Run |
| --- | --- |
| "Hatch Chubbie" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py hatch` |
| "Hatch one named Byte" | Add `--name "Byte"` to `hatch` |
| "Feed Chubbie" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py feed` |
| "Play with Chubbie" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py play` |
| "Take care of Chubbie" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py care` |
| "Teach Chubbie to say broooo" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py teach "broooo"` |
| "Talk to Chubbie" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py talk` |
| "How's my Chubbie?" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py status` |
| "What does Chubbie remember?" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py memories` |
| "Did Chubbie evolve?" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py evolution` |
| "Give Chubbie an adventure" | `~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py story` |

For a harmless story, run `story`, text the three choices, ask for one answer, and narrate only a short fictional
outcome. Stories do not change stats unless the script reports a state change.

## Teaching

Pass only the expression the student deliberately supplied. The script accepts at most 60 characters, refuses
links, likely credentials, contact details, and dangerous content, and stores no unrelated conversation. If it
refuses an expression, say why in one line and ask for a different harmless phrase. Never coax the student to
share private information.

## Export for group adoption

When the student deliberately asks to share this creature with a Discord group, choose a file path under the
student's shareable workspace and run:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py export --output "/workspace/your_files/chubbie-export.json"
```

Send that file to the student. It contains creature state and fictional memories only—no chat logs, credentials,
or user identifiers. Explain that import is a one-time copy; the personal and Discord creatures do not sync.
Never upload or send the file anywhere without the student's explicit request.

## Optional GapQuest moment

If GapQuest has just produced a morning brief and the student previously opted into Chubbie extras, offer one
short optional line: "Your Chubbie has a tiny idea for today. Want it?" Wait for yes. Then use one real public
campus event already present in the brief as flavor for a harmless mini-adventure. Do not include Canvas deadlines,
grades, calendar details, or other private academic information in any export or group message. If GapQuest is not
installed or found no event, Chubbie works normally and the hook is skipped.

Do not create recurring or unsolicited Chubbie messages unless the student explicitly asks and confirms a schedule.

## Demo mode

For a clearly labeled local demonstration only, put `--demo` before the command. It lowers evolution thresholds
and removes the cooldown. Never silently use it for normal play. `--sample` uses bundled state and never writes the
student's real save, for example:

```bash
~/.local/share/venvs/chubbie/bin/python scripts/chubbie_cli.py --sample status
```

## Replies

Reply like a funny friend in a text thread: short plain text, no Markdown, usually one to four lines. Lead with what
happened. Preserve the creature's saved stage and archetype in the voice: babies use simpler bursts, teenagers are
dramatic, and adults sound confidently ridiculous. Use the script's wording or lightly paraphrase it without
changing facts. Ask only one question at a time.

When a command fails, send the script's actionable error in one short line. Never claim an action, save, export, or
evolution worked when the script failed.

