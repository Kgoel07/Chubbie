# Discord setup

## Create and invite the application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Open the application's **Bot** page, use **Reset Token**, copy the newly displayed bot token, and place it only
   in local `.env` as `DISCORD_BOT_TOKEN`. Do not use the Application ID, Public Key, OAuth client secret, or an
   OAuth access token. Paste the raw token without a `Bot ` prefix.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**. Discord will otherwise connect, but
   CHUBBIE cannot see natural messages. Presence and Server Members intents are not required.
4. Under OAuth2 URL Generator select scopes `bot` and `applications.commands`.
5. Select bot permissions: View Channels, Send Messages, Embed Links, Attach Files, and Read Message History. CHUBBIE
   does not need Administrator. Invite the generated URL to a test server you control.
6. Copy the test server ID (Developer Mode → right-click server → Copy Server ID) into optional
   `DISCORD_GUILD_ID` for rapid guild-only registration. Remove it for global production registration.

Administrator is required for `/chubbie reset`. Manage Channels or Administrator is required for `/chubbie enable`,
`/chubbie disable`, `/chubbie ambient`, `/chubbie debug`, and the one-step `/chubbie hatch`. `/chubbie demo start|stop`
requires Administrator.

## Configure and run

```powershell
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\Activate.ps1
python -m discord_bot.bot
```

Required: `DISCORD_BOT_TOKEN`. Optional: `DISCORD_GUILD_ID`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and
`CHUBBIE_DATABASE_PATH`. Global commands can take time to appear; development-guild commands are immediate.

If startup says `401 Unauthorized`, reset the token on the Bot page and replace the value in `.env`. A token copied
into `.env.example`, source control, a screenshot, or chat must be considered exposed and reset. Quotes around a
dotenv value are accepted, but they are unnecessary.

## Smoke test

In one channel:

```text
/chubbie hatch name:Byte ambient:true
hey Chubbie, what do you think of regular expressions?
/chubbie mentions mode:on
/chubbie demo start duration_seconds:90
/chubbie feed
/chubbie play
/chubbie teach expression:ship it
/chubbie status
/chubbie story
```

Use a second channel to hatch a different creature and verify isolation. Restart the process, then run status in the
first channel to demonstrate persistence. The bot must be online to receive interactions; missing external tokens
are not simulated.

`/chubbie hatch` enables natural chat in that channel immediately; no second enable command is required. For an
imported or pre-existing creature, `/chubbie enable` still activates that nursery. Direct addressing works with a bot mention or fuzzy name
variants such as “hey chubbie” and “CHUBBIEEEEE”. Ambient mode is a second, explicit opt-in. Production defaults
require at least 3 messages in 10 minutes, enforce a 10-minute Chubbie cooldown, and permit at most 3 ambient replies
per hour. Sensitive conversation and prompt-injection-like text force silence before the model is called.

`/chubbie debug` is the first troubleshooting step when ambient speech is missing. It reports channel and ambient
opt-ins, command demo status, recent human-message count, current cooldown, remaining quota, latest participation
decision/failure, provider availability, requested Message Content intent, and View/Send/History permissions. It
never displays recent message text or credentials.

When a creature is hatched, the bot posts a deterministic hatching embed followed by one original AI-generated BABY
`HATCH` line. Existing/adopted creatures still receive a one-time entrance when enabled. Re-running hatch or enable
does not repeat it. For 90 seconds, replies
to Chubbie and short follow-ups form a connected welcome interaction. A Discord reply to any tracked Chubbie message
also works without writing her name.

