"""Helpers for navigating the `event["options"]` tree of slash-command events.

Discord delivers slash command options as a nested list of dicts:
    [{"name": "subcmd", "type": 1, "options": [{"name": "campaign_id", "type": 4, "value": 5}, ...]}]

These helpers flatten that into easy lookups.
"""
from typing import Any, Dict, List, Optional


def get_subcommand(event: Dict[str, Any]) -> Optional[str]:
    """Return the subcommand name, or None."""
    options = event.get("options") or []
    if not options:
        return None
    first = options[0]
    # type 1 = SUB_COMMAND, type 2 = SUB_COMMAND_GROUP (we don't use groups currently)
    if isinstance(first, dict) and first.get("type") in (1, 2) and first.get("name"):
        return str(first["name"])
    return None


def _subcommand_options(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the inner options list belonging to the (sub)command."""
    options = event.get("options") or []
    if not options:
        return []
    first = options[0]
    if isinstance(first, dict) and first.get("type") in (1, 2):
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
