"""Helpers for navigating the `event["options"]` tree of slash-command events.

Discord delivers slash command options as a nested list of dicts:
    [{"name": "subcmd", "type": 1, "options": [{"name": "campaign_id", "type": 4, "value": 5}, ...]}]

These helpers flatten that into easy lookups.

The platform exposes the options tree under TWO keys, ``options`` (canonical
SDK 0.5.3+) and ``command_options`` (legacy alias). Some platform versions
have a privacy-filter whitelist that drops one of them — we read ``options``
first and fall back to ``command_options`` so we work on every deployment.
"""
from typing import Any, Dict, List, Optional


def _opts(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the slash-command options list, tolerating either key name."""
    raw = event.get("options")
    if raw is None:
        raw = event.get("command_options")
    return list(raw or [])


def get_subcommand(event: Dict[str, Any]) -> Optional[str]:
    """Return the subcommand name, or None.

    A subcommand option in Discord's interaction data is identified by the
    absence of a ``value`` field — regular parameter options always carry
    one. We rely on that invariant instead of the ``type`` field because
    discord.py's data dict has been observed to omit the SUB_COMMAND
    ``type: 1`` marker in some delivery paths, breaking a type-based check.
    """
    options = _opts(event)
    if not options:
        return None
    first = options[0]
    if not isinstance(first, dict):
        return None
    name = first.get("name")
    if not name:
        return None
    # SUB_COMMAND / SUB_COMMAND_GROUP — explicit type wins when present
    if first.get("type") in (1, 2):
        return str(name)
    # Defensive fallback: a regular parameter option always has `value`.
    # If there's no `value`, this is a subcommand even if `type` is missing.
    if "value" not in first:
        return str(name)
    return None


def _subcommand_options(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the inner options list belonging to the (sub)command.

    Mirrors the heuristic in ``get_subcommand``: if the first option lacks
    a ``value`` field, treat it as a subcommand wrapper and descend into
    its ``options``.
    """
    options = _opts(event)
    if not options:
        return []
    first = options[0]
    if not isinstance(first, dict):
        return options
    if first.get("type") in (1, 2) or "value" not in first:
        return first.get("options") or []
    return options


def get_option(event: Dict[str, Any], name: str) -> Any:
    """Return the raw value of a subcommand option, or None."""
    for opt in _subcommand_options(event):
        if isinstance(opt, dict) and opt.get("name") == name:
            return opt.get("value")
    return None


def get_option_int(event: Dict[str, Any], name: str) -> Optional[int]:
    v = get_option(event, name)
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def get_option_str(event: Dict[str, Any], name: str) -> Optional[str]:
    v = get_option(event, name)
    if v is None:
        return None
    return str(v)


def get_option_bool(event: Dict[str, Any], name: str) -> Optional[bool]:
    v = get_option(event, name)
    if v is None:
        return None
    return bool(v)


def get_option_user_id(event: Dict[str, Any], name: str) -> Optional[str]:
    """User options (type 6) carry the user id as the value."""
    v = get_option(event, name)
    if v is None:
        return None
    return str(v)


def get_modal_value(event: Dict[str, Any], custom_id: str) -> str:
    """Read a single modal field value by its inner custom_id."""
    return str((event.get("modal_values") or {}).get(custom_id) or "").strip()


def get_invoking_user_id(event: Dict[str, Any]) -> str:
    member = event.get("member") or {}
    user = member.get("user") or {}
    return str(user.get("id") or event.get("user_id") or "")
