"""Pytest fixtures and a small stub-able SQL backend.

The SDK's `_MockSql` records calls but always returns `[]` / `0`.
Our handlers use INSERT…RETURNING and rely on row data coming back, so we
provide `StubSql` that lets each test set per-query return values.
"""
import os
import sys
from typing import Any, Callable, Dict, List, Optional

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mmo_maid_sdk.testing import MockContext, MockClock, make_event  # noqa: E402


class StubSql:
    """Records executed SQL and lets tests register canned responses.

    Usage:
        ctx.sql = StubSql()
        ctx.sql.next_query([{"id": 1, "name": "x"}])
        ctx.sql.next_execute(1)
        ...
    """

    def __init__(self) -> None:
        self.executed: List[Dict[str, Any]] = []
        self._execute_queue: List[Any] = []
        self._query_queue: List[Any] = []
        self._query_one_queue: List[Any] = []
        self._scalar_queue: List[Any] = []
        # Matcher-style: register by SQL substring → callable(params)->result
        self._execute_matchers: List = []
        self._query_matchers: List = []
        self._query_one_matchers: List = []
        self._scalar_matchers: List = []

    def next_execute(self, value: int = 1) -> None:
        self._execute_queue.append(int(value))

    def next_query(self, rows: List[Dict[str, Any]]) -> None:
        self._query_queue.append(list(rows))

    def next_query_one(self, row: Optional[Dict[str, Any]]) -> None:
        self._query_one_queue.append(row)

    def next_scalar(self, value: Any) -> None:
        self._scalar_queue.append(value)

    def on_execute(self, sql_substring: str, handler: Callable[[Any], int]) -> None:
        self._execute_matchers.append((sql_substring, handler))

    def on_query(self, sql_substring: str, handler: Callable[[Any], List[Dict[str, Any]]]) -> None:
        self._query_matchers.append((sql_substring, handler))

    def on_query_one(self, sql_substring: str, handler: Callable[[Any], Optional[Dict[str, Any]]]) -> None:
        self._query_one_matchers.append((sql_substring, handler))

    def on_scalar(self, sql_substring: str, handler: Callable[[Any], Any]) -> None:
        self._scalar_matchers.append((sql_substring, handler))

    # API methods matching _SqlApi
    def execute(self, sql: str, params: Optional[list] = None) -> int:
        self.executed.append({"op": "execute", "sql": sql, "params": params})
        for sub, handler in self._execute_matchers:
            if sub in sql:
                return int(handler(params))
        if self._execute_queue:
            return int(self._execute_queue.pop(0))
        return 0

    def query(self, sql: str, params: Optional[list] = None, *, limit: int = 1000) -> List[Dict[str, Any]]:
        self.executed.append({"op": "query", "sql": sql, "params": params})
        for sub, handler in self._query_matchers:
            if sub in sql:
                return list(handler(params))
        if self._query_queue:
            return list(self._query_queue.pop(0))
        return []

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[Dict[str, Any]]:
        self.executed.append({"op": "query_one", "sql": sql, "params": params})
        for sub, handler in self._query_one_matchers:
            if sub in sql:
                return handler(params)
        if self._query_one_queue:
            return self._query_one_queue.pop(0)
        return None

    def scalar(self, sql: str, params: Optional[list] = None) -> Any:
        self.executed.append({"op": "scalar", "sql": sql, "params": params})
        for sub, handler in self._scalar_matchers:
            if sub in sql:
                return handler(params)
        if self._scalar_queue:
            return self._scalar_queue.pop(0)
        return None


@pytest.fixture
def ctx():
    c = MockContext(
        server_id="999",
        plugin_id="dnd_campaign_manager",
        version="1.0.0",
    )
    c.sql = StubSql()
    return c


@pytest.fixture
def admin_event():
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="campaign",
        guild_id="999",
        user_id="1001",
        member={
            "user": {"id": "1001"},
            "roles": [],
            "permissions": str(0x8),  # ADMINISTRATOR
        },
    )


@pytest.fixture
def player_event():
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="campaign",
        guild_id="999",
        user_id="2002",
        member={
            "user": {"id": "2002"},
            "roles": ["7777"],
            "permissions": "0",
        },
    )


@pytest.fixture
def dm_role_event():
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="campaign",
        guild_id="999",
        user_id="3003",
        member={
            "user": {"id": "3003"},
            "roles": ["55555"],  # the DM role id used in fixture settings
            "permissions": "0",
        },
    )


@pytest.fixture
def sample_campaign():
    return {
        "id": 42,
        "discord_srv_id": 999,
        "name": "Lost Mines",
        "party_name": "The Lost Mines Crew",
        "system": "D&D 5e",
        "description": "Phandelver and beyond.",
        "timezone": "UTC",
        "owner_user_id": 1001,
        "status": "active",
    }


@pytest.fixture
def sample_settings():
    return {
        "campaign_id": 42,
        "announce_channel_id": 12345,
        "recap_channel_id": 12346,
        "reminder_channel_id": 12347,
        "dm_role_id": 55555,
        "player_role_id": 66666,
        "reminder_offsets_minutes": [1440, 120, 15],
        "rsvp_required": False,
        "maybe_allowed": True,
        "alternate_times_allowed": False,
        "recap_draft_first": True,
        "quest_log_public": True,
        "npc_default_visibility": "public",
        "ping_on_reminders": False,
    }
