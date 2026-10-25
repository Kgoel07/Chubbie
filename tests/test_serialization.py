from __future__ import annotations

import json

import pytest

from chubbie.chubbie_core.engine import CreatureEngine, ProgressionConfig
from chubbie.chubbie_core.serialization import (
    SnapshotError,
    export_snapshot,
    import_snapshot,
    load_state,
    save_state,
)


def make_state():
    engine = CreatureEngine(ProgressionConfig(cooldown_seconds=0))
    state = engine.new_egg("Byte")
    engine.hatch(state)
    engine.apply(state, "teach", expression="ship it")
    return state


def test_import_export_preserves_supported_state_and_privacy() -> None:
    original = make_state()
    payload = export_snapshot(original)
    restored = import_snapshot(payload)
    assert restored == original
    assert "user_id" not in payload
    assert "token" not in payload.lower()
    assert "chat_log" not in payload


def test_malformed_and_oversized_imports_are_rejected() -> None:
    with pytest.raises(SnapshotError):
        import_snapshot("not-json")
    with pytest.raises(SnapshotError):
        import_snapshot(json.dumps({"schema_version": 99}))
    with pytest.raises(SnapshotError):
        import_snapshot(b"x" * (64 * 1024 + 1))


def test_state_persists_after_restart(tmp_path) -> None:
    path = tmp_path / "state.json"
    original = make_state()
    save_state(path, original)
    assert load_state(path) == original

