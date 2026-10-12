# Demo release and maintenance

This runbook describes release operations. The public repository and provisioned
services now have verified release evidence; see the [publication record](../release/publication-record.md).
Committed configuration, passing local checks and a CI handoff alone do not prove
a cloud deployment or cron activation.
Use the [environment matrix](environment-matrix.md) and existing
[platform configuration](../public-deployment.md) for exact variables.

## CI and approval capability

Run **Preview release gate** manually on the intended commit with
`operation=native-handoff`. It calls the complete existing CI workflow: backend,
mobile, public-copy/secret checks, Case Study unit/build and browser checks.
The handoff only runs after all CI jobs pass and records the commit SHA. Deploy
that exact commit; a new commit needs a new full CI gate.

The personal repository is now public at [Grainjin/workshop-ai-showcase](https://github.com/Grainjin/workshop-ai-showcase).
The original private-preview approval limitations below explain the current
workflow guard; public visibility alone does not configure a protected environment.
An environment name alone is not approval: GitHub can auto-create an absent
environment without protection. Private environment access requires eligible
plans, and required-reviewer rules on Free/Pro/Team are public-only, according to
[GitHub environment documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
No paid GitHub upgrade is authorized. The existing `operation=external-deploy` still
fails visibly after CI. The workflow has no cloud credentials and no environment
reference that could create an unprotected environment. Do not add secrets to an
unverified private environment or enable automatic cloud deployment from pushes.

The release uses the authorized native platforms after the CI gate. A future
GitHub deployment path requires a separately
reviewed implementation: first verify the actual environment exists with required
reviewers, prevent self-approval, restrict release branches, and test that access
to secrets is blocked before approval. Then use environment-scoped project tokens
or narrowly scoped hooks, fail on missing credentials or target IDs, and verify
terminal deployment status before reporting success. Do not use a workspace-wide
API token, `secrets: inherit`, raw command inputs, or trigger receipts as proof.

## Native preview/public release

1. Record the green full-CI commit, current API image/deployment ID, both Vercel
   deployment IDs, migration revision, database backup reference, and target
   project/environment/service IDs. Keep credentials out of this record.
2. In the authorized personal Railway project, explicitly apply and inspect API
   build/start/pre-deploy/health/restart settings from `railway.toml` through native
   settings or the connector. Provision Demo/simulated-payment flags, approved
   HTTPS CORS origins, guarded private PostgreSQL URL and stable RSA keys in the
   platform secret store. Optional model keys stay backend-only. Check the total
   infrastructure plus AI estimate is at most A$30/month before provisioning.
3. Deploy the exact green commit to the selected API service/environment. The
   documented deploy interface is native Railway deployment, or the attached
   [Railway upload/deploy CLI](https://docs.railway.com/cli/up) with explicit project,
   service and environment IDs. A project-scoped token is supplied only from a
   verified protected operations context; missing token/IDs must refuse the
   operation. Do not use `--detach` or `--ci` as completion evidence. Native status
   must reach success, migration must complete before traffic, and startup must
   pass the configured `/health` check. Failure stops release; use the rollback
   runbook. Review logs privately and record only sanitized outcomes and IDs.
4. Check `/ready` on the approved HTTPS API origin: database readiness must be
   healthy; absent optional AI/Redis/vector configuration may report degradation.
   `/health` remains dependency-free liveness. Core Demo navigation and simulated
   payment flows must work even when AI is unavailable. Verify allowed browser
   origins and WSS behavior without printing credential-bearing URLs.
5. Configure independent Vercel Demo (`frontend/mobile`) and Case Study
   (`showcase/site`) projects with the public variables from the matrix. Build the
   same green commit, wait for each native deployment to finish, and verify direct
   SPA navigation, readiness notice, release links and Demo/payment labels. Do not
   promote an older frontend with endpoints or flags mismatched to the API.
6. Record applied settings and actual deployment IDs, smoke results, optional
   degradation, spend controls and rollback targets. Preview activation and secret
   provisioning are Task 5 operations; public acceptance evidence is Task 6.

Railway's current [configuration reference](https://docs.railway.com/config-as-code/reference)
marks TOML configuration deprecated, with legacy support ending 2026-12-01.
Retain the reviewed TOMLs as setting references, but do not rely on file recognition
for new services: the controller must apply and verify every required native
setting before launch. Add a maintenance check before that deadline to confirm
supported native settings or plan a separately reviewed IaC migration.

## Daily private-network reset

Only the dedicated Railway reset service schedules daily data maintenance. Its
reference file is `railway-reset.toml`, using the same Docker build as the API and
the guarded command:

```sh
/app/docker/api/entrypoint.sh reset-demo --confirm reset-workshop-demo
```

Native settings must explicitly match: Dockerfile `docker/api/Dockerfile`, root
repository build context, start command above, cron `0 17 * * *` UTC, restart policy
`NEVER`, no pre-deploy command, no API HTTP health check, no public domain, and the
minimum reset environment in the matrix. Clear inherited API health/pre-deploy
settings and disable the image's API-only HTTP probe in any runtime that honors
Docker `HEALTHCHECK`. Protect native project access, select exact service and
environment IDs, and never attach LLM keys or broad shared secret groups.

The schedule is 04:00 Sydney during daylight saving and 03:00 during standard
time. [Railway cron jobs](https://docs.railway.com/cron-jobs) use UTC, require the
process to exit, and skip an occurrence if the previous execution is still active.
There is no restart loop. As of 2026-10-12 the daily 17:00 UTC schedule is active and
its first execution succeeded. Confirm later executions from actual completion;
configuration committed here does not itself install a schedule. No reset was
performed during the final documentation update.

The manual GitHub **Demo reset isolated dry run** workflow migrates its own runner
PostgreSQL database, runs the real reset CLI, and verifies reset safety/rollback.
It requires no external secret and has no daily schedule. A GitHub-hosted runner
cannot resolve Railway's private database hostname;
[Railway run](https://docs.railway.com/cli/run) executes locally, so it is not a
remote reset interface. Do not add a public database proxy or HTTP reset endpoint.

For an actual manual reset, use native Railway **Run Now** on the explicitly
selected protected reset service, after confirming the running image, environment,
database marker and migrations. UI availability must be checked during activation;
if no native run action is available, stop and verify a supported remote interface
instead of running the command locally with injected private database variables.
No reliable command for an awaited remote cron run was verified for this task, so
none is embedded in GitHub Actions.

Pause Demo traffic and any workers for the maintenance window, wait for actual
process completion, and record the sanitized exit code plus post-commit JSON
summary (`database`, `seed`, `table_counts`). Success includes 36 users, 30 provider
profiles and 300 completed bookings; quota counters and visitor chats/payments are
cleared. A trigger receipt or an `Active` job is not success. A nonzero exit must
remain a visible operations failure; use [rollback](rollback.md). Resume traffic
only after readiness and sample data checks. Disable any old server cron before
activation so only one scheduler exists. Uploaded files, Redis and vector data
are not cleared by this database-only reset.
