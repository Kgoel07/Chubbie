# 60–90 second judge demo

Before recording, set `CHUBBIE_DEMO_MODE=1` and `CHUBBIE_POLL_SECONDS=12` in `.env`, label the screen “DEMO MODE,”
and start the bot. Demo thresholds are 3/6/10 instead of production's 8/20/40.

**0–12 seconds — Cubbie/iMessage.** Text “Cubbie, hatch Chubbie.” Then: “Play with Byte” and “Teach Byte to say
ship it.” Say: “This isn't a baby-themed prompt. Every change runs through a deterministic engine and persists under
the student's HOME.”

**12–22 seconds — deliberate handoff.** Text: “Export my Chubbie so my Discord group can adopt it.” Show the small
JSON attachment. Say: “No chat logs, credentials, Canvas data, or user identifiers cross this boundary.”

**22–35 seconds — Discord adoption.** In the nursery channel run `/chubbie adopt` and attach the export. Show
`/chubbie status`. Say: “Each Discord channel gets an independent shared creature.”

**35–50 seconds — three parents.** Have three real accounts run play, care, teach, and feed commands. Refresh status.
Say: “Per-user cooldowns stop spam in production. The trait shifts are deterministic, and teenager/adult forms need
at least two distinct participants.”

**50–67 seconds — family meeting.** Run `/chubbie story`. Let three accounts press the Discord buttons. After the
12-second close, show `/chubbie memories`. Say: “One person, one vote. The result becomes a lasting family memory and
nudges personality; ties resolve predictably.”

**67–80 seconds — earned evolution.** Use enough explicit care/play/teach commands to cross the next demo threshold,
then run `/chubbie evolution` and `/chubbie talk`. Point out that dialogue now matches the earned archetype and that
the response is labeled if the no-key fallback was used.

**80–90 seconds — restart proof.** Stop and restart `python -m discord_bot.bot`, then run `/chubbie status`. Close:
“The bot forgot the process, but Byte remembered the family. Your group chat made a baby; now the database has
receipts.”

