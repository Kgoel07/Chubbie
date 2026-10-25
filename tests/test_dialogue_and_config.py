from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from chubbie.chubbie_core.dialogue import generate_dialogue
from chubbie.chubbie_core.engine import CreatureEngine


ROOT = Path(__file__).resolve().parents[1]


def test_missing_llm_credentials_use_fallback(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = CreatureEngine().new_egg()
    CreatureEngine().hatch(state)
    result = generate_dialogue(state)
    assert not result.used_ai
    assert result.text


def test_missing_discord_credentials_produce_clear_error(tmp_path) -> None:
    env = os.environ.copy()
    env.pop("DISCORD_BOT_TOKEN", None)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-m", "discord_bot.bot"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode != 0
    assert "DISCORD_BOT_TOKEN is missing" in completed.stderr + completed.stdout


def test_cubbie_cli_runs_without_importing_discord(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    script_path = ROOT / "chubbie" / "scripts" / "chubbie_cli.py"
    code = (
        "import builtins,runpy,sys; old=builtins.__import__; "
        "builtins.__import__=lambda n,*a,**k: (_ for _ in ()).throw(AssertionError('discord imported')) "
        "if n.startswith('discord') else old(n,*a,**k); "
        f"sys.argv=['chubbie_cli.py','--state',{str(state_path)!r},'hatch']; "
        f"runpy.run_path({str(script_path)!r},run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "hatched" in completed.stdout.lower()
    assert state_path.exists()

