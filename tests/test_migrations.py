"""Schema migration smoke tests: idempotency, unique ids, DDL safety."""
import re

from plugin_module.storage.migrations import MIGRATIONS


def test_migrations_have_required_fields():
    assert MIGRATIONS, "MIGRATIONS list is empty"
    for m in MIGRATIONS:
        assert "id" in m and isinstance(m["id"], int)
        assert "name" in m and m["name"]
        assert "sql" in m and m["sql"].strip()


def test_migration_ids_are_unique_and_monotonic():
    ids = [int(m["id"]) for m in MIGRATIONS]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_every_create_table_is_idempotent():
    for m in MIGRATIONS:
        sql = m["sql"]
        # Find every CREATE TABLE and verify it includes IF NOT EXISTS before the table name.
        for create_match in re.finditer(r"CREATE\s+TABLE\b([^(]+)", sql, re.IGNORECASE):
            preamble = create_match.group(1).upper()
            assert "IF NOT EXISTS" in preamble, (
                f"Migration {m['name']!r} has non-idempotent CREATE TABLE: "
                f"CREATE TABLE{preamble.rstrip()}"
            )
        creates = re.findall(r"CREATE\s+TABLE\s+IF NOT EXISTS\s+(\w+)", sql, re.IGNORECASE)
        assert creates, f"Migration {m['name']!r} contains no CREATE TABLE"


def test_every_create_index_is_idempotent():
    for m in MIGRATIONS:
        sql = m["sql"]
        for idx_match in re.finditer(r"CREATE\s+(?:UNIQUE\s+)?INDEX\b([^(]+)", sql, re.IGNORECASE):
            preamble = idx_match.group(1).upper()
            assert "IF NOT EXISTS" in preamble, (
                f"Migration {m['name']!r} has non-idempotent CREATE INDEX: "
                f"CREATE INDEX{preamble.rstrip()}"
            )


def test_all_tables_have_dnd_prefix():
    """Sanity check: don't accidentally clobber unrelated platform tables."""
    for m in MIGRATIONS:
        creates = re.findall(r"CREATE TABLE\s+IF NOT EXISTS\s+(\w+)", m["sql"], re.IGNORECASE)
        for table in creates:
            assert table.startswith("dnd_"), f"Table {table!r} missing dnd_ prefix"


def test_bootstrap_runs_pending_migrations_once(ctx):
    """Run twice — second pass should be a no-op (no execute() calls)."""
    from plugin_module.storage.bootstrap import run_pending_migrations
    applied = run_pending_migrations(ctx)
    assert applied >= 1
    # Snapshot the SQL log count
    before = len(ctx.sql.executed)
    applied2 = run_pending_migrations(ctx)
    assert applied2 == 0
    # Second pass should NOT log new sql.execute calls
    assert len(ctx.sql.executed) == before
