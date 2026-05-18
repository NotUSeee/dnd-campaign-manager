"""Reminder dispatcher — at-most-once dedup, stale-window skip, recompute next_due."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

from plugin_module.core import time_util
from plugin_module.handlers import scheduled


# We test the dispatcher's *decision logic* by directly invoking the helper that
# operates on a session dict. This avoids needing a real Postgres and exercises
# the at-most-once primitive via the StubSql.

class _RecordingSql:
    """Specialized stub that simulates the array_append atomic UPDATE."""

    def __init__(self, initial_offsets_sent: List[int]) -> None:
        self.offsets_sent: List[int] = list(initial_offsets_sent)
        self.reminders_posted: List[int] = []
        self.executed: List[Dict[str, Any]] = []
        self._scalar_queue: List[Any] = []

    def execute(self, sql: str, params: Any = None) -> int:
        self.executed.append({"sql": sql, "params": params})
        if "array_append(reminder_offsets_sent" in sql:
            offset = int(params[0])
            if offset in self.offsets_sent:
                return 0
            self.offsets_sent.append(offset)
            return 1
        if "SET next_reminder_due_at" in sql:
            return 1
        return 1

    def query(self, sql: str, params: Any = None, *, limit: int = 1000):
        return []

    def query_one(self, sql: str, params: Any = None):
        return None

    def scalar(self, sql: str, params: Any = None):
        return self._scalar_queue.pop(0) if self._scalar_queue else None


def _ctx_for_reminders(ctx, *, settings: Dict[str, Any], session_row: Dict[str, Any]):
    """Wire a ctx so the dispatcher can read settings + the session back."""
    rec = _RecordingSql(session_row.get("reminder_offsets_sent") or [])
    ctx.sql = rec

    rec_settings = dict(settings)
    rec_session = dict(session_row)
    rec_settings["reminder_offsets_minutes"] = list(settings.get("reminder_offsets_minutes") or [])

    def _q1(sql: str, params: Any = None):
        # The settings lookup joins from dnd_sessions to dnd_campaign_settings
        if "dnd_campaign_settings" in sql:
            return rec_settings
        # The session refresh selects from dnd_sessions WHERE id = %s
        if "FROM dnd_sessions" in sql and "WHERE id" in sql:
            refreshed = dict(rec_session)
            refreshed["reminder_offsets_sent"] = list(rec.offsets_sent)
            return refreshed
        return None

    rec.query_one = _q1
    return rec


def _session_dict(**overrides) -> Dict[str, Any]:
    base = {
        "id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "session_number": 5, "title": "Test",
        "starts_at": datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc),
        "duration_minutes": 240, "status": "scheduled",
        "announce_channel_id": 12345, "announce_message_id": 99999,
        "reminder_offsets_sent": [],
    }
    base.update(overrides)
    return base


def _settings(**overrides) -> Dict[str, Any]:
    base = {
        "campaign_id": 42,
        "reminder_offsets_minutes": [1440, 120, 15],
        "reminder_channel_id": 12347,
        "announce_channel_id": 12345,
        "player_role_id": None,
        "ping_on_reminders": False,
        "campaign_name": "Lost Mines",
        "timezone": "UTC",
    }
    base.update(overrides)
    return base


def test_dispatcher_posts_15m_reminder(ctx):
    starts = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=15)
    session = _session_dict(starts_at=starts)
    rec = _ctx_for_reminders(ctx, settings=_settings(), session_row=session)

    scheduled._send_for_session(ctx, session, now)

    # 15 should now be in sent
    assert 15 in rec.offsets_sent
    # Message was sent to the reminder channel
    assert len(ctx.discord.messages_sent) == 1
    msg = ctx.discord.messages_sent[0]
    assert msg["channel_id"] == "12347"
    assert "15m" in msg["embeds"][0]["title"]
    # No content (no ping)
    assert msg["content"] == ""


def test_dispatcher_dedupes_within_same_tick(ctx):
    starts = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=15)
    session = _session_dict(starts_at=starts, reminder_offsets_sent=[15])
    _ctx_for_reminders(ctx, settings=_settings(), session_row=session)

    scheduled._send_for_session(ctx, session, now)

    # Already sent → no new post
    assert ctx.discord.messages_sent == []


def test_dispatcher_skips_stale_offset_after_session_started(ctx):
    starts = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    now = starts + timedelta(hours=2)  # 2 hours after session
    session = _session_dict(starts_at=starts)
    _ctx_for_reminders(ctx, settings=_settings(), session_row=session)

    scheduled._send_for_session(ctx, session, now)

    assert ctx.discord.messages_sent == []


def test_dispatcher_pings_role_when_opted_in(ctx):
    starts = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=15)
    session = _session_dict(starts_at=starts)
    settings = _settings(player_role_id=66666, ping_on_reminders=True)
    _ctx_for_reminders(ctx, settings=settings, session_row=session)

    scheduled._send_for_session(ctx, session, now)
    assert len(ctx.discord.messages_sent) == 1
    msg = ctx.discord.messages_sent[0]
    assert "<@&66666>" in msg["content"]
    assert msg["files"] is None  # no files attached


def test_dispatcher_marks_stale_offsets_sent_without_posting(ctx):
    """When the bot was down, late reminders with misleading labels are marked
    sent but not posted — only the freshest (the 15m, since session is 10m out)
    actually goes out."""
    starts = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=10)
    session = _session_dict(starts_at=starts, reminder_offsets_sent=[1440])
    rec = _ctx_for_reminders(ctx, settings=_settings(), session_row=session)

    scheduled._send_for_session(ctx, session, now)

    # 120 was stale (would say "2h" but it's actually 10m) — silently marked sent
    assert 120 in rec.offsets_sent
    # 15 was fresh and fired
    assert 15 in rec.offsets_sent
    # Only the 15m reminder actually posted
    assert len(ctx.discord.messages_sent) == 1
    assert "15m" in ctx.discord.messages_sent[0]["embeds"][0]["title"]
