"""D&D Campaign Manager plugin module.

Constructs the shared Plugin instance and imports each handler submodule so
its decorators register against the instance.
"""
from mmo_maid_sdk import Plugin

plugin = Plugin()

from plugin_module.handlers import (  # noqa: E402,F401  (imported for side-effects)
    lifecycle,
    scheduled,
    campaign,
    session,
    rsvp,
    recap,
    quest,
    npc,
    party,
    notes,
)
