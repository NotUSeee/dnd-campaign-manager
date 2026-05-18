"""Friendly error wrapping — DiscordApiError / PermissionError / RateLimitError."""
from mmo_maid_sdk import DiscordApiError, RateLimitError, SdkPermissionError

from plugin_module.core import safe_discord


def test_friendly_message_for_permission_error():
    msg = safe_discord.friendly_message(SdkPermissionError("missing"), action="post the message")
    assert "missing a required Discord permission" in msg
    assert "post the message" in msg


def test_friendly_message_for_403():
    exc = DiscordApiError("forbidden")
    exc.status_code = 403
    msg = safe_discord.friendly_message(exc, action="edit the embed")
    assert "missing a required Discord permission" in msg


def test_friendly_message_for_404():
    exc = DiscordApiError("not found")
    exc.status_code = 404
    msg = safe_discord.friendly_message(exc, action="post the recap")
    assert "no longer exists" in msg


def test_friendly_message_for_rate_limit_with_retry():
    exc = RateLimitError("slow down")
    exc.retry_after = 12.4
    msg = safe_discord.friendly_message(exc)
    assert "12s" in msg


def test_friendly_message_for_unknown_exception():
    msg = safe_discord.friendly_message(RuntimeError("boom"), action="do that")
    assert "unexpected" in msg.lower()


def test_respond_friendly_error_logs_and_replies(ctx):
    exc = SdkPermissionError("denied")
    safe_discord.respond_friendly_error(ctx, exc, action="post the message")
    assert len(ctx.interaction.responses) == 1
    assert ctx.interaction.responses[0]["ephemeral"] is True
    # Should also have logged
    assert any("discord_error" in (e.get("tags") or []) for e in ctx.log_entries)


class _FailingDiscord:
    """Drop-in replacement that raises on send_message."""

    def __init__(self, exc):
        self._exc = exc
        self.messages_sent = []

    def send_message(self, **kwargs):
        raise self._exc

    def edit_message(self, **kwargs):
        raise self._exc


def test_safe_send_message_returns_none_on_permission_error(ctx):
    ctx.discord = _FailingDiscord(SdkPermissionError("denied"))
    result = safe_discord.safe_send_message(
        ctx, channel_id="1", action="post the message",
        embeds=[{"title": "x"}],
    )
    assert result is None
    # Friendly response was sent
    assert any(
        "missing a required Discord permission" in r["content"]
        for r in ctx.interaction.responses
    )


def test_safe_send_message_returns_id_on_success(ctx):
    msg_id = safe_discord.safe_send_message(
        ctx, channel_id="1", action="post", content="hi"
    )
    assert msg_id == "1"


def test_safe_edit_message_swallows_error_silently_by_default(ctx):
    ctx.discord = _FailingDiscord(DiscordApiError("404"))
    ok = safe_discord.safe_edit_message(
        ctx, channel_id="1", message_id="2", embeds=[{"title": "x"}],
    )
    assert ok is False
    # No ephemeral response by default — edit failures are usually silent
    assert ctx.interaction.responses == []
