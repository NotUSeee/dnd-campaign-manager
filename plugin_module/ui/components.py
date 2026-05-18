"""Component (button + select) builders.

Pure functions: take dicts, return SDK component objects.
"""
from typing import Any, Dict, List

from mmo_maid_sdk import ActionRow, Button, SelectMenu, SelectOption

from plugin_module.constants import SELECT_OPTIONS_MAX
from plugin_module.core import ids
from plugin_module.core.time_util import discord_timestamp, now_utc


# ── RSVP buttons (on the session announcement embed) ──────────────────────


def rsvp_buttons(session_id: int, *, maybe_allowed: bool = True) -> List[ActionRow]:
    row = ActionRow(
        Button(
            "Attending",
            custom_id=ids.rsvp_id(session_id, "attending"),
            style="success",
            emoji="✅",
        ),
        Button(
            "Maybe",
            custom_id=ids.rsvp_id(session_id, "maybe"),
            style="secondary",
            emoji="❔",
            disabled=not maybe_allowed,
        ),
        Button(
            "Unavailable",
            custom_id=ids.rsvp_id(session_id, "unavailable"),
            style="danger",
            emoji="❌",
        ),
    )
    return [row]


def session_announce_components(
    session: Dict[str, Any],
    *,
    maybe_allowed: bool = True,
    alternate_times_allowed: bool = False,
    campaign_id: int = 0,
) -> List[ActionRow]:
    """RSVP buttons + secondary action row (info / alt-time / recap)."""
    rows = rsvp_buttons(int(session["id"]), maybe_allowed=maybe_allowed)

    secondary: List = []
    if campaign_id:
        secondary.append(
            Button(
                "Campaign Info",
                custom_id=ids.view_campaign_info_id(int(campaign_id)),
                style="secondary",
                emoji="ℹ️",
            )
        )
    if alternate_times_allowed:
        secondary.append(
            Button(
                "Propose alternate time",
                custom_id=ids.suggest_alt_time_btn_id(int(session["id"])),
                style="secondary",
                emoji="🕓",
            )
        )

    # 'Create Recap' once the session has ended (best-effort time check)
    starts_at = session.get("starts_at")
    duration = int(session.get("duration_minutes") or 0)
    if starts_at:
        from datetime import timedelta
        end = starts_at + timedelta(minutes=duration)
        if now_utc() >= end:
            secondary.append(
                Button(
                    "Create Recap",
                    custom_id=ids.recap_create_btn_id(int(session["id"])),
                    style="primary",
                    emoji="📜",
                )
            )

    if secondary:
        rows.append(ActionRow(*secondary[:5]))
    return rows


def recap_list_components(recaps: List[Dict[str, Any]]) -> List[ActionRow]:
    """One row of up-to-5 'View' buttons for recap list embeds.

    Returns at most one row — older recaps fall back to the message link.
    """
    if not recaps:
        return []
    btns = []
    for r in recaps[:5]:
        title = str(r.get("title") or f"Session {r.get('session_number') or r['id']}")
        label = f"View: {title}"[:80]
        btns.append(
            Button(label, custom_id=ids.recap_view_id(int(r["id"])), style="secondary", emoji="📜")
        )
    return [ActionRow(*btns)]


def campaign_info_components(campaign_id: int) -> List[ActionRow]:
    """Quick-action buttons shown under the campaign info embed."""
    return [
        ActionRow(
            Button(
                "View past recaps",
                custom_id=ids.view_campaign_recaps_id(int(campaign_id)),
                style="secondary",
                emoji="📜",
            ),
        )
    ]


# ── Settings panel ──────────────────────────────────────────────────────


def settings_panel_components(campaign_id: int) -> List[ActionRow]:
    """Two rows of edit buttons shown under the settings summary embed."""
    return [
        ActionRow(
            Button("Channels", custom_id=ids.settings_edit_btn_id("channels", campaign_id),
                   style="primary", emoji="📺"),
            Button("Roles", custom_id=ids.settings_edit_btn_id("roles", campaign_id),
                   style="primary", emoji="🎭"),
            Button("Reminders", custom_id=ids.settings_edit_btn_id("reminders", campaign_id),
                   style="primary", emoji="⏰"),
            Button("Defaults", custom_id=ids.settings_edit_btn_id("defaults", campaign_id),
                   style="primary", emoji="🗓"),
        ),
        ActionRow(
            Button("Toggles", custom_id=ids.settings_edit_btn_id("toggles", campaign_id),
                   style="secondary", emoji="⚙️"),
            Button("NPC visibility default",
                   custom_id=ids.settings_edit_btn_id("npc_vis", campaign_id),
                   style="secondary", emoji="🧙"),
        ),
    ]


