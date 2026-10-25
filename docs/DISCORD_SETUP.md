# Discord setup

## Create and invite the application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Add a bot, reset/copy its token, and place it only in local `.env` as `DISCORD_BOT_TOKEN`.
3. Do **not** enable Message Content. CHUBBIE uses slash commands and button interactions only.
4. Under OAuth2 URL Generator select scopes `bot` and `applications.commands`.
5. Select bot permissions: View Channels, Send Messages, Embed Links, Attach Files, and Read Message History. CHUBBIE
   does not need Administrator. Invite the generated URL to a test server you control.
6. Copy the test server ID (Developer Mode → right-click server → Copy Server ID) into optional
   `DISCORD_GUILD_ID` for rapid guild-only registration. Remove it for global production registration.

Runtime admin permission is required only for `/chubbie reset`; Discord's command hint and the callback both check it.

## Configure and run

```powershell
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\Activate.ps1
python -m discord_bot.bot
```

Required: `DISCORD_BOT_TOKEN`. Optional: `DISCORD_GUILD_ID`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and
`CHUBBIE_DATABASE_PATH`. Global commands can take time to appear; development-guild commands are immediate.

## Smoke test

In one channel:

```text
/chubbie hatch name:Byte
/chubbie feed
/chubbie play
/chubbie teach expression:ship it
/chubbie status
/chubbie story
```

Use a second channel to hatch a different creature and verify isolation. Restart the process, then run status in the
first channel to demonstrate persistence. The bot must be online to receive interactions; missing external tokens
are not simulated.

