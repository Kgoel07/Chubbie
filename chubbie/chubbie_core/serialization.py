from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import CreatureState, PortableSnapshot


MAX_IMPORT_BYTES = 64 * 1024


class SnapshotError(ValueError):
    pass


def export_snapshot(state: CreatureState, *, indent: int | None = 2) -> str:
    snapshot = PortableSnapshot(creature=state)
    return snapshot.model_dump_json(indent=indent)


def import_snapshot(payload: str | bytes) -> CreatureState:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > MAX_IMPORT_BYTES:
        raise SnapshotError(f"Snapshot exceeds the {MAX_IMPORT_BYTES // 1024} KB limit.")
    try:
        data = json.loads(raw)
        snapshot = PortableSnapshot.model_validate(data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise SnapshotError(f"Invalid CHUBBIE snapshot: {exc}") from exc
    return snapshot.creature.model_copy(deep=True)


def save_state(path: Path, state: CreatureState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def load_state(path: Path) -> CreatureState:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return CreatureState()
    if len(raw) > MAX_IMPORT_BYTES:
        raise SnapshotError("Saved state is unexpectedly large.")
    try:
        return CreatureState.model_validate_json(raw)
    except ValidationError as exc:
        raise SnapshotError(f"Saved state is invalid: {exc}") from exc