_TOGGLE_LABELS = [
    ("rsvp_required", "RSVP required"),
    ("maybe_allowed", "Allow 'Maybe' RSVPs"),
    ("alternate_times_allowed", "Allow players to propose alternate times"),
    ("recap_draft_first", "Recap drafts before posting"),
    ("quest_log_public", "Quest log visible to players"),
    ("ping_on_reminders", "Ping player role on reminders"),
]


def toggles_panel_components(campaign_id: int, settings: Dict[str, Any]) -> List[ActionRow]:
    """One button per toggle, each shows the current state and flips on click."""
    rows: List[ActionRow] = []
    bucket: List = []
    for key, label in _TOGGLE_LABELS:
        on = bool(settings.get(key, key in {"maybe_allowed", "recap_draft_first", "quest_log_public"}))
        emoji = "✅" if on else "⬜"
        style = "success" if on else "secondary"
        btn = Button(
            f"{label}"[:80],
            custom_id=ids.settings_toggle_btn_id(key, campaign_id),
            style=style, emoji=emoji,
        )
        bucket.append(btn)
        if len(bucket) == 2:
            rows.append(ActionRow(*bucket))
            bucket = []
    if bucket:
        rows.append(ActionRow(*bucket))
    rows.append(ActionRow(
        Button("Back to settings", custom_id=ids.settings_back_btn_id(campaign_id),
               style="secondary", emoji="↩️")
    ))
    return rows


def npc_visibility_select(campaign_id: int, current: str = "public") -> List[ActionRow]:
    options = [
        SelectOption("Public — everyone sees it", "public",
                     description="Players see name, role, location, public notes",
                     default=(current == "public"), emoji="🌍"),
        SelectOption("Partial — name + role only", "partial",
                     description="Players see name and role; details hidden",
                     default=(current == "partial"), emoji="🌗"),
        SelectOption("DM-only — never shown to players", "dm_only",
                     description="Only DMs and admins can see this NPC",
                     default=(current == "dm_only"), emoji="🔒"),
    ]
    return [
        ActionRow(SelectMenu(
            ids.settings_npc_vis_select_id(campaign_id),
            options=options,
            placeholder="Pick the default visibility for new NPCs…",
        )),
        ActionRow(
            Button("Back to settings", custom_id=ids.settings_back_btn_id(campaign_id),
                   style="secondary", emoji="↩️"),
        ),
    ]


# ── Cancel confirmation ───────────────────────────────────────────────────


def cancel_confirm_buttons(session_id: int) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                "Confirm Cancel",
                custom_id=ids.cancel_confirm_id(session_id),
                style="danger",
                emoji="🛑",
            ),
            Button(
                "Keep It",
                custom_id=ids.cancel_keep_id(session_id),
                style="secondary",
            ),
        )
    ]


# ── Recap preview action buttons ──────────────────────────────────────────


def recap_preview_buttons(recap_id: int) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                "Post to Channel",
                custom_id=ids.recap_post_id(recap_id),
                style="success",
                emoji="📤",
            ),
            Button(
                "Keep as Draft",
                custom_id=ids.recap_keep_id(recap_id),
                style="secondary",
            ),
            Button(
                "Add DM Notes",
                custom_id=ids.recap_dmnotes_id(recap_id),
                style="secondary",
                emoji="📝",
            ),
        )
    ]


# ── Visibility pickers (button row before a modal) ────────────────────────


