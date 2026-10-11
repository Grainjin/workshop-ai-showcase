# Demo rollback runbook

Use authorized native Railway/Vercel operations against explicitly selected
personal project, service and environment IDs. Record incident time, current and
previous commit/deployment IDs, schema revision and sanitized outcome. Never copy
tokens, connection URLs, request bodies or raw credential-bearing logs into CI or
incident notes. Use the [release runbook](public-demo.md) for approval capability,
exact settings, completion checks and the TOML deprecation maintenance deadline.

## API image or deployment rollback

Pause promotions and reset scheduling, remove Demo access while assessing impact,
and stop workers if they can write affected data. Choose the last verified API
deployment/image for the same environment. Check it is compatible with the current
schema; an API image rollback does not revert database migrations. Restore it
through Railway's native previous-deployment operation, retaining stable JWT
keys and public Demo/payment/HTTPS settings. Wait for terminal success, verify
`/health`, `/ready`, login, booking and simulated payments, then restore traffic.
If the native action is unavailable, redeploy the known-good commit using the
release path. Never claim success on an upload or queued receipt alone.

## Frontend rollback

Select the previous verified Vercel deployment independently for Demo and Case
Study, then use the native rollback/promotion operation for each affected project.
Check API/WS origins, Demo flags and source/Demo links match the retained API.
Frontend variables are build-time values; changing a platform variable does not
repair an existing bundle. Wait for deployment completion, verify direct SPA
navigation and readiness notices, and record the restored IDs before reopening
access. If no compatible previous build exists, rebuild the known-good commit
with approved HTTPS/WSS variables through the full CI release path.

## Database migration policy

Never automatically run `alembic downgrade -1` on a cloud database during rollback.
The CI migration round trip proves only its disposable test case, not preservation
of cloud data. Stop traffic and workers; capture and verify a private backup;
inspect the exact downgrade for dropped columns/tables and old-image compatibility.
Prefer an additive forward fix when safe. A destructive downgrade or restore
needs an explicit recovery decision for the identified database and potential
data loss, tested on a disposable restored copy first. Do not reset data as a
substitute for schema rollback. A failed pre-deploy migration must prevent the
new API from receiving traffic; inspect the actual schema revision before retry.

## Reset failure or incorrect reset

A refused/failed CLI exits nonzero, prints a fixed safe diagnostic and no success
summary, and rolls back truncation/seeding/identity restarts. Keep the failure
visible; stop the cron while investigating, confirm the guarded database name,
Demo flag, exact confirmation, migration completeness, available DB connection,
permissions and absence of a concurrent reset. Unknown foreign-key dependencies
or inheritance/partition relationships are safety refusals; do not add `CASCADE`
or weaken the marker. Preserve existing state and investigate privately.

Before a retry, verify no previous job is still active and pause traffic/workers.
Use native Run Now only after the service/DB guards are checked. Wait for exit and
post-commit counts, then re-enable the single daily UTC schedule and traffic.
A successfully committed reset intentionally replaces visitor data; restoring
that previous state requires a verified backup and an explicit recovery decision.
Database reset does not restore or delete uploads, Redis or vectors.

## AI-key rotation and spending incident

Disable or revoke the affected key in the provider account, remove all active
provider-key aliases from the API/worker secret stores, and redeploy with AI
unconfigured if immediate containment is needed. Retain `DEMO_MODE=true` and
`WORKSHOP_PAYMENT_MODE=demo`; `/ready` may report optional AI degradation while
core Demo flows remain available. Provision a replacement backend-only key in
the platform store, scoped to the intended provider/project and spend limit;
restart only affected services and check configuration readiness. Readiness does
not validate a key or make a paid request. Run any real paid model smoke only as
an authorized operation and verify provider spending. Inspect quota settings and
return the infrastructure plus AI target to at most A$30/month. Never place a key
in frontend builds, reset service, repository secrets or logs.

## Emergency Demo disable

Remove/pause the Demo frontend's public access and the API's public ingress
through native platform controls; pause workers and the reset schedule if the
incident involves data. Keep the Case Study available only with accurate release
status and disabled Demo link. Confirm approved origins no longer expose the Demo.
Do not switch public API `DEMO_MODE` to `false` or payments to `iyzico_sandbox` as a
shutdown mechanism: public startup requires Demo/simulated-payment flags. To
reopen, follow the complete release gate, confirm the incident is contained,
verify applied platform settings/readiness and restore the single reset schedule.

These are operator procedures, not activated automation. Existing TOML files are
reference settings; verify native configuration and supported behavior before
launch and before Railway's 2026-12-01 legacy-file deadline.
