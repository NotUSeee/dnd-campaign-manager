"""Apply pending schema migrations on plugin boot.

The runner reads the persisted schema version from KV, applies every
migration with id > version, then writes the new max id back. All DDL uses
`IF NOT EXISTS` so re-running an already-applied migration is harmless.
"""
from plugin_module.constants import SCHEMA_VERSION_KEY
from plugin_module.storage.migrations import MIGRATIONS


def run_pending_migrations(ctx) -> int:
    """Apply migrations newer than the stored schema_version. Returns number applied."""
    current = ctx.kv.get(SCHEMA_VERSION_KEY)
    try:
        current_version = int(current) if current is not None else 0
    except (TypeError, ValueError):
        current_version = 0

    pending = [m for m in MIGRATIONS if int(m["id"]) > current_version]
    if not pending:
        return 0

    applied = 0
    new_max = current_version
    for m in sorted(pending, key=lambda x: int(x["id"])):
        sql = str(m["sql"]).strip()
        if not sql:
            continue
        # The platform's sql.execute runs a single SQL string. Postgres will
        # accept multi-statement strings via execute() because psycopg
        # supports it; the platform's sandbox runs each migration as one
        # call. If the platform splits internally, this still works because
        # every statement is idempotent.
        ctx.sql.execute(sql)
        new_max = max(new_max, int(m["id"]))
        applied += 1

    if applied > 0:
        ctx.kv.set(SCHEMA_VERSION_KEY, new_max)
        try:
            ctx.log(
                f"Applied {applied} migration(s); schema_version now {new_max}",
                level="info",
                tags=["bootstrap", "migrations"],
            )
        except Exception:
            pass
    return applied
