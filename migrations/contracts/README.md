# Migration-owned schema contracts

`booking_columns.json` is a literal, reviewed Booking column contract at the
recorded migration head. It must not be generated at test time from ORM metadata.
Add or remove a column here explicitly alongside its migration and corresponding
existing-schema regression test. The recorded revision must match the current
single migration head. For a migration that leaves Booking unchanged, advance
the recorded revision after reviewing that the literal column list is unchanged.

The inherited initial migration still creates tables from current model metadata.
Consequently, comparing only a fresh database with that model cannot detect a
missing future migration. The independent manifest makes an unlisted model column
fail even when the initial migration silently creates it. Existing-database
migration tests remain necessary; this contract does not prove types, data
backfills, constraints, or every historical upgrade path.

`tests/test_model_migration_contract.py` compares model, manifest, and real
PostgreSQL schema, checks a downgrade/upgrade round trip, and requests the
customer, provider, and admin booking-list APIs against Alembic-created tables.
Those API fixtures override only the database dependency, use real signed tokens
and role checks, and prohibit model-driven table recreation after migration.
