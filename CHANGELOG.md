# Changelog

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
