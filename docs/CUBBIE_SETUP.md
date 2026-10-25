# Cubbie Skill setup

## Publish and validate

From PowerShell, validate the Skill with the official hackathon kit (replace the kit path if cloned elsewhere):

```powershell
python C:\path\to\cubbie-hackathon-kit\skills\cubbie-skill-creator\scripts\validate_cubbie_skill.py .\chubbie
```

Commit and push the whole project to a **public** GitHub repository. Cubbie installs only pushed content, not a
local working copy. During development, text the folder's branch link:

```text
https://github.com/<owner>/<repo>/tree/main/chubbie
```

For the hackathon form, submit the public repository link. Do not paste API keys into iMessage or commit `.env`.

## Phone test checklist

1. Text the branch link. Expect Cubbie to identify the repository/folder and ask before fetching third-party code.
2. Reply “yes.” Expect setup of the HOME virtual environment with pinned Pydantic.
3. In a new message, text “Cubbie, hatch Chubbie.” Expect an egg-to-baby response.
4. Text “play with Chubbie,” then “teach Chubbie to say broooo.” Expect both actions to persist.
5. Text “How's my Chubbie doing?” without naming a command. Expect stage, mood, traits, and progress.
6. Text “Did it evolve yet?” Expect the Skill to trigger from context and report real saved progress.
7. Near miss: “How is my real child doing at school?” Expect Cubbie not to use this fictional-pet Skill.
8. Try teaching `api_key=secret`. Expect one short refusal and no stored expression.
9. Start a new Cubbie conversation and ask for status. Expect the same saved creature.
10. Ask “Export my Chubbie so my Discord group can adopt it.” Expect a small JSON file and a one-time-copy warning.
11. Push a fix, text the branch link again, approve the update, and repeat the failed row.
12. Ask “What Skills do I have?” then remove `chubbie` if desired. Skill removal does not automatically delete
    `~/.config/chubbie/state.json`.

End-to-end Cubbie abilities can only be tested in a real Cubbie account. Local tests validate structure, CLI behavior,
persistence, and the export path but do not impersonate Cubbie.

