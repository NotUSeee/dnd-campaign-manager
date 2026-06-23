"""Web dashboard data — powers the custom iframe dashboard (dashboard/index.html).

Registered as ``dashboard.get_overview`` and called by YourBotSDK.rpc("get_overview").
Read-only. Each section is wrapped defensively so one failing query degrades that
panel instead of blanking the whole dashboard.

Visibility: this dashboard is web-facing (viewer role can open it), so it only
surfaces PUBLIC quests/NPCs and never DM secrets (secret_notes, dm_only entries).

Registration is guarded with ``hasattr`` so the plugin still imports on older
local SDKs that predate ``on_dashboard``; on the platform (current SDK) it
registers normally.
"""
from typing import Any, Dict, List, Optional

from plugin_module import plugin
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import party as st_party


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _resolve_campaign(ctx, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Selected campaign (?campaign_id=) or the most relevant active one."""
    cid = params.get("campaign_id")
    if cid:
        try:
            camp = st_campaigns.get_campaign(ctx, int(cid))
            if camp:
                return camp
        except Exception:
            pass
    try:
        rows = ctx.sql.query(
            """
            SELECT id, name, party_name, system, description, status, created_at
              FROM dnd_campaigns
             WHERE discord_srv_id = %s AND status <> 'archived'
             ORDER BY (status = 'active') DESC, updated_at DESC
             LIMIT 1
            """,
            [int(ctx.server_id)],
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def get_overview(ctx, params: Dict[str, Any]) -> Dict[str, Any]:
    srv = int(ctx.server_id)

    campaigns = _safe(lambda: ctx.sql.query(
        """
        SELECT id, name, system, status
          FROM dnd_campaigns
         WHERE discord_srv_id = %s AND status <> 'archived'
         ORDER BY (status = 'active') DESC, name
        """, [srv]), [])
    campaigns = [
        {"id": int(c["id"]), "name": c["name"], "system": c.get("system"), "status": c.get("status")}
        for c in (campaigns or [])
    ]

    campaign = _resolve_campaign(ctx, params)
    if not campaign:
        return {"campaigns": campaigns, "campaign": None}
    cid = int(campaign["id"])

    # ── Party roster ──
    members = _safe(lambda: st_party.list_active_party(ctx, cid), [])
    party = [{
        "name": (m.get("character_name") or "Unnamed adventurer"),
        "cls": (m.get("character_class") or ""),
        "level": m.get("character_level"),
    } for m in (members or [])]
    levels = [int(m["character_level"]) for m in (members or []) if m.get("character_level")]
    avg_level = round(sum(levels) / len(levels), 1) if levels else None
    class_counts: Dict[str, int] = {}
    for m in (members or []):
        c = (m.get("character_class") or "Unknown").strip() or "Unknown"
        class_counts[c] = class_counts.get(c, 0) + 1
    class_breakdown = [{"name": k, "value": v}
                       for k, v in sorted(class_counts.items(), key=lambda kv: -kv[1])]

    # ── Session counts ──
    sc = _safe(lambda: ctx.sql.query_one(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'completed') AS played,
               COUNT(*) FILTER (WHERE status = 'scheduled') AS scheduled
          FROM dnd_sessions WHERE campaign_id = %s
        """, [cid]), {}) or {}

    # ── Next scheduled session + RSVP tally ──
    nxt = _safe(lambda: ctx.sql.query_one(
        """
        SELECT id, session_number, title, starts_at
          FROM dnd_sessions
         WHERE campaign_id = %s AND status = 'scheduled' AND starts_at >= NOW()
         ORDER BY starts_at LIMIT 1
        """, [cid]), None)
    next_session = None
    if nxt:
        rsvp = {"attending": 0, "maybe": 0, "unavailable": 0}
        for r in _safe(lambda: ctx.sql.query(
            "SELECT status, COUNT(*) AS n FROM dnd_session_rsvps WHERE session_id = %s GROUP BY status",
            [int(nxt["id"])]), []) or []:
            if r.get("status") in rsvp:
                rsvp[r["status"]] = int(r["n"])
        next_session = {
            "title": nxt.get("title") or ("Session #%s" % (nxt.get("session_number") or "?")),
            "session_number": nxt.get("session_number"),
            "starts_at": _iso(nxt.get("starts_at")),
            "rsvp": rsvp,
        }

    # ── Quests (PUBLIC only) ──
    quests = {"active": 0, "completed": 0, "failed": 0, "abandoned": 0}
    for r in _safe(lambda: ctx.sql.query(
        """
        SELECT status, COUNT(*) AS n FROM dnd_quests
         WHERE campaign_id = %s AND visibility = 'public' GROUP BY status
        """, [cid]), []) or []:
        if r.get("status") in quests:
            quests[r["status"]] = int(r["n"])
    recent_quests = _safe(lambda: ctx.sql.query(
        """
        SELECT title, status FROM dnd_quests
         WHERE campaign_id = %s AND visibility = 'public' AND status = 'active'
         ORDER BY updated_at DESC LIMIT 6
        """, [cid]), []) or []

    # ── NPCs (PUBLIC only; never secret_notes) ──
    npc_count = (_safe(lambda: ctx.sql.query_one(
        "SELECT COUNT(*) AS n FROM dnd_npcs WHERE campaign_id = %s AND visibility = 'public'",
        [cid]), {}) or {}).get("n", 0)
    npcs = _safe(lambda: ctx.sql.query(
        """
        SELECT name, role, location FROM dnd_npcs
         WHERE campaign_id = %s AND visibility = 'public'
         ORDER BY updated_at DESC LIMIT 6
        """, [cid]), []) or []

    # ── Posted recaps ──
    recaps = _safe(lambda: ctx.sql.query(
        """
        SELECT r.title, r.posted_at, s.session_number
          FROM dnd_recaps r
          LEFT JOIN dnd_sessions s ON s.id = r.session_id
         WHERE r.campaign_id = %s AND r.status = 'posted'
         ORDER BY r.posted_at DESC LIMIT 5
        """, [cid]), []) or []

    # ── Sessions-played timeline (last ~6 months) ──
    tl = _safe(lambda: ctx.sql.query(
        """
        SELECT to_char(date_trunc('month', starts_at), 'Mon') AS label,
               date_trunc('month', starts_at) AS bucket, COUNT(*) AS n
          FROM dnd_sessions
         WHERE campaign_id = %s AND status = 'completed'
               AND starts_at > NOW() - INTERVAL '6 months'
         GROUP BY 1, 2 ORDER BY 2
        """, [cid]), []) or []

    # ── Attendance rate over logged sessions ──
    att = _safe(lambda: ctx.sql.query_one(
        """
        SELECT COUNT(*) FILTER (WHERE a.attended) AS yes, COUNT(*) AS total
          FROM dnd_session_attendance a
          JOIN dnd_sessions s ON s.id = a.session_id
         WHERE s.campaign_id = %s
        """, [cid]), {}) or {}
    attendance_rate = (
        round(int(att.get("yes") or 0) / int(att["total"]), 2)
        if att.get("total") else None
    )

    return {
        "campaigns": campaigns,
        "campaign": {
            "id": cid,
            "name": campaign.get("name"),
            "party_name": campaign.get("party_name"),
            "system": campaign.get("system") or "D&D 5e",
            "status": campaign.get("status") or "active",
            "description": campaign.get("description"),
        },
        "stats": {
            "party_size": len(party),
            "sessions_played": int(sc.get("played") or 0),
            "sessions_scheduled": int(sc.get("scheduled") or 0),
            "active_quests": quests["active"],
            "npc_count": int(npc_count or 0),
            "avg_level": avg_level,
            "attendance_rate": attendance_rate,
        },
        "next_session": next_session,
        "party": party,
        "class_breakdown": class_breakdown,
        "quests": {**quests, "recent": [
            {"title": q.get("title"), "status": q.get("status")} for q in recent_quests
        ]},
        "timeline": {"labels": [t.get("label") for t in tl],
                     "values": [int(t.get("n") or 0) for t in tl]},
        "recaps": [{
            "title": (r.get("title") or ("Session #%s" % (r.get("session_number") or "?"))),
            "posted_at": _iso(r.get("posted_at")),
        } for r in recaps],
        "npcs": [{"name": n.get("name"), "role": n.get("role"), "location": n.get("location")}
                 for n in npcs],
    }


# Guarded registration — older local SDKs (pre-on_dashboard) still import cleanly.
if hasattr(plugin, "on_dashboard"):
    plugin.on_dashboard("get_overview")(get_overview)