def visibility_picker(
    target: str,
    campaign_id: int,
    *,
    allow_partial: bool = False,
    default_visibility: str = "public",
) -> List[ActionRow]:
    """Build the public/partial/dm_only button row.

    The button matching `default_visibility` is rendered first with a star
    marker so DMs see their configured default as the obvious primary action.
    """
    specs = [
        ("public", "Public", "success", "🌍"),
    ]
    if allow_partial:
        specs.append(("partial", "Partial", "secondary", "🌗"))
    specs.append(("dm_only", "DM-only", "danger", "🔒"))

    if default_visibility in {s[0] for s in specs}:
        specs.sort(key=lambda s: 0 if s[0] == default_visibility else 1)

    btns = []
    for value, label, style, emoji in specs:
        if value == default_visibility:
            label = f"★ {label} (default)"
        btns.append(
            Button(
                label,
                custom_id=ids.visibility_btn_id(target, value, campaign_id),
                style=style,
                emoji=emoji,
            )
        )
    return [ActionRow(*btns)]


# ── Recurrence picker ─────────────────────────────────────────────────────


def recurrence_picker(session_id: int) -> List[ActionRow]:
    options = [
        SelectOption("One-time (no recurrence)", "none", emoji="1️⃣"),
        SelectOption("Weekly (same time each week)", "weekly", emoji="🗓"),
        SelectOption("Biweekly (every 2 weeks)", "biweekly", emoji="🗓"),
        SelectOption("Monthly (same day each month)", "monthly", emoji="🗓"),
    ]
    return [
        ActionRow(
            SelectMenu(
                ids.recurrence_picker_id(session_id),
                options=options,
                placeholder="Make this a recurring session?",
            )
        )
    ]


# ── Campaign & session pickers ────────────────────────────────────────────


def campaign_picker(
    target: str, campaigns: List[Dict[str, Any]], *, placeholder: str = "Pick a campaign…"
) -> List[ActionRow]:
    if not campaigns:
        return []
    options: List[SelectOption] = []
    for c in campaigns[:SELECT_OPTIONS_MAX]:
        label = str(c.get("name") or f"Campaign {c['id']}")[:100]
        desc = (c.get("party_name") or c.get("system") or "")[:100]
        options.append(SelectOption(label, str(c["id"]), description=desc or None))
    return [
        ActionRow(
            SelectMenu(ids.picker_id(target), options=options, placeholder=placeholder[:150])
        )
    ]


def session_picker(
    target: str, sessions: List[Dict[str, Any]], *, placeholder: str = "Pick a session…"
) -> List[ActionRow]:
    if not sessions:
        return []
    options: List[SelectOption] = []
    for s in sessions[:SELECT_OPTIONS_MAX]:
        starts = s.get("starts_at")
        title = str(s.get("title") or f"Session {s.get('session_number') or s['id']}")[:80]
        label = f"#{s.get('session_number') or s['id']} — {title}"[:100]
        desc = ""
        if starts:
            desc = discord_timestamp(starts, style="f")
            # SelectOption description shows literal text — strip Discord tags
            desc = f"Starts {desc}"[:100]
        options.append(SelectOption(label, str(s["id"]), description=desc or None))
    return [
        ActionRow(
            SelectMenu(ids.picker_id(target), options=options, placeholder=placeholder[:150])
        )
    ]


def quest_picker(
    target: str, quests: List[Dict[str, Any]], *, placeholder: str = "Pick a quest…"
) -> List[ActionRow]:
    if not quests:
        return []
    options: List[SelectOption] = []
    for q in quests[:SELECT_OPTIONS_MAX]:
        label = str(q.get("title") or f"Quest {q['id']}")[:100]
        status = str(q.get("status") or "active")
        desc = f"Status: {status}"[:100]
        options.append(SelectOption(label, str(q["id"]), description=desc))
    return [
        ActionRow(
            SelectMenu(ids.picker_id(target), options=options, placeholder=placeholder[:150])
        )
    ]


def attendance_select(session_id: int, rsvped_user_ids: List[int]) -> List[ActionRow]:
    """SelectMenu of RSVP'd users with min/max=many — DM picks attendees.

    Returns up to one row; empty list if there's nobody to pick.
    """
    if not rsvped_user_ids:
        return []
    options = []
    for uid in rsvped_user_ids[:SELECT_OPTIONS_MAX]:
        options.append(SelectOption(f"User {uid}", str(uid)))
    return [
        ActionRow(
            SelectMenu(
                f"{ids.PICKER_PREFIX}attendance:{session_id}"[:100],
                options=options,
                placeholder="Select everyone who attended…",
                min_values=0,
                max_values=min(SELECT_OPTIONS_MAX, len(options)),
            )
        )
    ]
