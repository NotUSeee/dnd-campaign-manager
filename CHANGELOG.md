# Changelog

## 1.1.0 — Web dashboard

A custom web dashboard for the plugin's marketplace page (Dashboard tab).

- New iframe dashboard (`dashboard/index.html`) — a themed campaign overview:
  next session + RSVP breakdown, quest log, party roster, party composition,
  a sessions-played chronicle, latest recaps, and notable NPCs. Hand-rolled
  SVG charts (no external dependencies).
- New `dashboard.get_overview` handler (`handlers/dashboard.py`) — one read-only
  RPC that powers the whole page. Surfaces PUBLIC quests/NPCs only; never sends
  DM secrets. Per-section error isolation so one bad query degrades a single
  panel, not the page.
- Campaign picker for servers running more than one campaign.
- `dashboard_manifest.json` (iframe mode) + packaging updated to bundle the
  dashboard. Handler registration is guarded so the plugin still imports on
  older local SDKs that predate `on_dashboard`.

## 1.0.6 — Tolerate ISO date strings from platform SQL results

The platform's SQL surface returns ``TIMESTAMPTZ`` columns as ISO 8601
strings over JSON-RPC (raw Python ``datetime`` objects aren't JSON-
serializable). Any code path that received a row directly and did
arithmetic on a timestamp column was breaking after the previous fix
landed end-to-end.

- ``core/time_util.parse_iso_dt(v)`` — idempotent coercer: passes
  ``datetime`` through, parses ISO strings to UTC-aware ``datetime``,
  returns ``None`` on empty / unparseable input.
- ``core/time_util.to_unix`` + ``discord_timestamp`` now accept either
  form, so embed builders don't have to coerce ahead of every call.
- ``storage/sessions._coerce_session`` now parses ``starts_at``,
  ``next_reminder_due_at``, ``created_at``, ``updated_at`` back to
  ``datetime`` so the reminder dispatcher's arithmetic works correctly.
- ``ui/format.render_dt`` / ``render_dt_relative`` accept strings too.

Pairs with a platform patch converting ``datetime`` / ``date`` / ``time``
/ ``Decimal`` columns to JSON-safe strings inside
``plugin_sql_query_with_meta`` so the result-size check + downstream
JSON-RPC framing don't trip on unserializable values.

## 1.0.5 — Replace INSERT…RETURNING with INSERT-then-SELECT

The MMO Maid sandbox SQL surface splits writes (``plugin_sql_execute`` —
returns rowcount only) from reads (``plugin_sql_query`` — SELECT only).
``INSERT … RETURNING`` is not supported through either path, so every
storage layer ``create_X`` function that relied on it raised
``RuntimeError: plugin_sql_query only accepts SELECT statements`` when
called.

Refactored all 7 INSERT…RETURNING sites to the two-step pattern: INSERT
via ``ctx.sql.execute``, then SELECT-back via ``ctx.sql.query_one`` using
the table's natural unique key (campaign name, recap session_id,
attendance pk, etc.) or ``(campaign_id, user_id) ORDER BY id DESC LIMIT 1``
for tables without a natural unique key.

Race window between INSERT and SELECT is theoretical for single-DM
workflows (campaigns/sessions/quests/etc. are slow human-driven actions)
but worth knowing about for future high-concurrency features.

Files touched: storage/campaigns.py, storage/sessions.py, storage/recaps.py,
storage/quests.py, storage/npcs.py, storage/notes.py.

## 1.0.4 — Fall back to legacy `command_options` key

The MMO Maid platform's `meta_only` privacy filter (the default for
installs that don't request `events:message_content`) strips fields not
in an explicit whitelist. Older platform versions whitelisted the legacy
`command_options` alias but NOT the canonical `options` key — even though
the bot writes both with identical values. That made `event.get("options")`
return `None` on every slash-command invocation, breaking every subcommand
dispatcher with "Unknown subcommand".

`core/option_reader._opts(event)` now reads `options` first and falls back
to `command_options`. Two new tests cover the missing-canonical-key case.

Pairs with a platform patch adding both `options` and `member` to the
meta-only whitelist, but the plugin-side fallback means the fix works
even before that platform patch ships.

## 1.0.3 — Opt out of auto-defer for modal-sending commands

Discord forbids `send_modal` after an interaction has been deferred —
modals can only be the initial response. The MMO Maid bot auto-defers
every marketplace slash command on dispatch, which made `/campaign create`,
`/session schedule`, `/session recap`, `/quest update`, and `/dmnotes add`
hang forever on "thinking…" because their `send_modal` calls got rejected
by Discord (HTTP 400, silent).

This release opts the four affected top-level commands out of the auto-
defer via the new `defer_on_dispatch: false` manifest flag (added to the
MMO Maid platform alongside this release). Subcommands that don't send
modals still work — they're now expected to be fast (< 3 s) or call
`ctx.interaction.defer(ephemeral=True)` themselves if they're slow.

- `manifest.json`: add `defer_on_dispatch: false` to `campaign`, `session`,
  `quest`, `dmnotes`. `npc` and `party` keep the default (true) — none of
  their subcommands send modals directly.

## 1.0.2 — Subcommand dispatch fix

- `core/option_reader.get_subcommand` no longer requires Discord's
  `type: 1` field on the subcommand option. Some delivery paths from
  discord.py were omitting that field, causing every `/campaign create`,
  `/session schedule`, etc. invocation to fall through to "Unknown
  subcommand." The function now identifies subcommands by the absence
  of a `value` field, which is the actual invariant.
- Added defensive tests covering the type-missing case.
- Added a one-line warning log in the campaign dispatcher to surface
  the raw options shape if anything still slips through.

## 1.0.1 — Manifest fix

- Reorder `/party add` and `/party remove` options so the required `user`
  parameter comes before the optional ones. Discord rejects any slash
  command where required options are listed after non-required ones, and
  the rejection failed the bulk command sync for the whole guild — so
  none of the plugin's commands were appearing.

## 1.0.0 — Initial release

First public release of D&D Campaign Manager.

- Multi-campaign per server: create, configure, archive campaigns
- Session scheduling with structured form (date, time, duration, notes)
- RSVP buttons: Attending / Maybe / Unavailable, with live count updates on the announcement embed
- Configurable session reminders (default 24h, 2h, 15m before) — atomic at-most-once dispatch
- Optional recurring sessions (weekly / biweekly / monthly), materialized 4 ahead with auto top-up
- Structured session recaps (DM-drafted then posted, or posted immediately)
- Quest log with status (active / completed / failed / abandoned) and visibility (public / DM-only)
- NPC log with three visibility tiers (public / partial / DM-only)
- Party roster with character info, soft-deleted to preserve attendance history
- Post-session attendance tracking, distinct from pre-session RSVPs
- DM-only notes: never posted publicly, ephemeral replies only
- Role-based permissions: campaign owner, DM role, server admin
- Two-step confirmation for destructive actions (session cancel)
- Mass-ping guardrail: reminders ping the player role only when the DM explicitly opts in
