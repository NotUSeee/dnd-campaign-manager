# D&D Campaign Manager

Schedule sessions, track RSVPs, post recaps, and organize campaign notes — for D&D, Pathfinder, and any tabletop campaign you run on Discord.

A marketplace plugin for the [MMO Maid](https://mmomaid.com) platform.

## What it does

One structured place inside your Discord server to handle the recurring logistics of a campaign:

- **Sessions:** schedule one-off or recurring sessions; players RSVP with buttons; the plugin sends reminders before kickoff
- **Recaps:** post structured recaps after each session (summary, highlights, loot, cliffhanger) — draft first or post immediately, your choice
- **Quests:** lightweight quest log with public and DM-only entries
- **NPCs:** three visibility tiers so you can drop hooks without spoilers
- **Party:** roster with character info; attendance history preserved when players leave
- **DM notes:** ephemeral-only knowledge base that never accidentally leaks to players

Supports multiple concurrent campaigns in the same server.

## Quickstart for DMs

1. Install the plugin from the marketplace
2. Run `/campaign create` and fill out the modal
3. Run `/campaign settings` to set your announcement channel, recap channel, reminder channel, and (optionally) the DM and player roles
4. Run `/session schedule` to post your first session announcement
5. Players click `Attending` / `Maybe` / `Unavailable` directly on the embed
6. After the session, run `/session recap` (or click the `Create Recap` button on the announcement) to record what happened

All slash commands support multiple campaigns via an inline picker when you omit the campaign ID.

## Commands

```
/campaign create | settings | info
/session  schedule | list | cancel | recap | attendance
/quest    add | update | list
/npc      add | list
/party    add | remove | list
/dmnotes  add | list      (DM-only, always ephemeral)
```

## Permissions model

| Action | Who can do it |
|---|---|
| Create a campaign | DM role OR server admin |
| Modify campaign settings, schedule/cancel sessions, post recaps, manage quests/NPCs/party | Campaign owner OR assigned DM role OR server admin |
| View campaign info, lists, recaps | Anyone (DM-only entries filtered server-side) |
| Add or view DM notes | DM role OR server admin only — replies are always ephemeral |

## Requested capabilities

| Capability | Why |
|---|---|
| `storage:sql` | Relational data for campaigns, sessions, RSVPs, quests, NPCs |
| `storage:kv` | One key: schema version pointer |
| `discord:send_message` | Posting announcements, recaps, reminders |
| `discord:edit_message` | Updating RSVP counts on the announcement embed |
| `discord:delete_message` | Optional cleanup on session cancel |
| `discord:read` | Resolving role/channel names for settings validation |
| `interaction:respond` | All slash commands, buttons, and modals |

The plugin does **not** request `manage_channels`, `manage_roles`, `add_reaction`, or any moderation capability. No outbound HTTP.

## Guardrails

- Session cancellation requires a two-step confirm
- Reminders never ping a role unless the DM explicitly enables `ping_on_reminders`
- DM-only notes route through `ctx.interaction.respond(..., ephemeral=True)` exclusively — never `send_message` — so they cannot leak to players
- Campaign settings modifications gated to DM role or server admin

## Out of scope (v1.0)

Character sheets, dice rolling, calendar export, native Discord scheduled events integration, voice channel provisioning, dashboard UI.

## Packaging for the marketplace

The dev portal accepts a single ZIP. Use the included build script:

```bash
python scripts/package.py
```

It produces `dnd_campaign_manager.zip` at the repo root, excluding
`tests/`, `scripts/`, `.venv/`, `__pycache__/`, and other dev-only files.
Final size is well under the 25 MB marketplace cap.

Upload the ZIP via the dev portal at `https://mmomaid.com/dev/plugins`.

## License

MIT — see `LICENSE`.
