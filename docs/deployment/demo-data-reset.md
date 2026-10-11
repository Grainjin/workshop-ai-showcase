# Scheduled demo data reset

Run from the repository root after applying migrations, with the deployment's
virtual environment and environment file loaded:

```sh
python -m backend.reset_demo_data --confirm reset-workshop-demo
```

Required environment:

```sh
DEMO_MODE=true
WORKSHOP_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/workshop_demo
DEMO_DATABASE_MARKER=workshop_demo
WORKSHOP_DEMO_SEED=42
```

Use a dedicated disposable demo database. The marker defaults to `workshop_demo`
and must be nonempty and occur in the parsed database name; occurrences in the
username, hostname or query do not count. The connected database name must also
match the URL. Confirmation is case-sensitive and accepts no extra whitespace.
SQLite, autocommit connections and sessions with existing transactions are refused.
The internal API is `reset_demo_database(db: Session, confirmation: str)` and
requires a fresh engine-bound session. There is no HTTP reset endpoint.

The canonical cloud schedule is the dedicated private-network Railway reset job
in `railway-reset.toml`: `0 17 * * *` UTC, which is 04:00 Sydney during daylight
saving and 03:00 during standard time. Follow the
[release and maintenance runbook](public-demo.md) to apply and verify native
settings, protect access, and provision only reset-specific environment values.
GitHub's manual `demo-reset.yml` workflow is an isolated PostgreSQL dry run, not a
second scheduler or a remote reset. Disable old server cron entries before native
schedule activation; never use a public DB proxy to run a private reset from CI.
This document and configuration do not install or activate a scheduled job.
Pause demo traffic and workers during the maintenance window. The transaction
takes PostgreSQL table locks; a transaction-scoped advisory lock refuses a second
reset while one is running. It does not stop visitors from writing after commit.

## Scope, output and recovery

Only the application's 46 metadata tables in the active migration schema are
truncated with `RESTART IDENTITY`. This includes users, bookings, chats,
favourites, payments, refunds, settlements, authentication tokens and
`demo_ai_usage`. `alembic_version` and unrelated tables are preserved. Missing
application tables cause refusal; run migrations first. No `CASCADE` is used:
an unexpected foreign-key dependency fails safely instead of widening deletion.
Every lock and truncate target uses `ONLY`. After locking the explicit tables,
catalog preflight rejects any inheritance or partition relationship involving an
application table, including an application table that is itself a child or an
empty partitioned parent. Current migrations have none; adding modeled partitions
also requires updating reset support. This refusal occurs before any truncate,
and protects unregistered descendants even when they live in another schema.

Location and demo seeds run in the same transaction, with a local random generator
using `WORKSHOP_DEMO_SEED`. Successful output is one JSON object with `database`,
`seed` and `table_counts`, printed only after commit. Expect 36 users (1 admin,
5 customers, 30 providers), 30 provider profiles, 210 availability records, 300
completed bookings, 300 reviews and 300 quote revisions. Each service category
has 30 quote samples (29 when querying a seeded booking in that category).
Visitor chats, favourites, payments, refunds, settlements and quota counters are
empty after reset. Existing demo account emails/passwords remain those documented
for the normal demo seed. Logs do not print passwords or connection URLs.

Repeated resets produce the same IDs, counts, sampled prices and booking states
for a given seed. Dates remain relative to the reset time, and password hashes
use fresh salts; this is not a byte-identical database dump. Ordinary demo seeding
still preserves existing users/providers and does not clear data.

Any truncate or seed failure rolls back the entire reset, including identity
sequence restarts. Previous data is retained and the CLI exits nonzero without
a success summary. There is no intermediate empty committed database. A completed
reset intentionally replaces visitor data; recovering a previous completed state
requires a backup. External uploaded files, Redis and vector data are outside this
database-only command's scope.

## Verification

Set `WORKSHOP_RESET_TEST_ADMIN_URL` to a PostgreSQL maintenance database accessible
to a role with `CREATEDB`, then run `pytest tests/test_demo_reset.py tests/test_seed.py`.
Tests create, migrate and remove their own `workshop_demo_task7_<random>` database.
They never reset the URL supplied as the maintenance/suite database. Tests without
PostgreSQL still run the refusal cases and skip integration cases.
