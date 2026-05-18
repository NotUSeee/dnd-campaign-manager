"""Friendly error wrapper for Discord API calls.

The SDK raises ``DiscordApiError``, ``SdkPermissionError`` (alias
``PermissionError``), and ``RateLimitError`` when the bot can't perform
an action. Handlers that bubble those exceptions show the user a generic
"Something went wrong" — not useful. These helpers catch the common
failures and surface a specific, actionable ephemeral reply.
"""
from __future__ import annotations

from typing import Any, Optional

from mmo_maid_sdk import (
    DiscordApiError,
    RateLimitError,
    SdkPermissionError,
)


def friendly_message(exc: Exception, *, action: str = "do that") -> str:
    """Translate an SDK error into one short sentence the user can act on."""
    if isinstance(exc, SdkPermissionError):
        return (
            f"I can't {action} — the bot is missing a required Discord permission. "
            "Ask a server admin to grant the right channel/role permissions."
        )
    if isinstance(exc, RateLimitError):
        retry = getattr(exc, "retry_after", None)
        if retry:
            return f"Rate-limited — please try again in {int(retry)}s."
        return "Rate-limited — please try again shortly."
    if isinstance(exc, DiscordApiError):
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status == 404:
            return (
                f"Couldn't {action} — Discord says the target channel, role, "
                "or message no longer exists. Check `/campaign settings`."
            )
        if status == 403:
            return (
                f"I can't {action} — the bot is missing a required Discord permission. "
                "Make sure the bot can view + send messages in the configured channel."
            )
        if status:
            return f"Discord rejected the request ({status}). Please try again."
    return f"Couldn't {action} — an unexpected error occurred. Please try again."


def respond_friendly_error(ctx, exc: Exception, *, action: str = "do that") -> None:
    """Send an ephemeral, user-friendly error reply for an SDK failure.

    Safe to call after `defer()` (uses followup) or before any response.
    Silently swallows any error from the response call itself so we don't
    cascade.
    """
    msg = friendly_message(exc, action=action)
    try:
        ctx.interaction.respond(content=msg, ephemeral=True)
    except Exception:
        try:
            ctx.interaction.followup(content=msg, ephemeral=True)
        except Exception:
            pass
    try:
        ctx.log(
            f"discord_error: {type(exc).__name__}: {exc} (action={action})",
            level="warning", tags=["discord_error"],
        )
    except Exception:
        pass


def safe_send_message(
    ctx, *, channel_id: str, action: str = "post the message",
    on_error_respond: bool = True, **kwargs: Any,
) -> Optional[str]:
    """Wrap ctx.discord.send_message — returns message_id on success, None on failure.

    On failure (PermissionError / 403 / 404), optionally responds to the
    interaction with a friendly message.
    """
    try:
        result = ctx.discord.send_message(channel_id=str(channel_id), **kwargs)
        return (result or {}).get("message_id") if isinstance(result, dict) else None
    except (DiscordApiError, RateLimitError, SdkPermissionError) as exc:
        if on_error_respond:
            respond_friendly_error(ctx, exc, action=action)
        return None
    except Exception as exc:  # noqa: BLE001
        if on_error_respond:
            respond_friendly_error(ctx, exc, action=action)
        return None


def safe_edit_message(
    ctx, *, channel_id: str, message_id: str,
    action: str = "update the message", on_error_respond: bool = False, **kwargs: Any,
) -> bool:
    """Wrap ctx.discord.edit_message — returns True on success.

    Defaults to NOT responding to the interaction on failure — edits are
    usually background updates (RSVP refresh) where surfacing the error is
    spurious. Pass `on_error_respond=True` if it matters.
    """
    try:
        ctx.discord.edit_message(
            channel_id=str(channel_id), message_id=str(message_id), **kwargs
        )
        return True
    except (DiscordApiError, RateLimitError, SdkPermissionError) as exc:
        if on_error_respond:
            respond_friendly_error(ctx, exc, action=action)
        try:
            ctx.log(
                f"safe_edit_message: {type(exc).__name__}: {exc}",
                level="warning", tags=["discord_error"],
            )
        except Exception:
            pass
        return False
    except Exception as exc:  # noqa: BLE001
        try:
            ctx.log(
                f"safe_edit_message: {type(exc).__name__}: {exc}",
                level="warning", tags=["discord_error"],
            )
        except Exception:
            pass
        return False
