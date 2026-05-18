"""Embed builders. Pure functions that take dicts and return embed dicts.

Discord embeds are dicts with shape:
    {"title": ..., "description": ..., "color": int, "fields": [...], "footer": {...}, ...}
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from plugin_module.constants import (
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
)
from plugin_module.core.time_util import (
    discord_timestamp,
    discord_timestamp_relative,
    format_duration,
    format_offset_label,
)
from plugin_module.ui.format import (
    boolean_label,
    join_user_mentions,
    mention_channel,
    mention_role,
    mention_user,
    offsets_summary,
    status_label,
    truncate,
    visibility_label,
    weekday_name,
)


# ── Generic helpers ───────────────────────────────────────────────────────


def _field(name: str, value: str, *, inline: bool = False) -> Dict[str, Any]:
    return {"name": str(name)[:256], "value": str(value)[:1024] or "—", "inline": bool(inline)}


def info_embed(title: str, description: str = "") -> Dict[str, Any]:
    return {
        "title": str(title)[:256],
        "description": str(description)[:4096],
        "color": COLOR_INFO,
    }


def success_embed(title: str, description: str = "") -> Dict[str, Any]:
    return {
        "title": f"✅ {title}"[:256],
        "description": str(description)[:4096],
        "color": COLOR_SUCCESS,
    }


def error_embed(title: str, description: str = "") -> Dict[str, Any]:
    return {
        "title": f"⚠️ {title}"[:256],
        "description": str(description)[:4096],
        "color": COLOR_DANGER,
    }


# ── Campaign embeds ───────────────────────────────────────────────────────


def campaign_created_embed(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": f"🎲 Campaign created: {campaign['name']}",
        "description": (campaign.get("description") or
                        "Run `/campaign settings` to choose channels and roles, "
                        "then `/session schedule` to plan your first session."),
        "color": COLOR_SUCCESS,
        "fields": [
            _field("Party", campaign.get("party_name") or "—", inline=True),
            _field("System", campaign.get("system") or "—", inline=True),
            _field("Timezone", campaign.get("timezone") or "UTC", inline=True),
            _field("DM", mention_user(campaign.get("owner_user_id")), inline=True),
        ],
        "footer": {"text": f"Campaign ID: {campaign['id']}"},
    }


def campaign_info_embed(
    campaign: Dict[str, Any],
    settings: Optional[Dict[str, Any]],
    *,
    next_session: Optional[Dict[str, Any]] = None,
    party_size: int = 0,
    active_quest_count: int = 0,
) -> Dict[str, Any]:
    settings = settings or {}
    fields = [
        _field("Party", campaign.get("party_name") or "—", inline=True),
        _field("System", campaign.get("system") or "—", inline=True),
        _field("Timezone", campaign.get("timezone") or "UTC", inline=True),
        _field("DM", mention_user(campaign.get("owner_user_id")), inline=True),
        _field("DM role", mention_role(settings.get("dm_role_id")), inline=True),
        _field("Player role", mention_role(settings.get("player_role_id")), inline=True),
        _field("Announcements", mention_channel(settings.get("announce_channel_id")), inline=True),
        _field("Recaps", mention_channel(settings.get("recap_channel_id")), inline=True),
        _field("Reminders", mention_channel(settings.get("reminder_channel_id")), inline=True),
        _field("Party size", str(party_size), inline=True),
        _field("Active quests", str(active_quest_count), inline=True),
        _field("Status", status_label(campaign.get("status") or "active"), inline=True),
    ]
    if next_session:
        starts = next_session.get("starts_at")
        title = next_session.get("title") or f"Session {next_session.get('session_number') or '?'}"
        fields.insert(
            0,
            _field(
                "Next session",
                f"**{title}** — {discord_timestamp(starts)} ({discord_timestamp_relative(starts)})",
            ),
        )
    return {
        "title": f"🎲 {campaign['name']}",
        "description": truncate(campaign.get("description") or "", 4000),
        "color": COLOR_PRIMARY,
        "fields": fields,
        "footer": {"text": f"Campaign ID: {campaign['id']}"},
    }


def campaign_settings_summary_embed(
    campaign: Dict[str, Any], settings: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "title": f"⚙️ Settings — {campaign['name']}",
        "color": COLOR_INFO,
        "fields": [
            _field("Announce channel", mention_channel(settings.get("announce_channel_id")), inline=True),
            _field("Recap channel", mention_channel(settings.get("recap_channel_id")), inline=True),
            _field("Reminder channel", mention_channel(settings.get("reminder_channel_id")), inline=True),
            _field("DM role", mention_role(settings.get("dm_role_id")), inline=True),
            _field("Player role", mention_role(settings.get("player_role_id")), inline=True),
            _field("Default day", weekday_name(settings.get("default_day_of_week")), inline=True),
            _field("Default time (local)", settings.get("default_time_local") or "—", inline=True),
            _field("Reminders", offsets_summary(settings.get("reminder_offsets_minutes") or []), inline=True),
            _field("RSVP required", boolean_label(settings.get("rsvp_required")), inline=True),
            _field("Maybe allowed", boolean_label(settings.get("maybe_allowed")), inline=True),
            _field("Alt times allowed", boolean_label(settings.get("alternate_times_allowed")), inline=True),
            _field("Recap draft-first", boolean_label(settings.get("recap_draft_first")), inline=True),
            _field("Quest log public", boolean_label(settings.get("quest_log_public")), inline=True),
            _field("Default NPC visibility", visibility_label(settings.get("npc_default_visibility") or "public"), inline=True),
            _field("Ping role on reminders", boolean_label(settings.get("ping_on_reminders")), inline=True),
        ],
        "footer": {"text": f"Campaign ID: {campaign['id']} — run /campaign settings to edit"},
    }


# ── Session embeds ────────────────────────────────────────────────────────


def session_announce_embed(
    *,
    campaign: Dict[str, Any],
    session: Dict[str, Any],
    rsvp_counts: Dict[str, int],
    attendee_user_ids: List[int],
    maybe_user_ids: List[int],
    unavailable_user_ids: List[int],
    rsvp_required: bool = False,
) -> Dict[str, Any]:
    starts_at = session.get("starts_at")
    title = session.get("title") or f"Session {session.get('session_number') or session['id']}"

    color = COLOR_PRIMARY
    if session.get("status") == "cancelled":
        color = COLOR_MUTED
    elif session.get("status") == "completed":
        color = COLOR_SUCCESS

    description_lines = []
    if session.get("status") == "cancelled":
        description_lines.append("**~~CANCELLED~~** — This session has been cancelled.")
    if rsvp_required and session.get("status") == "scheduled":
        description_lines.append("**📌 RSVP required** — please pick a response below.")
    if session.get("notes_for_players"):
        description_lines.append(truncate(session["notes_for_players"], 2000))

    fields = [
        _field("📅 Starts", f"{discord_timestamp(starts_at)} ({discord_timestamp_relative(starts_at)})", inline=False),
        _field("⏱ Duration", format_duration(int(session.get("duration_minutes") or 0)), inline=True),
        _field("🎲 Campaign", campaign.get("name") or "—", inline=True),
        _field("👑 DM", mention_user(campaign.get("owner_user_id")), inline=True),
        _field(
            f"✅ Attending ({rsvp_counts.get('attending', 0)})",
            join_user_mentions(attendee_user_ids),
            inline=False,
        ),
        _field(
            f"❔ Maybe ({rsvp_counts.get('maybe', 0)})",
            join_user_mentions(maybe_user_ids),
            inline=True,
        ),
        _field(
            f"❌ Unavailable ({rsvp_counts.get('unavailable', 0)})",
            join_user_mentions(unavailable_user_ids),
            inline=True,
        ),
    ]

    title_prefix = "🛑 " if session.get("status") == "cancelled" else "🎲 "
    return {
        "title": f"{title_prefix}{title}"[:256],
        "description": "\n\n".join(description_lines)[:4096] if description_lines else "",
        "color": color,
        "fields": fields,
        "footer": {"text": f"Session #{session.get('session_number') or session['id']} • Campaign ID {campaign['id']}"},
    }


def session_reminder_embed(
    *,
    campaign: Dict[str, Any],
    session: Dict[str, Any],
    offset_minutes: int,
    pending_rsvp_user_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    starts_at = session.get("starts_at")
    title = session.get("title") or f"Session {session.get('session_number') or session['id']}"
    label = format_offset_label(offset_minutes)
    embed: Dict[str, Any] = {
        "title": f"⏰ Reminder — {label} until {title}",
        "description": (
            f"**{campaign.get('name', 'Campaign')}** — "
            f"{discord_timestamp(starts_at)} ({discord_timestamp_relative(starts_at)})"
        ),
        "color": COLOR_WARNING,
    }
    if pending_rsvp_user_ids:
        embed["fields"] = [
            _field(
                f"⚠️ Still waiting on RSVPs ({len(pending_rsvp_user_ids)})",
                join_user_mentions(pending_rsvp_user_ids),
                inline=False,
            )
        ]
    return embed


def session_list_embed(
    campaign: Dict[str, Any], sessions: List[Dict[str, Any]], *, scope: str
) -> Dict[str, Any]:
    heading = {"upcoming": "Upcoming sessions", "past": "Past sessions", "all": "All sessions"}.get(
        scope, "Sessions"
    )
    if not sessions:
        return info_embed(f"{heading} — {campaign['name']}", "No sessions to show.")
    lines = []
    for s in sessions[:25]:
        num = s.get("session_number") or s["id"]
        title = s.get("title") or f"Session {num}"
        status_emoji = {
            "scheduled": "📅",
            "cancelled": "🛑",
            "completed": "✅",
        }.get(s.get("status"), "•")
        starts = s.get("starts_at")
        lines.append(
            f"{status_emoji} **#{num}** — {title} · "
            f"{discord_timestamp(starts)} ({discord_timestamp_relative(starts)}) · ID `{s['id']}`"
        )
    return {
        "title": f"📜 {heading} — {campaign['name']}",
        "description": "\n".join(lines)[:4096],
        "color": COLOR_INFO,
    }


def session_cancel_confirm_embed(session: Dict[str, Any]) -> Dict[str, Any]:
    starts = session.get("starts_at")
    title = session.get("title") or f"Session {session.get('session_number') or session['id']}"
    return {
        "title": f"🛑 Cancel '{title}'?",
        "description": (
            f"This will cancel the session scheduled for "
            f"{discord_timestamp(starts)} ({discord_timestamp_relative(starts)}). "
            "The announcement will be updated to show it as cancelled. "
            "This action can't be undone."
        ),
        "color": COLOR_WARNING,
    }


# ── Recap embeds ──────────────────────────────────────────────────────────


def recap_preview_embed(
    recap: Dict[str, Any], session: Dict[str, Any], campaign: Dict[str, Any]
) -> Dict[str, Any]:
    title = recap.get("title") or f"Session {session.get('session_number') or session['id']} recap"
    fields = []
    fields.append(_field("Summary", truncate(recap.get("summary") or "", 1024)))
    if recap.get("highlights"):
        fields.append(_field("Highlights", truncate(recap["highlights"], 1024)))
    if recap.get("loot"):
        fields.append(_field("Loot", truncate(recap["loot"], 1024)))
    if recap.get("cliffhanger"):
        fields.append(_field("Cliffhanger", truncate(recap["cliffhanger"], 1024)))
    return {
        "title": f"📜 [Draft preview] {title}",
        "description": f"**{campaign['name']}** · Session #{session.get('session_number') or session['id']}",
        "color": COLOR_MUTED,
        "fields": fields,
        "footer": {"text": "Use 'Post to Channel' to share, 'Keep as Draft' to save for later, or 'Add DM Notes' for private notes."},
    }


def recap_posted_embed(
    recap: Dict[str, Any], session: Dict[str, Any], campaign: Dict[str, Any]
) -> Dict[str, Any]:
    title = recap.get("title") or f"Session {session.get('session_number') or session['id']} recap"
    fields = [_field("Summary", truncate(recap.get("summary") or "", 1024))]
    if recap.get("highlights"):
        fields.append(_field("Highlights", truncate(recap["highlights"], 1024)))
    if recap.get("loot"):
        fields.append(_field("Loot", truncate(recap["loot"], 1024)))
    if recap.get("cliffhanger"):
        fields.append(_field("Cliffhanger", truncate(recap["cliffhanger"], 1024)))
    starts = session.get("starts_at")
    return {
        "title": f"📜 {title}",
        "description": f"**{campaign['name']}** · Session #{session.get('session_number') or session['id']} · "
                       f"played {discord_timestamp(starts, style='D') if starts else '—'}",
        "color": COLOR_PRIMARY,
        "fields": fields,
        "footer": {"text": f"By {campaign.get('name')} • Recap ID {recap['id']}"},
    }


def recap_list_embed(
    campaign: Dict[str, Any], recaps: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not recaps:
        return info_embed(f"📜 Past recaps — {campaign['name']}", "No posted recaps yet.")
    lines = []
    for r in recaps[:25]:
        title = r.get("title") or f"Session {r.get('session_number') or r['session_id']} recap"
        when = r.get("posted_at")
        when_str = discord_timestamp(when, style="d") if when else "—"
        link = ""
        if r.get("posted_channel_id") and r.get("posted_message_id"):
            link = f" — [jump](https://discord.com/channels/{0}/{r['posted_channel_id']}/{r['posted_message_id']})"
        lines.append(f"📜 **{title}** · {when_str}{link}")
    return {
        "title": f"📜 Past recaps — {campaign['name']}",
        "description": "\n".join(lines)[:4096],
        "color": COLOR_INFO,
    }


# ── Quest embeds ──────────────────────────────────────────────────────────


def quest_added_embed(quest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": f"📜 Quest added: {quest['title']}",
        "description": truncate(quest.get("description") or "", 4000),
        "color": COLOR_SUCCESS,
        "fields": [
            _field("Status", status_label(quest.get("status") or "active"), inline=True),
            _field("Visibility", visibility_label(quest.get("visibility") or "public"), inline=True),
        ],
        "footer": {"text": f"Quest ID {quest['id']}"},
    }


def quest_updated_embed(quest: Dict[str, Any], update_text: str) -> Dict[str, Any]:
    return {
        "title": f"📝 Quest update: {quest['title']}",
        "description": truncate(update_text, 4000),
        "color": COLOR_INFO,
        "fields": [
            _field("Status", status_label(quest.get("status") or "active"), inline=True),
        ],
        "footer": {"text": f"Quest ID {quest['id']}"},
    }


def quest_list_embed(
    campaign: Dict[str, Any], quests: List[Dict[str, Any]], *, viewer_is_dm: bool, status_filter: Optional[str] = None
) -> Dict[str, Any]:
    if not quests:
        return info_embed(
            f"📜 Quest log — {campaign['name']}",
            "No quests to show." + (" (DM-only entries are hidden.)" if not viewer_is_dm else ""),
        )
    by_status: Dict[str, List[str]] = {}
    for q in quests[:50]:
        bucket = by_status.setdefault(q.get("status") or "active", [])
        vis = " 🔒" if q.get("visibility") == "dm_only" else ""
        bucket.append(f"• **{q['title']}** — `ID {q['id']}`{vis}")
    fields = []
    for st in ("active", "completed", "failed", "abandoned"):
        if st in by_status and by_status[st]:
            fields.append(_field(
                f"{status_label(st)} ({len(by_status[st])})",
                truncate("\n".join(by_status[st]), 1024),
            ))
    suffix = f" • Filter: {status_label(status_filter)}" if status_filter else ""
    return {
        "title": f"📜 Quest log — {campaign['name']}{suffix}",
        "color": COLOR_PRIMARY,
        "fields": fields,
    }


# ── NPC embeds ────────────────────────────────────────────────────────────


def npc_added_embed(npc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": f"🧙 NPC added: {npc['name']}",
        "color": COLOR_SUCCESS,
        "fields": [
            _field("Role", npc.get("role") or "—", inline=True),
            _field("Location", npc.get("location") or "—", inline=True),
            _field("Visibility", visibility_label(npc.get("visibility") or "public"), inline=True),
        ],
        "footer": {"text": f"NPC ID {npc['id']}"},
    }


def npc_list_embed(
    campaign: Dict[str, Any], npcs: List[Dict[str, Any]], *, viewer_is_dm: bool
) -> Dict[str, Any]:
    if not npcs:
        return info_embed(
            f"🧙 NPCs — {campaign['name']}",
            "No NPCs to show." + (" (DM-only and partial-visibility entries are hidden where applicable.)" if not viewer_is_dm else ""),
        )
    lines = []
    for n in npcs[:25]:
        vis = n.get("visibility") or "public"
        bits = [f"**{n['name']}**"]
        if n.get("role"):
            bits.append(f"*{n['role']}*")
        if n.get("location") and (viewer_is_dm or vis == "public"):
            bits.append(f"@ {n['location']}")
        vis_tag = {"public": "", "partial": " 🌗", "dm_only": " 🔒"}.get(vis, "")
        line = " · ".join(bits) + vis_tag
        if viewer_is_dm and n.get("secret_notes"):
            line += "\n   📓 " + truncate(str(n["secret_notes"]), 200)
        elif n.get("public_notes"):
            line += "\n   " + truncate(str(n["public_notes"]), 200)
        lines.append(line)
    return {
        "title": f"🧙 NPCs — {campaign['name']}",
        "description": truncate("\n\n".join(lines), 4000),
        "color": COLOR_PRIMARY,
    }


# ── Party embeds ──────────────────────────────────────────────────────────


def party_roster_embed(
    campaign: Dict[str, Any], members: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not members:
        return info_embed(
            f"🛡 Party — {campaign['name']}",
            "Nobody in the party yet. Add players with `/party add`.",
        )
    lines = []
    for m in members[:25]:
        bits = [mention_user(m["user_id"])]
        if m.get("character_name"):
            bits.append(f"as **{m['character_name']}**")
        meta = []
        if m.get("character_class"):
            meta.append(str(m["character_class"]))
        if m.get("character_level"):
            meta.append(f"lvl {m['character_level']}")
        if meta:
            bits.append(f"({', '.join(meta)})")
        lines.append("• " + " ".join(bits))
    return {
        "title": f"🛡 Party — {campaign['name']}",
        "description": truncate("\n".join(lines), 4000),
        "color": COLOR_PRIMARY,
    }


# ── DM notes embeds (always ephemeral) ────────────────────────────────────


def dmnote_list_embed(
    campaign: Dict[str, Any], notes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not notes:
        return info_embed(
            f"📓 DM notes — {campaign['name']}",
            "No DM-only notes yet. Add one with `/dmnotes add`.",
        )
    lines = []
    for n in notes[:25]:
        body_preview = truncate(str(n.get("body") or ""), 150)
        lines.append(f"• **{n['title']}** — `ID {n['id']}`\n   {body_preview}")
    return {
        "title": f"📓 DM notes — {campaign['name']}",
        "description": truncate("\n\n".join(lines), 4000),
        "color": COLOR_MUTED,
        "footer": {"text": "These notes are visible only to you. Players cannot see this message."},
    }


def dmnote_added_embed(note: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": f"📓 DM note saved: {note['title']}",
        "description": truncate(str(note.get("body") or ""), 4000),
        "color": COLOR_MUTED,
        "footer": {"text": f"Note ID {note['id']} • DM-only — players cannot see this."},
    }


# ── Alternate time proposal embed ─────────────────────────────────────────


def alt_time_proposal_embed(
    *,
    session: Dict[str, Any],
    campaign: Dict[str, Any],
    proposer_user_id: str,
    proposed_at: datetime,
    reason: str = "",
) -> Dict[str, Any]:
    title = session.get("title") or f"Session {session.get('session_number') or session['id']}"
    fields = [
        _field("Original start", discord_timestamp(session.get("starts_at"))),
        _field("Proposed start", f"{discord_timestamp(proposed_at)} ({discord_timestamp_relative(proposed_at)})"),
        _field("Proposed by", mention_user(proposer_user_id), inline=True),
    ]
    if reason:
        fields.append(_field("Reason", truncate(reason, 1024)))
    dm_mention = mention_user(campaign.get("owner_user_id"))
    return {
        "title": f"🕓 Alternate time proposed for {title}",
        "description": (
            f"{dm_mention} — a player suggested a different start time for this session. "
            "If you want to accept, reschedule via `/session schedule` (or cancel the original)."
        ),
        "color": COLOR_INFO,
        "fields": fields,
        "footer": {"text": f"Session #{session.get('session_number') or session['id']} • Campaign ID {campaign['id']}"},
    }


# ── Attendance embed ──────────────────────────────────────────────────────


def attendance_prompt_embed(
    session: Dict[str, Any], campaign: Dict[str, Any], rsvp_user_ids: List[int]
) -> Dict[str, Any]:
    title = session.get("title") or f"Session {session.get('session_number') or session['id']}"
    if not rsvp_user_ids:
        desc = "Nobody RSVP'd. Use `/party list` to find players manually."
    else:
        desc = (
            "Select everyone who actually attended. Players you don't pick are marked absent. "
            "(Only RSVP'd players appear here.)"
        )
    return {
        "title": f"📋 Attendance — {title}",
        "description": desc,
        "color": COLOR_INFO,
        "footer": {"text": f"{campaign['name']} • Session ID {session['id']}"},
    }


def attendance_recorded_embed(
    session: Dict[str, Any], present_user_ids: List[int], absent_user_ids: List[int]
) -> Dict[str, Any]:
    return {
        "title": "📋 Attendance recorded",
        "color": COLOR_SUCCESS,
        "fields": [
            _field(f"Present ({len(present_user_ids)})", join_user_mentions(present_user_ids), inline=False),
            _field(f"Absent ({len(absent_user_ids)})", join_user_mentions(absent_user_ids), inline=False),
        ],
        "footer": {"text": f"Session ID {session['id']}"},
    }
