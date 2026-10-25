# 60–90 second judge demo

Before recording, optionally set `CHUBBIE_DEMO_MODE=1` for accelerated evolution and `CHUBBIE_POLL_SECONDS=12` in
`.env`, then start the bot. In a fresh Discord nursery run `/chubbie hatch ambient:true` and
`/chubbie demo start duration_seconds:90`. Conversational demo mode is temporary and visibly announced.

**0–12 seconds — Cubbie/iMessage.** Text “Cubbie, hatch Chubbie.” Then: “Play with Byte” and “Teach Byte to say
ship it.” Say: “This isn't a baby-themed prompt. Every change runs through a deterministic engine and persists under
the student's HOME.”

**12–22 seconds — deliberate handoff.** Text: “Export my Chubbie so my Discord group can adopt it.” Show the small
JSON attachment. Say: “No chat logs, credentials, Canvas data, or user identifiers cross this boundary.”

**22–35 seconds — Discord adoption.** In the nursery channel run `/chubbie adopt` and attach the export. Show
`/chubbie status`, then have a moderator run `/chubbie enable`. Let Chubbie's original baby entrance appear. Say:
“Each channel gets an independent creature, and this entrance came from the live character model.”

**35–50 seconds — three parents.** Have three real accounts run play, care, teach, and feed commands. Refresh status.
Say: “Per-user cooldowns stop spam in production. The trait shifts are deterministic, and teenager/adult forms need
at least two distinct participants.”

**50–60 seconds — actual conversation.** Type “hey Chubbie, what do you think of regular expressions?” then
“CHUBBIEEEEE explain yourself,” or reply directly to her entrance. Show the connected follow-up. Let two people discuss
code and show at most one relevant ambient interjection. Say: “Demo mode still enforces safety, activity, cooldown,
quota, sampling, and burst protection; the model writes every actual line.” Use `/chubbie surprise` only if a manual
conversation starter is needed.

**60–75 seconds — family meeting.** Run `/chubbie story`. Let three accounts press the Discord buttons. After the
12-second close, show `/chubbie memories`. Say: “One person, one vote. The result becomes a lasting family memory and
nudges personality; ties resolve predictably.”

**75–84 seconds — earned evolution.** Use enough explicit care/play/teach commands to cross the next demo threshold,
then run `/chubbie evolution` and `/chubbie talk`. Point out that dialogue now matches the earned archetype and that
the language changed from baby fragments into a genuinely different developmental voice.

**84–90 seconds — restart proof.** Stop and restart `python -m discord_bot.bot`, then run `/chubbie status`. Close:
“The bot forgot the process, but Byte remembered the family. Your group chat made a baby; now the database has
receipts.”

