"""Plugin lifecycle hooks: ready, install, enable, disable, uninstall.

`on_ready` runs the schema migration bootstrap. `on_install` also runs it
(belt-and-suspenders) so a fresh install gets the schema even before the
first reminder tick.
"""
from plugin_module import plugin
from plugin_module.storage.bootstrap import run_pending_migrations


@plugin.on_ready
def on_ready(ctx):
    try:
        applied = run_pending_migrations(ctx)
        ctx.log(
            f"D&D Campaign Manager ready (server {ctx.server_id}); "
            f"{applied} migration(s) applied this boot",
            level="info",
            tags=["lifecycle", "ready"],
        )
    except Exception as exc:  # noqa: BLE001 — log everything, never crash boot
        ctx.log(f"on_ready bootstrap failed: {exc}", level="error", tags=["lifecycle"])


@plugin.on_install
def on_install(ctx):
    try:
        run_pending_migrations(ctx)
    except Exception as exc:  # noqa: BLE001
        ctx.log(f"on_install bootstrap failed: {exc}", level="error", tags=["lifecycle"])
    ctx.log(
        "D&D Campaign Manager installed. Run `/campaign create` to get started.",
        level="info",
        tags=["lifecycle", "install"],
    )


@plugin.on_enable
def on_enable(ctx):
    try:
        run_pending_migrations(ctx)
    except Exception as exc:  # noqa: BLE001
        ctx.log(f"on_enable bootstrap failed: {exc}", level="error", tags=["lifecycle"])
    ctx.log("D&D Campaign Manager enabled", level="info", tags=["lifecycle", "enable"])


@plugin.on_disable
def on_disable(ctx):
    ctx.log("D&D Campaign Manager disabled", level="info", tags=["lifecycle", "disable"])


@plugin.on_uninstall
def on_uninstall(ctx):
    ctx.log(
        "D&D Campaign Manager uninstalled (campaign data is retained until the plugin schema is dropped).",
        level="info",
        tags=["lifecycle", "uninstall"],
    )
