"""Guarded, atomic PostgreSQL demo reset. CLI/internal use only."""

import argparse
from dataclasses import asdict, dataclass
import json

from sqlalchemy import bindparam, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend import config, models  # noqa: F401 -- registers application metadata
from backend.database import Base, SessionLocal
from backend.seed_demo_data import seed_demo_data


@dataclass(frozen=True)
class DemoResetResult:
    database: str
    seed: int
    table_counts: dict[str, int]


def reset_demo_database(db: Session, confirmation: str) -> DemoResetResult:
    """Own one complete transaction; require an idle, engine-bound session."""
    if not config.DEMO_MODE:
        raise ValueError("Demo reset requires DEMO_MODE=true")
    if confirmation != "reset-workshop-demo":
        raise ValueError("Demo reset requires exact confirmation reset-workshop-demo")
    bind = db.get_bind()
    if not isinstance(bind, Engine):
        raise ValueError("Demo reset requires an engine-bound session")
    if bind.dialect.name != "postgresql":
        raise ValueError("Demo reset requires PostgreSQL")
    marker = config.DEMO_DATABASE_MARKER
    database = bind.url.database or ""
    if not marker or marker not in database:
        raise ValueError("Demo database name must contain DEMO_DATABASE_MARKER")
    if db.in_transaction():
        raise ValueError("Demo reset requires a session without an active transaction")

    with db.begin():
        connection = db.connection()
        if getattr(connection.connection.dbapi_connection, "autocommit", False):
            raise ValueError("Demo reset requires transactional PostgreSQL, not autocommit")
        actual_database, schema = connection.execute(
            text("SELECT current_database(), current_schema()")
        ).one()
        if actual_database != database or marker not in actual_database:
            raise ValueError("Connected database does not match the guarded database name")
        if not connection.scalar(text(
            "SELECT pg_try_advisory_xact_lock(hashtext('workshop-demo-reset'))"
        )):
            raise ValueError("A demo reset is already running")

        tables = sorted(
            (table for table in Base.metadata.tables.values() if table.name != "alembic_version"),
            key=lambda table: table.name,
        )
        present = set(inspect(connection).get_table_names(schema=schema))
        if not schema or any(table.schema not in (None, schema) or table.name not in present
                             for table in tables):
            raise ValueError("Application schema is incomplete; run migrations before resetting")
        quote = connection.dialect.identifier_preparer.quote_identifier
        targets = ", ".join(f"ONLY {quote(schema)}.{quote(table.name)}" for table in tables)
        # Freeze the target definitions before inspecting inheritance. ONLY also keeps
        # this non-destructive lock from recursively reaching unregistered tables.
        connection.execute(text(f"LOCK TABLE {targets} IN ACCESS EXCLUSIVE MODE"))
        has_inheritance = connection.scalar(text("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_class AS target
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = target.relnamespace
                WHERE namespace.nspname = :schema AND target.relname IN :table_names
                  AND (target.relkind = 'p' OR target.relispartition OR EXISTS (
                      SELECT 1 FROM pg_catalog.pg_inherits AS inheritance
                      WHERE inheritance.inhparent = target.oid
                         OR inheritance.inhrelid = target.oid
                  ))
            )
        """).bindparams(bindparam("table_names", expanding=True)),
            {"schema": schema, "table_names": [table.name for table in tables]})
        if has_inheritance:
            # Current application migrations contain no inheritance/partitions.
            # Refuse even modeled relationships until explicit support is designed.
            raise ValueError("Demo reset refuses application inheritance or partition relationships")
        # No CASCADE: an unknown dependent table must cause rollback, never expand scope.
        connection.execute(text(f"TRUNCATE TABLE {targets} RESTART IDENTITY"))
        db.expunge_all()
        seed_demo_data(db)
        db.flush()
        counts = {table.name: db.scalar(select(func.count()).select_from(table))
                  for table in tables}
        result = DemoResetResult(database=database, seed=config.WORKSHOP_DEMO_SEED,
                                 table_counts=counts)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            result = reset_demo_database(db, args.confirm)
    except Exception:
        # Do not expose credentials, SQL parameters, or seeded account data in cron logs.
        parser.exit(1, "Demo reset refused or failed; no reset was committed. Check guards, "
                    "database availability and migrations.\n")
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
