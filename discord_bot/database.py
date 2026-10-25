from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from chubbie.chubbie_core.models import CreatureState


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class PollRecord:
    id: str
    guild_id: int
    channel_id: int
    title: str
    prompt: str
    choices: tuple[str, ...]
    expires_at: datetime
    closed_at: datetime | None
    winning_index: int | None
    message_id: int | None


@dataclass(frozen=True)
class ChannelConfig:
    enabled: bool = False
    ambient_enabled: bool = False
    entrance_sent: bool = False
    welcome_until: datetime | None = None
    demo_expires_at: datetime | None = None


class ChubbieRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self) -> None:
        with self.connection() as db:
            db.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS creatures (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id)
                );
                CREATE TABLE IF NOT EXISTS participants (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_key TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id, user_key)
                );
                CREATE TABLE IF NOT EXISTS cooldowns (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_key TEXT NOT NULL,
                    last_action_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id, user_key)
                );
                CREATE TABLE IF NOT EXISTS polls (
                    id TEXT PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    choices_json TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    closed_at TEXT,
                    winning_index INTEGER,
                    message_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS votes (
                    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                    user_key TEXT NOT NULL,
                    choice_index INTEGER NOT NULL,
                    voted_at TEXT NOT NULL,
                    PRIMARY KEY (poll_id, user_key)
                );
                CREATE TABLE IF NOT EXISTS channel_config (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    ambient_enabled INTEGER NOT NULL DEFAULT 0,
                    entrance_sent INTEGER NOT NULL DEFAULT 0,
                    welcome_until TEXT,
                    demo_expires_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id)
                );
                CREATE TABLE IF NOT EXISTS mention_preferences (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id, user_id)
                );
                CREATE INDEX IF NOT EXISTS polls_channel_open
                    ON polls(guild_id, channel_id, closed_at);
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(channel_config)").fetchall()}
            migrations = {
                "entrance_sent": "ALTER TABLE channel_config ADD COLUMN entrance_sent INTEGER NOT NULL DEFAULT 0",
                "welcome_until": "ALTER TABLE channel_config ADD COLUMN welcome_until TEXT",
                "demo_expires_at": "ALTER TABLE channel_config ADD COLUMN demo_expires_at TEXT",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    db.execute(statement)

    def get_creature(self, guild_id: int, channel_id: int) -> CreatureState | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT state_json FROM creatures WHERE guild_id=? AND channel_id=?",
                (guild_id, channel_id),
            ).fetchone()
        return CreatureState.model_validate_json(row["state_json"]) if row else None

    def save_creature(self, guild_id: int, channel_id: int, state: CreatureState) -> None:
        now = _iso(datetime.now(timezone.utc))
        with self.connection() as db:
            db.execute(
                """INSERT INTO creatures(guild_id, channel_id, state_json, updated_at)
                   VALUES(?,?,?,?) ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                   state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (guild_id, channel_id, state.model_dump_json(), now),
            )

    def delete_nursery(self, guild_id: int, channel_id: int) -> bool:
        with self.connection() as db:
            db.execute("DELETE FROM polls WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            db.execute("DELETE FROM cooldowns WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            db.execute("DELETE FROM participants WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            db.execute("DELETE FROM channel_config WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            db.execute("DELETE FROM mention_preferences WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            result = db.execute("DELETE FROM creatures WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
            return result.rowcount > 0

    def get_channel_config(self, guild_id: int, channel_id: int) -> ChannelConfig:
        with self.connection() as db:
            row = db.execute(
                """SELECT enabled, ambient_enabled, entrance_sent, welcome_until, demo_expires_at
                   FROM channel_config WHERE guild_id=? AND channel_id=?""",
                (guild_id, channel_id),
            ).fetchone()
        return (
            ChannelConfig(
                bool(row["enabled"]),
                bool(row["ambient_enabled"]),
                bool(row["entrance_sent"]),
                _dt(row["welcome_until"]),
                _dt(row["demo_expires_at"]),
            )
            if row
            else ChannelConfig()
        )

    def set_channel_enabled(self, guild_id: int, channel_id: int, enabled: bool) -> ChannelConfig:
        current = self.get_channel_config(guild_id, channel_id)
        ambient = current.ambient_enabled if enabled else False
        self._upsert_channel_config(guild_id, channel_id, enabled, ambient)
        if not enabled:
            self.stop_demo(guild_id, channel_id)
        updated = self.get_channel_config(guild_id, channel_id)
        return ChannelConfig(enabled, ambient, updated.entrance_sent, updated.welcome_until, updated.demo_expires_at)

    def set_channel_ambient(self, guild_id: int, channel_id: int, enabled: bool) -> ChannelConfig:
        current = self.get_channel_config(guild_id, channel_id)
        if enabled and not current.enabled:
            raise ValueError("Enable Chubbie in this channel first with /enable.")
        self._upsert_channel_config(guild_id, channel_id, current.enabled, enabled)
        updated = self.get_channel_config(guild_id, channel_id)
        return ChannelConfig(current.enabled, enabled, updated.entrance_sent, updated.welcome_until, updated.demo_expires_at)

    def _upsert_channel_config(
        self, guild_id: int, channel_id: int, enabled: bool, ambient_enabled: bool
    ) -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO channel_config(guild_id,channel_id,enabled,ambient_enabled,updated_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(guild_id,channel_id) DO UPDATE SET
                   enabled=excluded.enabled, ambient_enabled=excluded.ambient_enabled,
                   updated_at=excluded.updated_at""",
                (guild_id, channel_id, int(enabled), int(ambient_enabled), _iso(datetime.now(timezone.utc))),
            )

    def claim_entrance(self, guild_id: int, channel_id: int, welcome_until: datetime) -> bool:
        with self.connection() as db:
            result = db.execute(
                """UPDATE channel_config SET entrance_sent=1, welcome_until=?, updated_at=?
                   WHERE guild_id=? AND channel_id=? AND enabled=1 AND entrance_sent=0""",
                (_iso(welcome_until), _iso(datetime.now(timezone.utc)), guild_id, channel_id),
            )
            return result.rowcount == 1

    def release_entrance(self, guild_id: int, channel_id: int) -> None:
        with self.connection() as db:
            db.execute(
                """UPDATE channel_config SET entrance_sent=0, welcome_until=NULL, updated_at=?
                   WHERE guild_id=? AND channel_id=?""",
                (_iso(datetime.now(timezone.utc)), guild_id, channel_id),
            )

    def start_demo(self, guild_id: int, channel_id: int, expires_at: datetime) -> ChannelConfig:
        current = self.get_channel_config(guild_id, channel_id)
        if not current.enabled:
            raise ValueError("Enable Chubbie in this channel first with /chubbie enable.")
        if not current.ambient_enabled:
            raise ValueError("Enable ambient mode first with /chubbie ambient on.")
        with self.connection() as db:
            db.execute(
                "UPDATE channel_config SET demo_expires_at=?, updated_at=? WHERE guild_id=? AND channel_id=?",
                (_iso(expires_at), _iso(datetime.now(timezone.utc)), guild_id, channel_id),
            )
        return self.get_channel_config(guild_id, channel_id)

    def stop_demo(self, guild_id: int, channel_id: int) -> ChannelConfig:
        with self.connection() as db:
            db.execute(
                "UPDATE channel_config SET demo_expires_at=NULL, updated_at=? WHERE guild_id=? AND channel_id=?",
                (_iso(datetime.now(timezone.utc)), guild_id, channel_id),
            )
        return self.get_channel_config(guild_id, channel_id)

    def list_active_demos(self, now: datetime | None = None) -> list[tuple[int, int, datetime]]:
        now = now or datetime.now(timezone.utc)
        with self.connection() as db:
            db.execute(
                "UPDATE channel_config SET demo_expires_at=NULL WHERE demo_expires_at IS NOT NULL AND demo_expires_at<=?",
                (_iso(now),),
            )
            rows = db.execute(
                """SELECT guild_id, channel_id, demo_expires_at FROM channel_config
                   WHERE enabled=1 AND demo_expires_at>?""",
                (_iso(now),),
            ).fetchall()
        return [
            (int(row["guild_id"]), int(row["channel_id"]), _dt(row["demo_expires_at"]))
            for row in rows
        ]

    def set_mention_preference(
        self, guild_id: int, channel_id: int, user_id: str, enabled: bool
    ) -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO mention_preferences(guild_id,channel_id,user_id,enabled,updated_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(guild_id,channel_id,user_id) DO UPDATE SET
                   enabled=excluded.enabled, updated_at=excluded.updated_at""",
                (guild_id, channel_id, user_id, int(enabled), _iso(datetime.now(timezone.utc))),
            )

    def get_mentionable_users(self, guild_id: int, channel_id: int) -> frozenset[str]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT user_id FROM mention_preferences WHERE guild_id=? AND channel_id=? AND enabled=1",
                (guild_id, channel_id),
            ).fetchall()
        return frozenset(str(row["user_id"]) for row in rows)

    def register_participant(self, guild_id: int, channel_id: int, user_key: str, now: datetime) -> int:
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO participants VALUES(?,?,?,?)",
                (guild_id, channel_id, user_key, _iso(now)),
            )
            row = db.execute(
                "SELECT COUNT(*) AS count FROM participants WHERE guild_id=? AND channel_id=?",
                (guild_id, channel_id),
            ).fetchone()
            return int(row["count"])

    def get_last_action(self, guild_id: int, channel_id: int, user_key: str) -> datetime | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT last_action_at FROM cooldowns WHERE guild_id=? AND channel_id=? AND user_key=?",
                (guild_id, channel_id, user_key),
            ).fetchone()
        return _dt(row["last_action_at"]) if row else None

    def record_action(self, guild_id: int, channel_id: int, user_key: str, now: datetime) -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO cooldowns VALUES(?,?,?,?)
                   ON CONFLICT(guild_id, channel_id, user_key) DO UPDATE SET
                   last_action_at=excluded.last_action_at""",
                (guild_id, channel_id, user_key, _iso(now)),
            )

    def create_poll(
        self,
        guild_id: int,
        channel_id: int,
        title: str,
        prompt: str,
        choices: tuple[str, ...],
        expires_at: datetime,
    ) -> PollRecord:
        poll = PollRecord(
            id=uuid.uuid4().hex,
            guild_id=guild_id,
            channel_id=channel_id,
            title=title[:80],
            prompt=prompt[:240],
            choices=choices,
            expires_at=expires_at,
            closed_at=None,
            winning_index=None,
            message_id=None,
        )
        with self.connection() as db:
            db.execute(
                "INSERT INTO polls VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    poll.id,
                    poll.guild_id,
                    poll.channel_id,
                    poll.title,
                    poll.prompt,
                    json.dumps(poll.choices),
                    _iso(poll.expires_at),
                    None,
                    None,
                    None,
                ),
            )
        return poll

    def set_poll_message(self, poll_id: str, message_id: int) -> None:
        with self.connection() as db:
            db.execute("UPDATE polls SET message_id=? WHERE id=?", (message_id, poll_id))

    def get_poll(self, poll_id: str) -> PollRecord | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM polls WHERE id=?", (poll_id,)).fetchone()
        return self._poll(row) if row else None

    def get_open_poll(self, guild_id: int, channel_id: int) -> PollRecord | None:
        with self.connection() as db:
            row = db.execute(
                """SELECT * FROM polls WHERE guild_id=? AND channel_id=? AND closed_at IS NULL
                   ORDER BY expires_at DESC LIMIT 1""",
                (guild_id, channel_id),
            ).fetchone()
        return self._poll(row) if row else None

    def list_open_polls(self) -> list[PollRecord]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM polls WHERE closed_at IS NULL").fetchall()
        return [self._poll(row) for row in rows]

    def add_vote(self, poll_id: str, user_key: str, choice_index: int, now: datetime) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO votes(poll_id,user_key,choice_index,voted_at) VALUES(?,?,?,?)",
                (poll_id, user_key, choice_index, _iso(now)),
            )

    def vote_counts(self, poll_id: str, choice_count: int) -> list[int]:
        counts = [0] * choice_count
        with self.connection() as db:
            rows = db.execute(
                "SELECT choice_index, COUNT(*) AS count FROM votes WHERE poll_id=? GROUP BY choice_index",
                (poll_id,),
            ).fetchall()
        for row in rows:
            if 0 <= row["choice_index"] < choice_count:
                counts[row["choice_index"]] = int(row["count"])
        return counts

    def close_poll(self, poll_id: str, winning_index: int, closed_at: datetime) -> bool:
        with self.connection() as db:
            result = db.execute(
                "UPDATE polls SET closed_at=?, winning_index=? WHERE id=? AND closed_at IS NULL",
                (_iso(closed_at), winning_index, poll_id),
            )
            return result.rowcount == 1

    @staticmethod
    def _poll(row: sqlite3.Row) -> PollRecord:
        return PollRecord(
            id=row["id"],
            guild_id=int(row["guild_id"]),
            channel_id=int(row["channel_id"]),
            title=row["title"],
            prompt=row["prompt"],
            choices=tuple(json.loads(row["choices_json"])),
            expires_at=_dt(row["expires_at"]),
            closed_at=_dt(row["closed_at"]),
            winning_index=row["winning_index"],
            message_id=row["message_id"],
        )

