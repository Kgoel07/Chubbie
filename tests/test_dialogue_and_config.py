from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from chubbie.chubbie_core.dialogue import (
    ConversationLine,
    generate_character_response,
    generate_dialogue,
    select_relevant_memories,
)
from chubbie.chubbie_core.engine import CreatureEngine
from chubbie.chubbie_core.models import LifeStage, Memory


ROOT = Path(__file__).resolve().parents[1]


def test_missing_llm_credentials_use_fallback(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = CreatureEngine().new_egg()
    CreatureEngine().hatch(state)
    result = generate_dialogue(state)
    assert not result.used_ai
    assert result.text
    assert any(ord(char) >= 0x2600 for char in result.text)


def test_ai_dialogue_uses_minimal_reasoning_and_visible_text_budget(monkeypatch) -> None:
    captured = {}
    calls = 0

    class FakeResponses:
        def create(self, **kwargs):
            nonlocal calls
            calls += 1
            captured.update(kwargs)
            if calls == 1:
                return SimpleNamespace(output_text='{"text":"tiny snack council","emotion":"curious","topic":"snacks"}')
            return SimpleNamespace(output_text='```json\n{"text":"tiny snack council 🐣","emotion":"curious","topic":"snacks"}\n```')

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    state = CreatureEngine().new_egg()
    CreatureEngine().hatch(state)
    result = generate_dialogue(state, "feed")
    assert result.used_ai
    assert result.text.endswith("🐣")
    assert calls == 2
    assert captured["reasoning"] == {"effort": "minimal"}
    assert captured["max_output_tokens"] >= 200
    assert "Never narrate" in captured["instructions"]
    assert "raw" in captured["instructions"].lower()


def test_missing_discord_credentials_produce_clear_error(tmp_path) -> None:
    env = os.environ.copy()
    # An explicit empty value prevents python-dotenv from loading a developer's
    # real local .env during this isolated error-path test.
    env["DISCORD_BOT_TOKEN"] = ""
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


def test_cubbie_cli_json_is_structured_context_without_external_ai(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    script_path = ROOT / "chubbie" / "scripts" / "chubbie_cli.py"
    subprocess.run(
        [sys.executable, str(script_path), "--state", str(state_path), "--json", "hatch", "--name", "Byte"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    completed = subprocess.run(
        [sys.executable, str(script_path), "--state", str(state_path), "--json", "talk", "--message", "do you like regex?"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["event"]["action"] == "talk"
    assert payload["dialogue_context"]["developmental_stage"] == "BABY"
    assert payload["dialogue_context"]["user_message"] == "do you like regex?"
    assert "OPENAI" not in completed.stderr


def test_example_environment_contains_no_secrets() -> None:
    contents = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "sk-proj-" not in contents
    assert not any(line.startswith("DISCORD_BOT_TOKEN=") and line.split("=", 1)[1].strip() for line in contents.splitlines())


def test_overly_mature_baby_dialogue_is_retried_once(monkeypatch) -> None:
    outputs = iter(
        [
            '{"text":"According to my sophisticated calculations this digital existence requires a comprehensive explanation for everyone 😭","emotion":"curious","topic":"existence"}',
            '{"text":"papa... wat dat? 🥺","emotion":"confused","topic":"unknown"}',
        ]
    )

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=next(outputs))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    state = CreatureEngine().new_egg()
    CreatureEngine().hatch(state)
    result = generate_character_response(state, current_message="hello", interaction_type="DIRECT_MESSAGE")
    assert result.used_ai
    assert result.text == "papa... wat dat? 🥺"
    assert len(result.text.split()) <= 10


def test_repeated_ai_response_retries_then_uses_safe_fallback(monkeypatch) -> None:
    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text='{"text":"same weird joke 💀","emotion":"silly","topic":"joke"}')

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    state = CreatureEngine().new_egg()
    state.stage = LifeStage.TEENAGER
    recent = [ConversationLine("Chubbie", "same weird joke 💀", datetime.now(timezone.utc), True)]
    result = generate_character_response(state, recent, "say something", "DIRECT_MESSAGE")
    assert not result.used_ai
    assert result.text != "same weird joke 💀"


def test_unrelated_important_hydration_memory_is_not_injected() -> None:
    state = CreatureEngine().new_egg()
    state.memories.append(
        Memory(kind="group_vote", text='The family chose "Hydration roll call".', important=True)
    )
    memories = select_relevant_memories(state, "we should order pizza")
    assert all("hydration" not in memory.text.lower() for memory in memories)
    relevant = select_relevant_memories(state, "what happened with the hydration call?")
    assert any("hydration" in memory.text.lower() for memory in relevant)

